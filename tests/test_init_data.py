import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.db.init_data import extract_device_profiles, extract_device_profiles_from_devices


def test_extract_device_profiles():
    mock_df = pd.DataFrame({
        "point_id": ["p1", "p1", "p2", "p2"],
        "value": [100.0, 110.0, 200.0, 220.0],
        "incr": [10.0, 12.0, 20.0, 22.0],
    })

    profiles = extract_device_profiles(mock_df)

    assert "p1" in profiles
    assert "p2" in profiles
    assert profiles["p1"]["mean_value"] == pytest.approx(11.0, rel=0.1)
    assert profiles["p2"]["mean_value"] == pytest.approx(21.0, rel=0.1)


def test_extract_device_profiles_from_devices():
    mock_device_df = pd.DataFrame({
        "device_id": [1001, 1002, 1003],
        "device_name": ["F-WS-AT-tlzm-s1-总表", "F-EN-AP-kt-s1-1-空调WK3", "(243-Z1)APgl-7-箱门表"],
    })

    profiles = extract_device_profiles_from_devices(mock_device_df)

    assert len(profiles) == 3

    p1 = profiles[0]
    assert p1["area_name"] == "西南"
    assert p1["device_type"] == "照明"
    assert p1["point_id"] == "XNL-ZM-01"
    assert p1["display_name"] == "西南-照明-01号"

    p2 = profiles[1]
    assert p2["area_name"] == "东北"
    assert p2["device_type"] == "空调"
    assert p2["point_id"] == "DBL-KT-01"

    p3 = profiles[2]
    assert p3["area_name"] == "243层"
    assert p3["device_type"] == "公共照明"
    assert p3["point_id"] == "243C-GL-01"
