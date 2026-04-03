"""Expense classification prompt templates."""

EXPENSE_CLASSIFY_PROMPT = """다음 비용 항목의 설명을 읽고, 아래 카테고리 중 하나로 분류하세요.

카테고리:
- packaging: 포장재, 박스, 완충재, 아이스팩 등 포장 관련
- shipping: 택배비, 배송비, 운송비 등 배송 관련
- material: 원재료, 종자, 비료, 농약 등 생산 재료
- labor: 인건비, 일용직, 아르바이트 등 노동 관련
- utility: 전기, 수도, 가스, 통신 등 공과금
- marketing: 광고, 홍보, 이벤트, 쿠폰 등 마케팅
- other: 위 카테고리에 해당하지 않는 기타 비용

비용 설명: {description}

영어 카테고리명 한 단어만 답하세요:"""
