from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.db import get_db, Alert, ThresholdConfig

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int | None
    point_id: str | None
    alert_type: str
    severity: str
    message: str | None
    value: float | None
    threshold: float | None
    created_at: str
    resolved_at: str | None


class ThresholdConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int | None
    point_id: str | None
    metric: str
    min_value: float | None
    max_value: float | None
    severity: str


class ThresholdConfigUpdate(BaseModel):
    min_value: float | None = None
    max_value: float | None = None
    severity: str | None = None


def _alert_to_response(a: Alert) -> AlertResponse:
    return AlertResponse(
        id=a.id,
        device_id=a.device_id,
        point_id=a.point_id,
        alert_type=a.alert_type,
        severity=a.severity,
        message=a.message,
        value=a.value,
        threshold=a.threshold,
        created_at=a.created_at.isoformat() if a.created_at else "",
        resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
    )


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    severity: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Alert)
    if severity:
        query = query.filter(Alert.severity == severity)
    alerts = query.order_by(Alert.created_at.desc()).limit(limit).offset(offset).all()
    return [_alert_to_response(a) for a in alerts]


@router.get("/active", response_model=list[AlertResponse])
def list_active_alerts(db: Session = Depends(get_db)):
    alerts = (
        db.query(Alert)
        .filter(Alert.resolved_at.is_(None))
        .order_by(Alert.created_at.desc())
        .all()
    )
    return [_alert_to_response(a) for a in alerts]


@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.resolved_at:
        raise HTTPException(status_code=400, detail="Alert already resolved")
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "resolved", "alert_id": alert_id}


@router.get("/thresholds", response_model=list[ThresholdConfigResponse])
def list_thresholds(db: Session = Depends(get_db)):
    return db.query(ThresholdConfig).all()


@router.put("/thresholds/{point_id}")
def update_threshold(
    point_id: str,
    update: ThresholdConfigUpdate,
    db: Session = Depends(get_db),
):
    config = (
        db.query(ThresholdConfig)
        .filter(ThresholdConfig.point_id == point_id)
        .first()
    )
    if not config:
        config = ThresholdConfig(point_id=point_id)
        db.add(config)

    if update.min_value is not None:
        config.min_value = update.min_value
    if update.max_value is not None:
        config.max_value = update.max_value
    if update.severity is not None:
        config.severity = update.severity

    db.commit()
    return {"status": "updated", "point_id": point_id}
