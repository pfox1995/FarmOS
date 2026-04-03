"""Shipment tracking router."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.shipment import Shipment
from app.schemas.shipment import ShipmentCreate, ShipmentResponse
from app.services.shipping_tracker import ShippingTracker

router = APIRouter(prefix="/api/shipments", tags=["shipments"])


@router.post("/", response_model=ShipmentResponse)
def create_shipment(body: ShipmentCreate, db: Session = Depends(get_db)):
    shipment = Shipment(
        order_id=body.order_id,
        carrier=body.carrier,
        tracking_number=body.tracking_number,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    return shipment


@router.get("/", response_model=List[ShipmentResponse])
def list_shipments(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    query = db.query(Shipment)
    if status:
        query = query.filter(Shipment.status == status)
    return query.order_by(Shipment.created_at.desc()).all()


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(shipment_id: int, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment


@router.post("/{shipment_id}/check", response_model=ShipmentResponse)
def check_shipment_status(shipment_id: int, db: Session = Depends(get_db)):
    """Manually trigger a status check for a shipment."""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    ShippingTracker.update_shipment(shipment)
    db.commit()
    db.refresh(shipment)
    return shipment
