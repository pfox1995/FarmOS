"""농약 검색/매칭용 모델 (`rag_pesticide_documents`)."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PesticideProduct(Base):
    """`rag_pesticide_documents` 읽기 모델."""

    __tablename__ = "rag_pesticide_documents"

    application_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_timing: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    corporation_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    crop_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dilution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    formulation_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_livestock_toxicity: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingredient_or_formulation_name: Mapped[str | None] = mapped_column(
        Text, nullable=True, index=True
    )
    max_use_count_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    target_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    usage_purpose_name: Mapped[str | None] = mapped_column(Text, nullable=True)
