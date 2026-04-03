"""Chatbot prompt templates."""

INTENT_CLASSIFY_PROMPT = """사용자 질문의 의도를 다음 중 하나로 분류하세요.

카테고리:
- delivery: 배송 현황, 배송 조회, 배송 관련 문의
- stock: 재고 확인, 품절 여부, 입고 예정
- storage: 보관 방법, 저장 방법, 유통기한
- season: 제철 정보, 수확 시기, 계절 과일/채소
- exchange: 교환, 환불, 반품, 클레임
- other: 위 카테고리에 해당하지 않는 기타 문의

질문: {question}

영어 카테고리명 한 단어만 답하세요:"""

ANSWER_PROMPT = """당신은 농산물 직거래 쇼핑몰의 고객 지원 챗봇입니다.
친절하고 정확하게 한국어로 답변하세요.

{context}

고객 질문: {question}

답변:"""
