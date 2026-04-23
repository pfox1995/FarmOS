"""농약 검색/매칭용 모델."""

from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PesticideProduct(Base):
    """`rag_pesticide_documents` 읽기 모델 (RAG 검색용)."""

    __tablename__ = "rag_pesticide_documents"

    document_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # FK에 인덱스를 추가하여 조인 성능 최적화 (CoderrabitAI 리뷰 반영)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("rag_pesticide_product_applications.application_id"),
        nullable=False,
        index=True
    )
    
    crop_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    target_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    
    brand_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    corporation_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingredient_or_formulation_name: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    
    application_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_timing: Mapped[str | None] = mapped_column(Text, nullable=True)
    dilution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_use_count_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    formulation_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # N:1 관계 (여러 제품 문서가 하나의 등록 정보에 연결될 수 있음)
    details: Mapped["PesticideApplication"] = relationship(back_populates="document_entry")


class PesticideApplication(Base):
    """`rag_pesticide_product_applications` (실제 농약 등록 정보 원본)."""
    
    __tablename__ = "rag_pesticide_product_applications"

    application_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 1:N 관계 (하나의 등록 정보에 여러 RAG 문서가 매달릴 수 있음)
    document_entry: Mapped[list["PesticideProduct"]] = relationship(back_populates="details")
