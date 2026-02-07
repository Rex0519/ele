from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.db import get_db, Device, ElectricData, DeviceProfile

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: int
    device_no: str | None
    device_name: str | None
    status: int | None


class DeviceDataResponse(BaseModel):
    time: str
    value: float | None
    incr: float | None


@router.get("", response_model=list[DeviceResponse])
def list_devices(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return db.query(Device).limit(limit).offset(offset).all()


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("/{device_id}/data", response_model=list[DeviceDataResponse])
def get_device_data(
    device_id: int,
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    profile = db.query(DeviceProfile).filter(DeviceProfile.device_id == device_id).first()
    if profile:
        rows = (
            db.query(ElectricData)
            .filter(ElectricData.point_id == profile.point_id)
            .order_by(ElectricData.time.desc())
            .limit(limit)
            .all()
        )
    else:
        rows = (
            db.query(ElectricData)
            .filter(ElectricData.device_id == device_id)
            .order_by(ElectricData.time.desc())
            .limit(limit)
            .all()
        )
    return [
        DeviceDataResponse(time=r.time.isoformat(), value=r.value, incr=r.incr)
        for r in rows
    ]
