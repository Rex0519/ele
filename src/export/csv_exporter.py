import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.models import Alert, ConfigArea, Device, DeviceProfile, ElectricData


class CsvExporter:
    def __init__(self, db: Session, export_dir: Path | str = "data_export"):
        self.db = db
        self.export_dir = Path(export_dir)

    def export_all(self):
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self._export_areas()
        self._export_devices()
        self._export_electric_data()
        self._export_alerts()
        self._write_metadata()

    def _export_areas(self):
        areas = self.db.query(ConfigArea).filter(ConfigArea.is_delete == 0).all()
        self._write_csv(
            "areas.csv",
            ["config_id", "name", "parent_id", "level", "energy_type", "park_id"],
            [
                {
                    "config_id": a.config_id,
                    "name": a.name,
                    "parent_id": a.parent_id,
                    "level": a.level,
                    "energy_type": a.energy_type,
                    "park_id": a.park_id,
                }
                for a in areas
            ],
        )

    def _export_devices(self):
        devices = self.db.query(Device).all()
        profiles = {p.device_id: p for p in self.db.query(DeviceProfile).all()}
        rows = []
        for d in devices:
            p = profiles.get(d.device_id)
            rows.append(
                {
                    "device_id": d.device_id,
                    "device_name": d.device_name,
                    "device_no": d.device_no,
                    "device_type": p.device_type if p else "",
                    "area_name": p.area_name if p else "",
                    "point_id": p.point_id if p else "",
                    "rated_power": p.mean_value if p else "",
                }
            )
        self._write_csv(
            "devices.csv",
            ["device_id", "device_name", "device_no", "device_type", "area_name", "point_id", "rated_power"],
            rows,
        )

    def _export_electric_data(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        data = self.db.query(ElectricData).filter(ElectricData.time >= cutoff).all()
        self._write_csv(
            "electric_data.csv",
            ["point_id", "time", "value", "incr"],
            [{"point_id": r.point_id, "time": r.time.isoformat(), "value": r.value, "incr": r.incr} for r in data],
        )

    def _export_alerts(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        alerts = (
            self.db.query(Alert).filter((Alert.resolved_at.is_(None)) | (Alert.resolved_at >= cutoff)).all()
        )
        self._write_csv(
            "alerts.csv",
            ["id", "point_id", "device_id", "alert_type", "severity", "message", "value", "threshold", "created_at", "resolved_at"],
            [
                {
                    "id": a.id,
                    "point_id": a.point_id,
                    "device_id": a.device_id,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "value": a.value,
                    "threshold": a.threshold,
                    "created_at": a.created_at.isoformat() if a.created_at else "",
                    "resolved_at": a.resolved_at.isoformat() if a.resolved_at else "",
                }
                for a in alerts
            ],
        )

    def _write_metadata(self):
        meta = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "data_range_days": 30,
            "tables": {
                "areas": {"file": "areas.csv", "description": "区域配置列表"},
                "devices": {
                    "file": "devices.csv",
                    "description": "设备列表，含所属区域和额定功率。通过 point_id 关联 electric_data",
                    "join": "devices.point_id → electric_data.point_id",
                },
                "electric_data": {
                    "file": "electric_data.csv",
                    "description": "逐小时用电数据。value=累计值(kWh)，incr=该小时增量(kWh)",
                    "join": "electric_data.point_id → devices.point_id",
                },
                "alerts": {
                    "file": "alerts.csv",
                    "description": "告警记录。resolved_at 为空表示未解决",
                    "join": "alerts.point_id → devices.point_id",
                },
            },
            "usage_example": "import pandas as pd; devices = pd.read_csv('devices.csv'); data = pd.read_csv('electric_data.csv', parse_dates=['time']); merged = data.merge(devices[['point_id','device_name','area_name']], on='point_id')",
        }
        with open(self.export_dir / "_metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def _write_csv(self, filename: str, fieldnames: list[str], rows: list[dict]):
        with open(self.export_dir / filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
