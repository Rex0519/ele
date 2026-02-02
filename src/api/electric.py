from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db import get_db, ElectricData, ConfigArea

router = APIRouter(prefix="/electric", tags=["electric"])


class ElectricDataResponse(BaseModel):
    time: str
    device_id: int
    point_id: str | None
    value: float | None
    incr: float | None


class AreaSummaryResponse(BaseModel):
    area_id: int
    area_name: str | None
    total_value: float
    total_incr: float
    device_count: int


class StatisticsResponse(BaseModel):
    period: str
    total_consumption: float
    avg_hourly: float
    peak_hour: int | None
    peak_value: float | None


@router.get("/realtime", response_model=list[ElectricDataResponse])
def get_realtime_data(
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ElectricData)
        .order_by(ElectricData.time.desc())
        .limit(limit)
        .all()
    )
    return [
        ElectricDataResponse(
            time=r.time.isoformat(),
            device_id=r.device_id,
            point_id=r.point_id,
            value=r.value,
            incr=r.incr,
        )
        for r in rows
    ]


@router.get("/areas/{area_id}/summary", response_model=AreaSummaryResponse)
def get_area_summary(
    area_id: int,
    period: str = Query("day", pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
):
    area = db.query(ConfigArea).filter(ConfigArea.config_id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")

    now = datetime.now()
    start = now - timedelta(
        days=1 if period == "day" else 7 if period == "week" else 30,
    )

    stats = (
        db.query(
            func.sum(ElectricData.value).label("total_value"),
            func.sum(ElectricData.incr).label("total_incr"),
            func.count(func.distinct(ElectricData.device_id)).label("device_count"),
        )
        .filter(ElectricData.time >= start)
        .first()
    )

    return AreaSummaryResponse(
        area_id=area_id,
        area_name=area.name,
        total_value=stats.total_value or 0,
        total_incr=stats.total_incr or 0,
        device_count=stats.device_count or 0,
    )


@router.get("/statistics", response_model=StatisticsResponse)
def get_statistics(
    period: str = Query("day", pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
):
    now = datetime.now()
    start = now - timedelta(
        days=1 if period == "day" else 7 if period == "week" else 30,
    )

    total = (
        db.query(func.sum(ElectricData.incr))
        .filter(ElectricData.time >= start)
        .scalar()
    ) or 0

    hours = (now - start).total_seconds() / 3600
    avg_hourly = total / hours if hours > 0 else 0

    peak = (
        db.query(
            func.extract("hour", ElectricData.time).label("hour"),
            func.sum(ElectricData.incr).label("total"),
        )
        .filter(ElectricData.time >= start)
        .group_by(func.extract("hour", ElectricData.time))
        .order_by(func.sum(ElectricData.incr).desc())
        .first()
    )

    return StatisticsResponse(
        period=period,
        total_consumption=round(total, 2),
        avg_hourly=round(avg_hourly, 2),
        peak_hour=int(peak.hour) if peak else None,
        peak_value=round(peak.total, 2) if peak else None,
    )
