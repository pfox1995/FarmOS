"""Job: Check and update shipment statuses."""
import logging
from app.database import SessionLocal
from app.services.shipping_tracker import ShippingTracker

logger = logging.getLogger(__name__)


def run():
    """Check all non-delivered shipments and update their status."""
    db = SessionLocal()
    try:
        updated = ShippingTracker.check_all(db)
        logger.info(f"Shipment check completed: {updated} shipments updated.")
    except Exception as e:
        logger.error(f"Shipment check failed: {e}")
        db.rollback()
    finally:
        db.close()
