"""농약 등록정보 캐시 모델 — 식품안전나라 API 전체 데이터 로컬 저장."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PesticideProduct(Base):
    """농약 등록정보 (식품안전나라 I1910 API 캐시, 전체 저장)."""

    __tablename__ = "pesticide_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 제품 정보
    product_name: Mapped[str] = mapped_column(
        String(200), index=True, comment="제품명 (PRDLST_KOR_NM)"
    )
    brand_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True, comment="브랜드명 (BRND_NM)"
    )
    company: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="제조사 (CPR_NM)"
    )
    purpose: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="용도: 살충제, 살균제 등 (PRPOS_DVS_CD_NM)"
    )
    form_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="제형: 수화제, 입상수화제 등 (MDC_SHAP_NM)"
    )

    # 작물/병해충 정보
    crop_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True, comment="대상 작물 (CROPS_NM)"
    )
    disease_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="병해충/잡초명 (SICKNS_HLSCT_NM_WEEDS_NM)"
    )

    # 사용 방법
    dilution: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="희석배수 (DILU_DRNG)"
    )
    usage_method: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="사용방법 (AGCHM_USE_MTHD)"
    )
    usage_period: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="사용적기 (USE_PPRTM)"
    )
    usage_count: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="사용횟수 (USE_TMNO)"
    )

    # 안전 정보
    toxicity: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="독성 (PERSN_LVSTCK_TOXCTY)"
    )

    # 동기화 메타데이터
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
