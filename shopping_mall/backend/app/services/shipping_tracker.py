"""Simulated shipping status tracker."""
import json
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.shipment import Shipment


class ShippingTracker:
    """Simulate shipment status progression based on time since creation."""

    STATUS_FLOW = ["registered", "picked_up", "in_transit", "delivered"]

    @classmethod
    def check_status(cls, shipment: Shipment) -> str:
        """Simulate status progression based on days since creation."""
        if shipment.status == "delivered":
            return "delivered"

        now = datetime.utcnow()
        if shipment.created_at is None:
            return shipment.status

        days_elapsed = (now - shipment.created_at).total_seconds() / 86400

        if days_elapsed >= 3:
            new_status = "delivered"
        elif days_elapsed >= 2:
            new_status = "in_transit"
        elif days_elapsed >= 1:
            new_status = "picked_up"
        else:
            new_status = "registered"

        return new_status

    @classmethod
    def update_shipment(cls, shipment: Shipment) -> bool:
        """Update a single shipment. Returns True if status changed."""
        new_status = cls.check_status(shipment)
        if new_status == shipment.status:
            shipment.last_checked_at = datetime.utcnow()
            return False

        now = datetime.utcnow()
        old_status = shipment.status

        # Update tracking history
        history = []
        if shipment.tracking_history:
            try:
                history = json.loads(shipment.tracking_history)
            except (json.JSONDecodeError, TypeError):
                history = []

        history.append({
            "from": old_status,
            "to": new_status,
            "timestamp": now.isoformat(),
        })

        shipment.status = new_status
        shipment.tracking_history = json.dumps(history, ensure_ascii=False)
        shipment.last_checked_at = now

        if new_status == "delivered":
            shipment.delivered_at = now

        return True

    @classmethod
    def check_all(cls, db: Session) -> int:
        """Check and update all non-delivered shipments. Returns count of updated."""
        shipments = (
            db.query(Shipment)
            .filter(Shipment.status != "delivered")
            .all()
        )
        updated = 0
        for shipment in shipments:
            if cls.update_shipment(shipment):
                updated += 1

        if updated > 0:
            db.commit()
        return updated
