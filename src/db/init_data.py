from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from src.db.models import ConfigArea, ConfigItem, Device, ConfigDevice, DeviceProfile


def extract_device_profiles(df: pd.DataFrame) -> dict:
    """从电力数据中提取设备特征"""
    profiles = {}
    for point_id, group in df.groupby("point_id"):
        profiles[point_id] = {
            "point_id": point_id,
            "mean_value": group["incr"].mean(),
            "std_value": group["incr"].std() if len(group) > 1 else 0,
            "min_value": group["incr"].min(),
            "max_value": group["incr"].max(),
            "last_value": group["value"].iloc[-1] if len(group) > 0 else 0,
        }
    return profiles


def load_excel_data(db: Session, data_dir: Path) -> None:
    """从 Excel 文件导入数据到数据库"""
    # 导入区域配置
    area_df = pd.read_excel(data_dir / "ene_config_area.xls")
    for _, row in area_df.iterrows():
        if row.get("is_delete") == 1:
            continue
        db.merge(ConfigArea(
            config_id=str(row["config_id"]),
            parent_id=str(row["config_parent_id"]) if pd.notna(row["config_parent_id"]) else None,
            name=row["config_name"],
            level=int(row["config_level"]) if pd.notna(row["config_level"]) else None,
            energy_type=row["energy_type"],
            park_id=int(row["park_id"]) if pd.notna(row["park_id"]) else None,
        ))

    # 导入项目配置
    item_df = pd.read_excel(data_dir / "ene_config_item.xls")
    for _, row in item_df.iterrows():
        if row.get("is_delete") == 1:
            continue
        db.merge(ConfigItem(
            config_id=str(row["config_id"]),
            parent_id=str(row["config_parent_id"]) if pd.notna(row["config_parent_id"]) else None,
            name=row["config_name"],
            level=int(row["config_level"]) if pd.notna(row["config_level"]) else None,
            energy_type=row["energy_type"],
            park_id=int(row["park_id"]) if pd.notna(row["park_id"]) else None,
        ))

    # 导入设备信息
    device_df = pd.read_excel(data_dir / "devicenfo.xls")
    for _, row in device_df.iterrows():
        db.merge(Device(
            device_id=int(row["device_id"]),
            device_no=row["device_no"],
            device_name=row["device_name"],
            point_type_id=int(row["point_type_id"]) if pd.notna(row["point_type_id"]) else None,
            region_id=int(row["region_id"]) if pd.notna(row["region_id"]) else None,
            building_id=int(row["building_id"]) if pd.notna(row["building_id"]) else None,
            floor_id=int(row["floor_id"]) if pd.notna(row["floor_id"]) else None,
            status=int(row["status"]) if pd.notna(row["status"]) else 1,
            remark=row["remark"] if pd.notna(row["remark"]) else None,
        ))

    # 导入设备-配置关联
    config_device_df = pd.read_excel(data_dir / "ene_config_device.xls")
    for _, row in config_device_df.iterrows():
        db.merge(ConfigDevice(
            config_device_id=int(row["config_device_id"]),
            config_id=str(row["config_id"]) if pd.notna(row["config_id"]) else None,
            device_id=int(row["device_id"]) if pd.notna(row["device_id"]) else None,
            device_level=int(row["device_level"]) if pd.notna(row["device_level"]) else None,
            energy_type=row["energy_type"],
            config_type=row["config_type"],
        ))

    # 提取设备特征
    electric_df = pd.read_excel(data_dir / "electric.xls")
    profiles = extract_device_profiles(electric_df)
    for profile in profiles.values():
        db.merge(DeviceProfile(**profile))

    db.commit()
