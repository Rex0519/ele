from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.db.maintenance import DataMaintenance


def test_cleanup_expired_alerts():
    """清理超过30天的 alert 记录"""
    mock_db = MagicMock()
    mock_db.execute.return_value.rowcount = 5

    m = DataMaintenance(mock_db)
    count = m.cleanup_expired_alerts(days=30)

    assert count == 5
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()
    sql_text = str(mock_db.execute.call_args[0][0])
    assert "alert" in sql_text
    assert "created_at" in sql_text


def test_backfill_missing_data_detects_gap():
    """检测到数据空缺时逐小时补全"""
    mock_db = MagicMock()

    three_hours_ago = datetime.now() - timedelta(hours=3)
    mock_result = MagicMock()
    mock_result.scalar.return_value = three_hours_ago
    mock_db.execute.return_value = mock_result

    from src.db.models import DeviceProfile
    profile = DeviceProfile(
        point_id="test-001", mean_value=10.0, std_value=1.0, last_value=100.0,
    )
    mock_db.query.return_value.all.return_value = [profile]

    m = DataMaintenance(mock_db)
    count = m.backfill_missing_data(days=30)

    # 应该补全 2 个小时（3小时前到1小时前，当前小时由调度器负责）
    assert count == 2


def test_backfill_missing_data_empty_table():
    """表为空时从30天前开始补全"""
    mock_db = MagicMock()

    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_db.execute.return_value = mock_result

    from src.db.models import DeviceProfile
    profile = DeviceProfile(
        point_id="test-001", mean_value=10.0, std_value=1.0, last_value=0.0,
    )
    mock_db.query.return_value.all.return_value = [profile]

    m = DataMaintenance(mock_db)
    count = m.backfill_missing_data(days=30)

    # 30天 × 24小时 - 1（当前小时由调度器负责）
    assert count == 30 * 24 - 1


def test_backfill_no_gap():
    """无数据缺口时不补全"""
    mock_db = MagicMock()

    recent = datetime.now() - timedelta(minutes=30)
    mock_result = MagicMock()
    mock_result.scalar.return_value = recent
    mock_db.execute.return_value = mock_result

    m = DataMaintenance(mock_db)
    count = m.backfill_missing_data(days=30)

    assert count == 0
