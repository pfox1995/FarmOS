from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class WeeklyReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    week_start: str
    week_end: str
    total_revenue: int
    total_expense: int
    net_profit: int
    report_content: Optional[str] = None
    generated_at: Optional[datetime] = None


class GenerateReportRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    week_start: str
    week_end: str
