"""공통 픽스처."""
import copy
from unittest.mock import MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

import pytest

from ai.agent import AgentClient, AgentResponse, AgentUnavailableError, ToolCall, TOOL_DEFINITIONS


# ── 테스트용 AgentClient 구현 ────────────────────────────────────────────────

class FakeAgentClient(AgentClient):
    """시나리오 기반 AgentClient 스텁.

    responses 리스트를 순서대로 반환하며, AgentUnavailableError를 포함시키면
    해당 호출에서 예외를 발생시킵니다.
    """

    def __init__(self, responses: list):
        self._responses = iter(responses)
        self.calls: list[list[dict]] = []  # chat_with_tools 호출당 messages 스냅샷

    async def chat_with_tools(
        self, messages: list[dict], tools: list[dict], system: str
    ) -> AgentResponse:
        self.calls.append(list(messages))
        resp = next(self._responses)
        if isinstance(resp, AgentUnavailableError):
            raise resp
        return resp

    def add_tool_results(
        self,
        messages: list[dict],
        response: AgentResponse,
        results: list[tuple[ToolCall, str]],
    ) -> None:
        """테스트용 단순 포맷 (Ollama 스타일)."""
        messages.append({"role": "assistant", "content": response.text or ""})
        for _, result in results:
            messages.append({"role": "tool", "content": result})

    async def is_available(self) -> bool:
        return True


def make_text_response(text: str) -> AgentResponse:
    """도구 호출 없는 최종 텍스트 응답."""
    return AgentResponse(text=text, tool_calls=[])


def make_tool_response(*tool_calls: tuple[str, dict]) -> AgentResponse:
    """도구 호출 응답. (name, args) 튜플 가변 인자."""
    calls = [
        ToolCall(id=f"tc_{i}", name=name, arguments=args)
        for i, (name, args) in enumerate(tool_calls)
    ]
    return AgentResponse(text=None, tool_calls=calls)


# ── RAG 서비스 목 ─────────────────────────────────────────────────────────────

class FakeRAGService:
    """retrieve / retrieve_multiple 결과를 제어 가능한 RAG 스텁."""

    def __init__(self, results: dict[str, list[str]] | None = None):
        # collection → 반환할 문서 리스트. 없으면 빈 리스트.
        self._results: dict[str, list[str]] = results or {}

    def retrieve(
        self,
        question: str,
        collection: str,
        top_k: int = 3,
        distance_threshold: float = 0.5,
        where: dict | None = None,
    ) -> list[str]:
        return self._results.get(collection, [])[:top_k]

    def retrieve_multiple(
        self,
        question: str,
        collections: list[str],
        top_k_per: int = 2,
        distance_threshold: float = 0.5,
    ) -> list[str]:
        docs = []
        seen = set()
        for col in collections:
            for doc in self._results.get(col, [])[:top_k_per]:
                if doc not in seen:
                    seen.add(doc)
                    docs.append(doc)
        return docs


# ── DB 세션 목 ────────────────────────────────────────────────────────────────

def make_mock_db(orders=None, shipments=None, products=None, chat_session=None):
    """SQLAlchemy Session 체인 목.

    db.query(Model) 호출 시 모델 클래스별로 다른 목을 반환하여
    Order/Shipment/Product/ChatSession 쿼리가 서로 덮어쓰지 않도록 분리합니다.
    """
    from app.models.order import Order
    from app.models.shipment import Shipment
    from app.models.product import Product
    from app.models.chat_session import ChatSession

    db = MagicMock()

    # 모델별 독립 목 체인 생성
    order_mock = MagicMock()
    shipment_mock = MagicMock()
    product_mock = MagicMock()
    chat_session_mock = MagicMock()

    def query_side_effect(model):
        if model is Order:
            return order_mock
        if model is Shipment:
            return shipment_mock
        if model is Product:
            return product_mock
        if model is ChatSession:
            return chat_session_mock
        return MagicMock()

    db.query.side_effect = query_side_effect

    # ── Order 체인 ─────────────────────────────────────────────────
    # filter().order_by().limit().all() → orders (최근 3건)
    order_mock.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
        orders or []
    )
    # filter().filter().order_by().limit().all() → orders (order_id 추가 필터)
    order_mock.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
        orders or []
    )
    # filter().all() → orders (단순 조회)
    order_mock.filter.return_value.all.return_value = orders or []

    # ── Shipment 체인 ──────────────────────────────────────────────
    # filter().first() → 첫 번째 shipment
    shipment_obj = (shipments or [None])[0]
    shipment_mock.filter.return_value.first.return_value = shipment_obj

    # ── Product 체인 ──────────────────────────────────────────────
    # filter().order_by().limit().all() → products
    product_mock.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
        products or []
    )
    # filter().limit().all() → products
    product_mock.filter.return_value.limit.return_value.all.return_value = products or []

    # ── ChatSession 체인 ───────────────────────────────────────────
    # filter().first() → chat_session
    chat_session_mock.filter.return_value.first.return_value = chat_session

    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    return db


# ── 도메인 오브젝트 팩토리 ───────────────────────────────────────────────────

def make_order(
    order_id=1,
    user_id=10,
    total_price=35000,
    status="shipping",
    created_at=None,
    items=None,
):
    order = MagicMock()
    order.id = order_id
    order.user_id = user_id
    order.total_price = total_price
    order.status = status
    order.created_at = created_at or datetime(2026, 4, 10, tzinfo=KST)
    order.shipping_address = "서울시 강남구"
    order.items = items or []
    return order


def make_shipment(
    order_id=1,
    carrier="CJ대한통운",
    tracking_number="1234567890",
    status="in_transit",
    expected_arrival=None,
):
    s = MagicMock()
    s.order_id = order_id
    s.carrier = carrier
    s.tracking_number = tracking_number
    s.status = status
    s.expected_arrival = expected_arrival or datetime(2026, 4, 12, tzinfo=KST)
    return s


def make_product(
    product_id=1,
    name="딸기",
    price=12000,
    discount_rate=0,
    stock=150,
    rating=4.5,
    review_count=32,
    sales_count=200,
    description="신선한 딸기",
):
    p = MagicMock()
    p.id = product_id
    p.name = name
    p.price = price
    p.discount_rate = discount_rate
    p.stock = stock
    p.rating = rating
    p.review_count = review_count
    p.sales_count = sales_count
    p.description = description
    p.restock_date = None
    return p


# ── 공통 픽스처 ──────────────────────────────────────────────────────────────

@pytest.fixture
def tools():
    return copy.deepcopy(TOOL_DEFINITIONS)


@pytest.fixture
def empty_rag():
    return FakeRAGService()


@pytest.fixture
def empty_db():
    return make_mock_db()
