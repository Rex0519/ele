import re

DEVICE_TYPES = {
    "tlzm": "照明",
    "kt": "空调",
    "ft": "扶梯",
    "fj": "风机",
    "sy": "水泵",
    "gg": "广告",
    "xx": "消防",
    "gl": "公共照明",
    "py": "配电",
    "pdj": "配电间",
    "wsj": "污水井",
    "rsq": "热水器",
}

AREA_ABBR = {
    "西北": "XBL",
    "西南": "XNL",
    "东北": "DBL",
    "东南": "DNL",
    "中南": "ZNL",
    "中北": "ZBL",
    "243层": "243C",
    "238层": "238C",
    "249层": "249C",
    "能源中心": "NYZX",
    "地下负2层": "DXF2",
    "地下负3层": "DXF3",
    "其他": "QT",
}

AREA_ABBR_REVERSE = {v: k for k, v in AREA_ABBR.items()}
DEVICE_TYPE_ABBR = {
    "照明": "ZM",
    "空调": "KT",
    "扶梯": "FT",
    "风机": "FJ",
    "水泵": "SB",
    "广告": "GG",
    "消防": "XF",
    "公共照明": "GL",
    "配电": "PD",
    "配电间": "PDJ",
    "污水井": "WSJ",
    "热水器": "RSQ",
    "其他": "QT",
}


def parse_device_name(name: str) -> dict:
    """解析设备名称，提取区域和设备类型"""
    area = _extract_area(name)
    device_type = _extract_device_type(name)
    return {"area": area, "device_type": device_type}


def _extract_area(name: str) -> str:
    name_upper = name.upper()
    if re.search(r"F-WS|[-_]WS[-_]", name_upper):
        return "西南"
    if re.search(r"F-WN|[-_]WN[-_]", name_upper):
        return "西北"
    if re.search(r"F-ES|[-_]ES[-_]", name_upper):
        return "东南"
    if re.search(r"F-EN|[-_]EN[-_]", name_upper):
        return "东北"
    if re.search(r"F-CS|[-_]CS[-_]", name_upper):
        return "中南"
    if re.search(r"F-CN|[-_]CN[-_]", name_upper):
        return "中北"
    if "243" in name:
        return "243层"
    if "238" in name:
        return "238层"
    if "249" in name:
        return "249层"
    if re.search(r"H[23][-_]", name_upper):
        return "能源中心"
    return "其他"


def _extract_device_type(name: str) -> str:
    name_lower = name.lower()
    for code, type_name in DEVICE_TYPES.items():
        if code in name_lower:
            return type_name
    if "照明" in name:
        return "照明"
    if "空调" in name:
        return "空调"
    if "热水器" in name:
        return "热水器"
    return "其他"


def generate_point_id(area: str, device_type: str, seq: int) -> str:
    """生成可读的 point_id"""
    area_code = AREA_ABBR.get(area, "QT")
    type_code = DEVICE_TYPE_ABBR.get(device_type, "QT")
    return f"{area_code}-{type_code}-{seq:02d}"


def generate_display_name(area: str, device_type: str, seq: int) -> str:
    """生成中文显示名称"""
    return f"{area}-{device_type}-{seq:02d}号"
