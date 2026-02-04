import pytest
from src.db.device_parser import parse_device_name, DEVICE_TYPES, AREA_ABBR


def test_parse_lighting_device():
    result = parse_device_name("F-WS-AT-tlzm-s1-总表")
    assert result["area"] == "西南"
    assert result["device_type"] == "照明"


def test_parse_aircon_device():
    result = parse_device_name("F-EN-AP-kt-s1-1-空调WK3")
    assert result["area"] == "东北"
    assert result["device_type"] == "空调"


def test_parse_escalator_device():
    result = parse_device_name("F-WS-AT-ft-s1-3")
    assert result["area"] == "西南"
    assert result["device_type"] == "扶梯"


def test_parse_layer_device():
    result = parse_device_name("(243-Z1)APgl-7-箱门表")
    assert result["area"] == "243层"
    assert result["device_type"] == "公共照明"


def test_parse_energy_center_device():
    result = parse_device_name("(H3-6)ATz1-WLTD1")
    assert result["area"] == "能源中心"
    assert result["device_type"] == "其他"


def test_parse_unknown_device():
    result = parse_device_name("unknown-device-xyz")
    assert result["area"] == "其他"
    assert result["device_type"] == "其他"


def test_device_types_mapping():
    assert "照明" in DEVICE_TYPES.values()
    assert "空调" in DEVICE_TYPES.values()
    assert "扶梯" in DEVICE_TYPES.values()


def test_area_abbr_mapping():
    assert AREA_ABBR["西北"] == "XBL"
    assert AREA_ABBR["东南"] == "DNL"
    assert AREA_ABBR["243层"] == "243C"
