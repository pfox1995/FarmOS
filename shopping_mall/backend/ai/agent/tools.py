"""에이전트 도구 정의 (중립 형식).

각 클라이언트가 자신의 형식으로 변환합니다.
- OpenAIAgentClient: {"type":"function","function":{...}}
- ClaudeAgentClient: {"name":..., "description":..., "input_schema":{...}}

도구 추가 방법:
1. TOOL_DEFINITIONS에 항목 추가
2. TOOL_TO_INTENT에 매핑 추가
3. executor.py의 _dispatch_tool + _tool_*() 메서드 구현
"""

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "search_faq",
        "description": (
            "FAQ에서 운영 관련 질문의 답변을 검색합니다. "
            "배송 기간, 결제 수단, 적립금 사용, 묶음 배송, 재입고 알림 등 "
            "일반적인 운영 절차 관련 질문에 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색할 질문 내용 (예: '배송 얼마나 걸려요?')",
                },
                "top_k": {
                    "type": "integer",
                    "description": "반환할 결과 수 (기본값: 3)",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_storage_guide",
        "description": (
            "농산물별 보관 방법 가이드를 검색합니다. "
            "냉장/냉동 방법, 유통기한, 보관 주의사항 관련 질문에 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "보관법을 알고 싶은 상품명 (예: '딸기', '소고기', '사과')",
                },
                "query": {
                    "type": "string",
                    "description": "보관 관련 질문 전문",
                },
            },
            "required": ["product_name", "query"],
        },
    },
    {
        "name": "search_season_info",
        "description": (
            "제철 농산물 정보와 수확 시기를 검색합니다. "
            "'지금 제철이 뭐야?', '딸기 언제 나와?' 같은 질문에 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "제철/계절 관련 질문",
                },
                "season": {
                    "type": "string",
                    "enum": ["봄", "여름", "가을", "겨울", "연중"],
                    "description": "특정 계절 필터 (선택 사항)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_policy",
        "description": (
            "운영 정책 문서에서 관련 내용을 검색합니다. "
            "반품·교환·환불, 결제·적립금, 회원 등급, 배송 정책, "
            "상품 품질 보증, 고객 서비스 운영 규정 등에 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "정책 관련 질문",
                },
                "policy_type": {
                    "type": "string",
                    "enum": [
                        "return",       # 반품·교환·환불 정책
                        "payment",      # 주문·결제·적립금 정책
                        "membership",   # 개인정보·회원 정책
                        "delivery",     # 배송 정책
                        "quality",      # 상품 품질·신선도 보증 정책
                        "service",      # 고객 서비스 운영 정책
                        "all",          # 전체 정책 검색
                    ],
                    "description": "정책 종류 필터 (기본: all)",
                    "default": "all",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_order_status",
        "description": (
            "사용자의 주문 및 배송 현황을 실시간으로 조회합니다. "
            "배송 조회, 송장번호, 도착 예정일 관련 질문에 사용하세요. "
            "반드시 로그인한 사용자(user_id 있음)에게만 사용하세요. "
            "도착 예정일은 주말·공휴일을 자동으로 제외한 실제 영업일 기준으로 계산됩니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "특정 주문 ID (없으면 최근 3건 조회)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_products",
        "description": (
            "상품을 이름이나 카테고리로 검색하고 재고 상태를 확인합니다. "
            "'딸기 있어요?', '과일 뭐 있어?', '재고 있는 상품만 보여줘' 등에 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색할 상품명 또는 카테고리 (예: '딸기', '과일')",
                },
                "check_stock": {
                    "type": "boolean",
                    "description": "true 시 재고 있는 상품만 반환 (기본: false)",
                    "default": False,
                },
                "limit": {
                    "type": "integer",
                    "description": "반환할 최대 상품 수 (기본: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_product_detail",
        "description": (
            "특정 상품의 상세 정보(가격, 재고, 설명, 평점 등)를 조회합니다. "
            "search_products로 상품을 찾은 후 상세 정보가 필요할 때 사용하세요. "
            "product_id 또는 product_name 중 반드시 하나 이상을 제공해야 합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "상품 ID (search_products 결과에서 얻음)",
                },
                "product_name": {
                    "type": "string",
                    "description": "상품명으로 검색 (product_id가 없을 때 사용)",
                },
            },
        },
    },
    {
        "name": "search_farm_info",
        "description": (
            "FarmOS 플랫폼 소개, 농장 정보, 유기농/친환경 인증 기준을 검색합니다. "
            "'FarmOS가 어떤 서비스예요?', '유기농 인증 믿을 수 있어요?' 등에 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "농장, 원산지, 플랫폼, 인증 관련 질문",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "create_exchange_request",
        "description": (
            "교환 신청을 접수합니다. 단, 즉시 처리하지 않고 사용자 확인을 요청합니다. "
            "사용자가 교환을 요청하면 이 도구를 먼저 호출하여 접수 내용을 보여주고, "
            "사용자가 '확인' 또는 '신청'이라고 답하면 confirm_pending_action을 호출하세요. "
            "반드시 로그인한 사용자(user_id 있음)에게만 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "교환할 주문 ID",
                },
                "reason": {
                    "type": "string",
                    "description": "교환 사유 (예: '상품 불량', '오배송', '단순 변심')",
                },
                "order_item_id": {
                    "type": "integer",
                    "description": "교환할 특정 상품 항목 ID (주문 내 특정 상품만 교환 시)",
                },
            },
            "required": ["order_id", "reason"],
        },
    },
    {
        "name": "confirm_pending_action",
        "description": (
            "대기 중인 액션(교환 신청 등)을 사용자가 확인하여 최종 실행합니다. "
            "create_exchange_request 호출 후 사용자가 '확인', '네', '신청해줘' 등으로 동의했을 때 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "cancel_pending_action",
        "description": (
            "대기 중인 액션(교환 신청 등)을 취소합니다. "
            "create_exchange_request 호출 후 사용자가 '취소', '아니요', '안 할게요' 등으로 거부했을 때 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "escalate_to_agent",
        "description": (
            "챗봇이 처리할 수 없는 케이스를 상담원에게 연결합니다. "
            "다른 도구로 해결할 수 없는 복잡한 민원, 고객이 직접 상담원을 요청할 때, "
            "거래 취소/변경 등 실제 처리 권한이 필요할 때 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "에스컬레이션 사유 (로그 기록용)",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["normal", "high"],
                    "description": "긴급도. high 시 우선 처리 안내 (기본: normal)",
                    "default": "normal",
                },
            },
            "required": ["reason"],
        },
    },
]

# 사용된 첫 번째 도구를 기존 ChatLog.intent 형식으로 역산
TOOL_TO_INTENT: dict[str, str] = {
    "get_order_status": "delivery",
    "search_products": "stock",
    "get_product_detail": "stock",
    "search_storage_guide": "storage",
    "search_season_info": "season",
    "search_policy": "policy",
    "search_faq": "other",
    "search_farm_info": "other",
    "create_exchange_request": "exchange",
    "confirm_pending_action": "exchange",
    "cancel_pending_action": "exchange",
    "escalate_to_agent": "escalation",
}
