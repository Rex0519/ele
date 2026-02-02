import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.db.init_data import extract_device_profiles


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
