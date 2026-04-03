"""Calendar and harvest schedule router."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.harvest import HarvestSchedule
from app.schemas.harvest import HarvestCreate, HarvestUpdate, HarvestResponse
from app.services.demand_forecaster import forecast_demand

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/", response_model=List[HarvestResponse])
def get_monthly_calendar(
    year: int = Query(..., description="Year"),
    month: int = Query(..., description="Month (1-12)"),
    db: Session = Depends(get_db),
):
    """Get harvest schedules for a given month."""
    prefix = f"{year:04d}-{month:02d}"
    schedules = (
        db.query(HarvestSchedule)
        .filter(HarvestSchedule.harvest_date.like(f"{prefix}%"))
        .order_by(HarvestSchedule.harvest_date)
        .all()
    )
    return schedules


@router.post("/harvest", response_model=HarvestResponse)
def create_harvest_schedule(body: HarvestCreate, db: Session = Depends(get_db)):
    schedule = HarvestSchedule(
        product_id=body.product_id,
        harvest_date=body.harvest_date,
        estimated_quantity=body.estimated_quantity,
        status=body.status,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.put("/harvest/{schedule_id}", response_model=HarvestResponse)
def update_harvest_schedule(
    schedule_id: int,
    body: HarvestUpdate,
    db: Session = Depends(get_db),
):
    schedule = db.query(HarvestSchedule).filter(HarvestSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Harvest schedule not found")

    if body.harvest_date is not None:
        schedule.harvest_date = body.harvest_date
    if body.estimated_quantity is not None:
        schedule.estimated_quantity = body.estimated_quantity
    if body.actual_quantity is not None:
        schedule.actual_quantity = body.actual_quantity
    if body.status is not None:
        schedule.status = body.status

    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("/forecast/{product_id}")
def get_demand_forecast(product_id: int, db: Session = Depends(get_db)):
    """Get demand forecast for a product based on moving average."""
    return forecast_demand(db, product_id)
