from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class ChatQuestion(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    question: str
    user_id: Optional[int] = None


class ChatAnswer(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    answer: str
    intent: str
    escalated: bool = False


class ChatLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    user_id: Optional[int] = None
    intent: str
    question: str
    answer: str
    escalated: bool
    rating: Optional[int] = None
    created_at: Optional[datetime] = None


class ChatRating(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    rating: int
