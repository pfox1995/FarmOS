"""AI-powered expense classifier with keyword fallback."""
import logging
from sqlalchemy.orm import Session

from app.models.expense import ExpenseEntry

logger = logging.getLogger(__name__)


KEYWORD_RULES = {
    "packaging": ["포장", "박스", "완충재", "아이스팩", "보냉", "스티로폼", "테이프", "봉투"],
    "shipping": ["택배", "배송", "운송", "퀵", "우체국", "CJ", "한진", "로젠", "배달"],
    "material": ["원재료", "종자", "비료", "농약", "사료", "모종", "퇴비", "씨앗", "원물"],
    "labor": ["인건비", "일용직", "아르바이트", "급여", "알바", "수당", "노임", "인력"],
    "utility": ["전기", "수도", "가스", "통신", "인터넷", "전화", "공과금", "관리비"],
    "marketing": ["광고", "홍보", "이벤트", "쿠폰", "프로모션", "SNS", "블로그", "마케팅"],
}


class ExpenseClassifier:
    """Classify expense descriptions into categories."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def classify(self, description: str) -> str:
        """Classify a single expense description."""
        if self.llm:
            try:
                return await self.llm.classify_expense(description)
            except Exception as e:
                logger.warning(f"LLM expense classification failed: {e}")

        return self._keyword_classify(description)

    def _keyword_classify(self, description: str) -> str:
        """Fallback keyword-based classification."""
        desc_lower = description.lower()
        for category, keywords in KEYWORD_RULES.items():
            if any(kw in desc_lower for kw in keywords):
                return category
        return "other"

    async def classify_all_unclassified(self, db: Session) -> int:
        """Classify all expense entries that don't have a category. Returns count."""
        entries = (
            db.query(ExpenseEntry)
            .filter(
                (ExpenseEntry.category.is_(None)) | (ExpenseEntry.category == "")
            )
            .all()
        )
        count = 0
        for entry in entries:
            category = await self.classify(entry.description)
            entry.category = category
            entry.auto_classified = True
            count += 1

        if count > 0:
            db.commit()
        return count
