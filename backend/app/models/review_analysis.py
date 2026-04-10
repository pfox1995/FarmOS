"""리뷰 분석 SQLAlchemy 모델.

# Design Ref: §5.2 — SQLAlchemy Models
"""

from sqlalchemy import Column, Float, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base


class ReviewAnalysis(Base):
    """분석 실행 기록 테이블."""

    __tablename__ = "review_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_type = Column(String(20), nullable=False)   # "manual" | "batch"
    target_scope = Column(String(50), default="all")     # "all" | "product:{id}" | "platform:{name}"
    review_count = Column(Integer, default=0)
    sentiment_summary = Column(JSONB, nullable=True)     # { positive, negative, neutral, total }
    keywords = Column(JSONB, nullable=True)              # [{ word, count, sentiment }]
    summary = Column(Text, nullable=True)                # LLM 생성 요약 (JSON 문자열)
    trends = Column(JSONB, nullable=True)
    anomalies = Column(JSONB, nullable=True)
    llm_provider = Column(String(30), nullable=True)
    llm_model = Column(String(50), nullable=True)
    processing_time_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReviewSentiment(Base):
    """개별 리뷰 감성 분석 캐시 테이블."""

    __tablename__ = "review_sentiments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(String(50), nullable=False)       # ChromaDB 리뷰 ID
    sentiment = Column(String(10), nullable=False)       # positive | negative | neutral
    score = Column(Float, default=0.0)                   # -1.0 ~ 1.0
    reason = Column(Text, nullable=True)
    keywords = Column(JSONB, nullable=True)              # 추출된 키워드 배열
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
