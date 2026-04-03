"""Reports, revenue, and expenses router."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.weekly_report import WeeklyReport
from app.models.revenue import RevenueEntry
from app.models.expense import ExpenseEntry
from app.schemas.report import WeeklyReportResponse, GenerateReportRequest
from app.schemas.revenue import RevenueResponse
from app.schemas.expense import ExpenseCreate, ExpenseResponse
from app.services.ai_report import ReportService
from app.services.ai_classifier import ExpenseClassifier
from ai.llm_client import LLMClient

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _get_llm():
    return LLMClient()


@router.get("/weekly", response_model=List[WeeklyReportResponse])
def list_weekly_reports(db: Session = Depends(get_db)):
    return db.query(WeeklyReport).order_by(WeeklyReport.generated_at.desc()).all()


@router.get("/weekly/{report_id}", response_model=WeeklyReportResponse)
def get_weekly_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(WeeklyReport).filter(WeeklyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.post("/weekly/generate", response_model=WeeklyReportResponse)
async def generate_weekly_report(body: GenerateReportRequest, db: Session = Depends(get_db)):
    """Trigger weekly report generation."""
    service = ReportService(llm_client=_get_llm())
    report = await service.generate_weekly(body.week_start, body.week_end, db)
    return report


@router.get("/revenue", response_model=List[RevenueResponse])
def list_revenue(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(RevenueEntry)
    if start_date:
        query = query.filter(RevenueEntry.date >= start_date)
    if end_date:
        query = query.filter(RevenueEntry.date <= end_date)
    return query.order_by(RevenueEntry.date.desc()).all()


@router.get("/expenses", response_model=List[ExpenseResponse])
def list_expenses(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(ExpenseEntry)
    if start_date:
        query = query.filter(ExpenseEntry.date >= start_date)
    if end_date:
        query = query.filter(ExpenseEntry.date <= end_date)
    return query.order_by(ExpenseEntry.date.desc()).all()


@router.post("/expenses", response_model=ExpenseResponse)
def create_expense(body: ExpenseCreate, db: Session = Depends(get_db)):
    entry = ExpenseEntry(
        date=body.date,
        description=body.description,
        amount=body.amount,
        category=body.category,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/expenses/classify")
async def classify_expenses(db: Session = Depends(get_db)):
    """AI-classify all unclassified expense entries."""
    classifier = ExpenseClassifier(llm_client=_get_llm())
    count = await classifier.classify_all_unclassified(db)
    return {"classified_count": count}
