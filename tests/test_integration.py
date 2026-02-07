import asyncio

from unittest.mock import MagicMock

from src.db.device_parser import parse_device_name, generate_point_id, generate_display_name


def test_device_parser_to_mcp_workflow():
    """集成测试：设备名称解析 → 生成可读 ID → MCP 工具查询"""
    from src.mcp.server import _list_devices

    # 1. 解析设备名称
    parsed = parse_device_name("F-WS-AT-tlzm-s1-总表")
    assert parsed["area"] == "西南"
    assert parsed["device_type"] == "照明"

    # 2. 生成可读 ID
    point_id = generate_point_id(parsed["area"], parsed["device_type"], 1)
    display_name = generate_display_name(parsed["area"], parsed["device_type"], 1)
    assert point_id == "XNL-ZM-01"
    assert display_name == "西南-照明-01号"

    # 3. 通过 MCP 工具查询
    mock_profile = MagicMock()
    mock_profile.point_id = point_id
    mock_profile.display_name = display_name
    mock_profile.device_type = "照明"
    mock_profile.area_name = "西南"

    db = MagicMock()
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = [mock_profile]

    result = _list_devices(db, {"area": "西南"})
    assert "XNL-ZM-01" in result[0].text
    assert "西南-照明-01号" in result[0].text


def test_extract_profiles_to_query_workflow():
    """集成测试：从设备表提取 profile → 通过名称查询电力数据"""
    import pandas as pd
    from src.db.init_data import extract_device_profiles_from_devices
    from src.mcp.server import _query_electric_data

    # 1. 从设备表提取 profile
    device_df = pd.DataFrame({
        "device_id": [1001],
        "device_name": ["F-EN-AP-kt-s1-1-空调WK3"],
    })
    profiles = extract_device_profiles_from_devices(device_df)
    assert len(profiles) == 1
    assert profiles[0]["point_id"] == "DBL-KT-01"
    assert profiles[0]["area_name"] == "东北"

    # 2. 通过名称查询（无数据场景）
    mock_profile = MagicMock()
    mock_profile.point_id = profiles[0]["point_id"]
    mock_profile.display_name = profiles[0]["display_name"]

    db = MagicMock()
    profile_query = MagicMock()
    profile_query.filter.return_value.limit.return_value.all.return_value = [mock_profile]
    data_query = MagicMock()
    data_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.side_effect = [profile_query, data_query]

    result = _query_electric_data(db, {"device_name": "东北空调"})
    assert "东北-空调-01号" in result[0].text
