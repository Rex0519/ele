from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import Alert, ElectricData, ThresholdConfig
from src.alert.rules import AlertType, Severity, check_threshold, check_trend


class AlertDetector:
    def __init__(self, db: Session):
        self.db = db

    def detect_all(self) -> list[Alert]:
        alerts: list[Alert] = []
        alerts.extend(self._detect_threshold_alerts())
        alerts.extend(self._detect_trend_alerts())
        alerts.extend(self._detect_offline_alerts())
        return alerts

    def _detect_threshold_alerts(self) -> list[Alert]:
        alerts: list[Alert] = []
        configs = self.db.query(ThresholdConfig).all()

        for config in configs:
            latest = (
                self.db.query(ElectricData)
                .filter(ElectricData.device_id == config.device_id)
                .order_by(ElectricData.time.desc())
                .first()
            )
            if not latest:
                continue

            result = check_threshold(
                value=latest.incr or 0,
                min_val=config.min_value,
                max_val=config.max_value,
                severity=config.severity,
            )
            if result:
                alert = Alert(
                    device_id=config.device_id,
                    alert_type=result["type"],
                    severity=result["severity"],
                    message=result["message"],
                    value=latest.incr,
                    threshold=result["threshold"],
                )
                self.db.add(alert)
                alerts.append(alert)

        self.db.commit()
        return alerts

    def _detect_trend_alerts(self) -> list[Alert]:
        alerts: list[Alert] = []
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        subq = (
            self.db.query(
                ElectricData.device_id,
                func.max(ElectricData.time).label("max_time"),
            )
            .filter(ElectricData.time >= hour_ago)
            .group_by(ElectricData.device_id)
            .subquery()
        )

        current_data = (
            self.db.query(ElectricData)
            .join(
                subq,
                (ElectricData.device_id == subq.c.device_id)
                & (ElectricData.time == subq.c.max_time),
            )
            .all()
        )

        for current in current_data:
            previous = (
                self.db.query(ElectricData)
                .filter(
                    ElectricData.device_id == current.device_id,
                    ElectricData.time >= day_ago - timedelta(hours=1),
                    ElectricData.time <= day_ago,
                )
                .order_by(ElectricData.time.desc())
                .first()
            )
            if not previous:
                continue

            result = check_trend(
                current=current.incr or 0,
                previous=previous.incr or 0,
            )
            if result:
                alert = Alert(
                    device_id=current.device_id,
                    alert_type=result["type"],
                    severity=result["severity"],
                    message=result["message"],
                    value=current.incr,
                    threshold=result["threshold"],
                )
                self.db.add(alert)
                alerts.append(alert)

        self.db.commit()
        return alerts

    def _detect_offline_alerts(self) -> list[Alert]:
        alerts: list[Alert] = []
        threshold = datetime.now() - timedelta(hours=2)

        subq = (
            self.db.query(
                ElectricData.device_id,
                func.max(ElectricData.time).label("last_time"),
            )
            .group_by(ElectricData.device_id)
            .subquery()
        )

        offline_devices = (
            self.db.query(subq.c.device_id)
            .filter(subq.c.last_time < threshold)
            .all()
        )

        for (device_id,) in offline_devices:
            existing = (
                self.db.query(Alert)
                .filter(
                    Alert.device_id == device_id,
                    Alert.alert_type == AlertType.OFFLINE,
                    Alert.resolved_at.is_(None),
                )
                .first()
            )
            if existing:
                continue

            alert = Alert(
                device_id=device_id,
                alert_type=AlertType.OFFLINE,
                severity=Severity.HIGH,
                message="设备超过2小时无数据上报",
            )
            self.db.add(alert)
            alerts.append(alert)

        self.db.commit()
        return alerts
