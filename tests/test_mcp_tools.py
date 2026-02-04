import asyncio

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_db():
    return MagicMock()


def test_list_areas_returns_area_list(mock_db):
    from src.mcp.server import _list_areas

    mock_area1 = MagicMock()
    mock_area1.name = "西北楼"
    mock_area2 = MagicMock()
    mock_area2.name = "西南楼"
    mock_area3 = MagicMock()
    mock_area3.name = "243层"

    mock_db.query.return_value.filter.return_value.all.return_value = [
        mock_area1, mock_area2, mock_area3,
    ]

    result = asyncio.run(_list_areas(mock_db, {}))

    assert len(result) == 1
    assert "西北楼" in result[0].text
    assert "西南楼" in result[0].text
    assert "243层" in result[0].text


def test_list_areas_empty(mock_db):
    from src.mcp.server import _list_areas

    mock_db.query.return_value.filter.return_value.all.return_value = []

    result = asyncio.run(_list_areas(mock_db, {}))

    assert "暂无" in result[0].text


def test_list_devices_filter_by_area(mock_db):
    from src.mcp.server import _list_devices

    mock_p1 = MagicMock()
    mock_p1.point_id = "XBL-ZM-01"
    mock_p1.display_name = "西北-照明-01号"
    mock_p1.device_type = "照明"
    mock_p1.area_name = "西北"

    mock_p2 = MagicMock()
    mock_p2.point_id = "XBL-KT-01"
    mock_p2.display_name = "西北-空调-01号"
    mock_p2.device_type = "空调"
    mock_p2.area_name = "西北"

    # area only: db.query().filter(area).limit().all()
    mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = [mock_p1, mock_p2]

    result = asyncio.run(_list_devices(mock_db, {"area": "西北"}))

    assert "西北-照明-01号" in result[0].text
    assert "西北-空调-01号" in result[0].text


def test_list_devices_empty(mock_db):
    from src.mcp.server import _list_devices

    # no filters: db.query().limit().all()
    mock_db.query.return_value.limit.return_value.all.return_value = []

    result = asyncio.run(_list_devices(mock_db, {}))

    assert "未找到" in result[0].text


def test_compare_usage_day(mock_db):
    from src.mcp.server import _compare_usage

    # scalar() for today total
    mock_db.query.return_value.filter.return_value.scalar.return_value = 1000.0

    result = asyncio.run(_compare_usage(mock_db, {"compare_type": "day"}))

    assert "今日" in result[0].text or "用电" in result[0].text


def test_compare_usage_unsupported(mock_db):
    from src.mcp.server import _compare_usage

    result = asyncio.run(_compare_usage(mock_db, {"compare_type": "unknown"}))

    assert "不支持" in result[0].text


def test_query_electric_data_by_name_single_match(mock_db):
    from src.mcp.server import _query_electric_data

    mock_profile = MagicMock()
    mock_profile.point_id = "XBL-ZM-01"
    mock_profile.display_name = "西北-照明-01号"

    # First query: DeviceProfile lookup → returns [mock_profile]
    # Second query: ElectricData lookup → returns []
    call_count = {"n": 0}
    original_query = mock_db.query

    def side_effect_query(*args):
        call_count["n"] += 1
        return original_query(*args)

    # Simpler approach: use a fresh mock for this test
    db = MagicMock()
    # profile lookup chain: db.query().filter().limit().all() → [mock_profile]
    profile_query = MagicMock()
    profile_query.filter.return_value.limit.return_value.all.return_value = [mock_profile]

    # electric data chain: db.query().filter().order_by().limit().all() → []
    data_query = MagicMock()
    data_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    db.query.side_effect = [profile_query, data_query]

    result = asyncio.run(_query_electric_data(db, {"device_name": "西北照明"}))

    assert "西北-照明-01号" in result[0].text
    assert "无数据" in result[0].text


def test_query_electric_data_by_name_no_match(mock_db):
    from src.mcp.server import _query_electric_data

    db = MagicMock()
    profile_query = MagicMock()
    profile_query.filter.return_value.limit.return_value.all.return_value = []
    db.query.return_value = profile_query

    result = asyncio.run(_query_electric_data(db, {"device_name": "不存在的设备"}))

    assert "未找到" in result[0].text


def test_query_electric_data_missing_params(mock_db):
    from src.mcp.server import _query_electric_data

    result = asyncio.run(_query_electric_data(mock_db, {}))

    assert "请提供" in result[0].text


def test_get_area_summary_by_name(mock_db):
    from src.mcp.server import _get_area_summary

    mock_area = MagicMock()
    mock_area.name = "西北楼"
    mock_area.config_id = "123"

    db = MagicMock()
    # area lookup: db.query().filter().first() → mock_area
    area_query = MagicMock()
    area_query.filter.return_value.first.return_value = mock_area
    # stats: db.query().filter().first() → stats
    mock_stats = MagicMock()
    mock_stats.total = 1000.0
    mock_stats.avg = 10.0
    mock_stats.count = 100
    stats_query = MagicMock()
    stats_query.filter.return_value.first.return_value = mock_stats

    db.query.side_effect = [area_query, stats_query]

    result = asyncio.run(_get_area_summary(db, {"area_name": "西北"}))

    assert "西北楼" in result[0].text


def test_analyze_anomaly_by_name(mock_db):
    from src.mcp.server import _analyze_anomaly

    mock_profile = MagicMock()
    mock_profile.point_id = "XBL-ZM-01"
    mock_profile.display_name = "西北-照明-01号"

    db = MagicMock()
    # profile lookup
    profile_query = MagicMock()
    profile_query.filter.return_value.limit.return_value.all.return_value = [mock_profile]
    # electric data
    data_query = MagicMock()
    data_query.filter.return_value.all.return_value = []
    # alerts
    alert_query = MagicMock()
    alert_query.filter.return_value.all.return_value = []

    db.query.side_effect = [profile_query, data_query, alert_query]

    result = asyncio.run(_analyze_anomaly(db, {"device_name": "西北照明"}))

    assert "西北-照明-01号" in result[0].text
