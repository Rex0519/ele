import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.db.models import ConfigArea, Device, DeviceProfile, ElectricData, Alert


@pytest.fixture
def export_dir(tmp_path):
    return tmp_path / "data_export"


@pytest.fixture
def mock_db():
    db = MagicMock()

    areas = [
        _make(config_id="1", name="西北楼", parent_id=None, level=1, energy_type="electric", park_id=1, is_delete=0),
        _make(config_id="2", name="东南楼", parent_id=None, level=1, energy_type="electric", park_id=1, is_delete=0),
    ]

    devices = [
        _make(device_id=101, device_no="D001", device_name="西北楼-照明-01", point_type_id=1, region_id=1, building_id=1, floor_id=1, status=1, remark=None),
    ]

    profiles = [
        _make(point_id="XBL-ZM-01", device_id=101, display_name="西北楼照明01", device_type="照明", area_name="西北楼", mean_value=5.0, std_value=1.0, min_value=2.0, max_value=10.0, last_value=5.0),
    ]

    now = datetime.now(timezone.utc)
    electric_rows = [
        _make(time=now, device_id=101, point_id="XBL-ZM-01", value=100.0, incr=5.0),
    ]

    alerts = [
        _make(id=1, device_id=101, point_id="XBL-ZM-01", alert_type="THRESHOLD", severity="WARNING", message="超阈值", value=20.0, threshold=18.0, created_at=now, resolved_at=None),
    ]

    def query_side_effect(model):
        mock_query = MagicMock()
        data_map = {
            ConfigArea: areas,
            Device: devices,
            DeviceProfile: profiles,
            ElectricData: electric_rows,
            Alert: alerts,
        }
        mock_query.all.return_value = data_map.get(model, [])
        mock_query.filter.return_value = mock_query
        return mock_query

    db.query.side_effect = query_side_effect
    return db


def _make(**kwargs):
    return SimpleNamespace(**kwargs)


def test_export_creates_all_files(mock_db, export_dir):
    from src.export.csv_exporter import CsvExporter

    exporter = CsvExporter(mock_db, export_dir)
    exporter.export_all()

    assert (export_dir / "areas.csv").exists()
    assert (export_dir / "devices.csv").exists()
    assert (export_dir / "electric_data.csv").exists()
    assert (export_dir / "alerts.csv").exists()
    assert (export_dir / "_metadata.json").exists()


def test_areas_csv_content(mock_db, export_dir):
    from src.export.csv_exporter import CsvExporter

    exporter = CsvExporter(mock_db, export_dir)
    exporter.export_all()

    with open(export_dir / "areas.csv") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 2
    assert reader[0]["name"] == "西北楼"


def test_devices_csv_joins_profile(mock_db, export_dir):
    from src.export.csv_exporter import CsvExporter

    exporter = CsvExporter(mock_db, export_dir)
    exporter.export_all()

    with open(export_dir / "devices.csv") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 1
    assert reader[0]["point_id"] == "XBL-ZM-01"
    assert reader[0]["device_type"] == "照明"
    assert reader[0]["area_name"] == "西北楼"


def test_metadata_json_structure(mock_db, export_dir):
    from src.export.csv_exporter import CsvExporter

    exporter = CsvExporter(mock_db, export_dir)
    exporter.export_all()

    with open(export_dir / "_metadata.json") as f:
        meta = json.load(f)
    assert "exported_at" in meta
    assert "tables" in meta
    assert "devices" in meta["tables"]
    assert "electric_data" in meta["tables"]
