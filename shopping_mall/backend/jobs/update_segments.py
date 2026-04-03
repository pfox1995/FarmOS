"""Job: Update customer segments using RFM analysis."""
import logging
from app.database import SessionLocal
from app.services.rfm_analyzer import RFMAnalyzer

logger = logging.getLogger(__name__)


def run():
    """Recalculate all customer segments."""
    db = SessionLocal()
    try:
        count = RFMAnalyzer.analyze_all(db)
        logger.info(f"Customer segments updated: {count} users processed.")
    except Exception as e:
        logger.error(f"Segment update failed: {e}")
        db.rollback()
    finally:
        db.close()
