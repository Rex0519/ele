from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.db.maintenance import DataMaintenance


def test_cleanup_expired_alerts():
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


def _make_backfill_mock(existing_hours: list[datetime]):
    """构造 backfill 测试用的 mock db"""
    mock_db = MagicMock()

    # cleanup_expired_alerts 用的 execute
    cleanup_result = MagicMock()
    cleanup_result.rowcount = 0

    # backfill 用的 execute：返回已有时间点
    backfill_result = MagicMock()
    backfill_result.__iter__ = lambda self: iter([(h,) for h in existing_hours])

    mock_db.execute.return_value = backfill_result

    from src.db.models import DeviceProfile
    profile = DeviceProfile(
        point_id="test-001", mean_value=10.0, std_value=1.0, last_value=100.0,
    )
    mock_db.query.return_value.all.return_value = [profile]

    return mock_db


def test_backfill_detects_gap():
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    # 最近3小时中只有第1小时有数据，缺2小时
    existing = [now - timedelta(hours=3)]
    mock_db = _make_backfill_mock(existing)

    m = DataMaintenance(mock_db)
    count = m.backfill_missing_data(days=1)

    # 缺失: now-2h, now-1h, now = 至少2个（取决于精确时间）
    assert count >= 2


def test_backfill_no_gap():
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    # 最近24小时全有数据
    existing = [now - timedelta(hours=i) for i in range(25)]
    mock_db = _make_backfill_mock(existing)

    m = DataMaintenance(mock_db)
    count = m.backfill_missing_data(days=1)

    assert count == 0
