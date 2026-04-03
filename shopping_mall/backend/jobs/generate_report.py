"""Job: Generate weekly report."""
import asyncio
import logging
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.services.ai_report import ReportService
from ai.llm_client import LLMClient

logger = logging.getLogger(__name__)


def run():
    """Generate the weekly report for the previous week."""
    db = SessionLocal()
    try:
        today = datetime.utcnow().date()
        # Previous week: Monday to Sunday
        week_end = today - timedelta(days=today.weekday())  # This Monday
        week_start = week_end - timedelta(days=7)

        llm = LLMClient()
        service = ReportService(llm_client=llm)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(
                service.generate_weekly(
                    week_start=week_start.strftime("%Y-%m-%d"),
                    week_end=week_end.strftime("%Y-%m-%d"),
                    db=db,
                )
            )
            logger.info(f"Weekly report generated: id={report.id}")
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Weekly report generation failed: {e}")
        db.rollback()
    finally:
        db.close()
