from sqlalchemy import Column, Integer, String, Text, UniqueConstraint
from app.core.database import Base

class NcpmsDiagnosis(Base):
    __tablename__ = "ncpms_diagnoses"

    id = Column(Integer, primary_key=True)
    pest_name = Column(String(100), nullable=False)
    crop_name = Column(String(100), index=True, nullable=False)
    
    ecology_info = Column(Text, nullable=True)
    biology_prvnbe_mth = Column(Text, nullable=True)
    prevent_method = Column(Text, nullable=True)
    chemical_prvnbe_mth = Column(Text, nullable=True)
    
    # 챗봇(LLM)에게 바로 던져주기 위해 미리 완성해둔 마크다운 문자열
    # (예: ### 생태 환경\n\n... \n\n### 재배 및 물리적 방제\n\n...)
    formatted_markdown = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint('pest_name', 'crop_name', name='uq_pest_crop_name'),
    )
