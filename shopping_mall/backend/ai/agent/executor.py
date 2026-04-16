"""에이전트 실행기 — tool_use 루프 + 12개 도구 구현."""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings

from ai.agent.clients.base import AgentClient, AgentUnavailableError, ToolCall
from ai.agent.tools import TOOL_DEFINITIONS, TOOL_TO_INTENT

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10       # 하드코딩 폴백 (settings 미설정 시)
MAX_ANSWER_LENGTH = 1000  # 최종 응답 최대 글자 수


# ── 요청 컨텍스트 ──────────────────────────────────────────────────────────────

@dataclass
class RequestContext:
    """LLM에 주입할 요청 시점의 세션 상태."""
    user_id: int | None
    is_logged_in: bool
    current_date: str   # "2026-04-13"
    current_time: str   # "14:32"

    @classmethod
    def build(cls, user_id: int | None) -> "RequestContext":
        now = datetime.now(timezone.utc).astimezone()
        return cls(
            user_id=user_id,
            is_logged_in=user_id is not None,
            current_date=now.strftime("%Y-%m-%d"),
            current_time=now.strftime("%H:%M"),
        )

    def to_system_suffix(self) -> str:
        """시스템 프롬프트 끝에 붙일 컨텍스트 블록."""
        login_status = f"로그인 (user_id={self.user_id})" if self.is_logged_in else "비로그인"
        return (
            f"\n\n## 현재 요청 컨텍스트\n"
            f"- 날짜/시각: {self.current_date} {self.current_time}\n"
            f"- 사용자 상태: {login_status}\n"
            f"- 주문 조회 가능: {'예' if self.is_logged_in else '아니오 (로그인 필요)'}"
        )

# policy_type → ChromaDB 컬렉션명
POLICY_COLLECTIONS: dict[str, list[str]] = {
    "return":     ["return_policy"],
    "payment":    ["payment_policy"],
    "membership": ["membership_policy"],
    "delivery":   ["delivery_policy"],
    "quality":    ["quality_policy"],
    "service":    ["service_policy"],
    "all": [
        "return_policy", "payment_policy", "membership_policy",
        "delivery_policy", "quality_policy", "service_policy",
    ],
}


@dataclass
class TraceStep:
    """도구 호출 한 단계의 추론 기록."""
    tool: str
    arguments: dict
    result: str        # 도구 실행 결과 (최대 500자)
    iteration: int     # 루프 몇 번째 반복


@dataclass
class AgentResult:
    answer: str
    intent: str
    escalated: bool
    tools_used: list[str] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)


# ── 응답 후처리 ────────────────────────────────────────────────────────────────

def _parse_answer(raw: str) -> str:
    """LLM 응답 텍스트 후처리.

    - 마크다운 헤딩(#) 제거
    - 과도한 빈 줄 압축 (3줄 이상 → 2줄)
    - 최대 길이 초과 시 문장 단위로 자름
    """
    # 마크다운 헤딩 제거 (## 제목 → 제목)
    text = re.sub(r"^#{1,6}\s+", "", raw, flags=re.MULTILINE)
    # 3줄 이상 연속 빈 줄 → 2줄
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) <= MAX_ANSWER_LENGTH:
        return text

    # 문장 단위 자르기 (마침표/느낌표/물음표 기준)
    truncated = text[:MAX_ANSWER_LENGTH]
    last_sentence_end = max(
        truncated.rfind("다."),
        truncated.rfind("요."),
        truncated.rfind("!"),
        truncated.rfind("?"),
    )
    if last_sentence_end > MAX_ANSWER_LENGTH // 2:
        truncated = truncated[: last_sentence_end + 1]

    return truncated + "\n\n(이어지는 내용은 상담원에게 문의해 주세요.)"


def _log_trace(trace: "list[TraceStep]", question: str) -> None:
    """추론 과정을 INFO 레벨로 출력."""
    if not trace:
        logger.info(f"[trace] 질문='{question[:60]}' → 도구 호출 없음 (직접 답변)")
        return
    logger.info(f"[trace] 질문='{question[:60]}' → {len(trace)}단계 도구 호출")
    for step in trace:
        logger.info(f"  [{step.iteration}] {step.tool}({step.arguments})")


class AgentExecutor:
    """Primary → Fallback tool_use 루프 실행기."""

    def __init__(
        self,
        primary: AgentClient,
        fallback: AgentClient | None,
        rag_service,
        tools: list[dict] | None = None,
        max_iterations: int | None = None,
    ):
        self.primary = primary
        self.fallback = fallback
        self.rag = rag_service
        self.tools = tools or TOOL_DEFINITIONS
        self.max_iterations = max_iterations or settings.agent_max_iterations or MAX_ITERATIONS

    # ── 진입점 ────────────────────────────────────────────────────────────

    async def run(
        self,
        db: Session,
        user_message: str,
        user_id: int | None,
        history: list[dict],
        system: str,
        session_id: int | None = None,
        context: RequestContext | None = None,
    ) -> AgentResult:
        """에이전트 루프 실행. Primary 실패 시 Fallback으로 전환."""
        ctx = context or RequestContext.build(user_id)
        system_with_ctx = system + ctx.to_system_suffix()

        try:
            return await self._run_loop(
                self.primary, db, user_message, user_id, session_id, history, system_with_ctx
            )
        except AgentUnavailableError as e:
            logger.warning(f"Primary LLM 실패: {e}. Fallback 시도.")
            if self.fallback:
                try:
                    return await self._run_loop(
                        self.fallback, db, user_message, user_id, session_id, history, system_with_ctx
                    )
                except AgentUnavailableError as e2:
                    logger.error(f"Fallback LLM도 실패: {e2}")
            return AgentResult(
                answer="죄송합니다. 현재 서비스에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도하거나 고객센터(1588-0000)로 문의해 주세요.",
                intent="escalation",
                escalated=True,
            )

    # ── 루프 ──────────────────────────────────────────────────────────────

    async def _run_loop(
        self,
        client: AgentClient,
        db: Session,
        user_message: str,
        user_id: int | None,
        session_id: int | None,
        history: list[dict],
        system: str,
    ) -> AgentResult:
        messages = list(history) + [{"role": "user", "content": user_message}]
        tools_used: list[str] = []
        trace: list[TraceStep] = []
        escalated = False

        for iteration in range(self.max_iterations):
            response = await client.chat_with_tools(messages, self.tools, system)

            # 도구 호출 없음 → 최종 답변
            if not response.tool_calls:
                raw_answer = response.text or "죄송합니다. 답변을 생성하지 못했습니다."
                answer = _parse_answer(raw_answer)
                intent = TOOL_TO_INTENT.get(tools_used[0], "other") if tools_used else "other"
                _log_trace(trace, user_message)
                return AgentResult(
                    answer=answer,
                    intent=intent,
                    escalated=escalated,
                    tools_used=tools_used,
                    trace=trace,
                )

            # 도구 실행
            results: list[tuple[ToolCall, str]] = []
            for tc in response.tool_calls:
                tools_used.append(tc.name)
                if tc.name == "escalate_to_agent":
                    escalated = True
                result = await self._dispatch_tool(tc, db, user_id, session_id)
                results.append((tc, result))
                trace.append(TraceStep(
                    tool=tc.name,
                    arguments=tc.arguments,
                    result=result[:500],
                    iteration=iteration + 1,
                ))
                logger.info(f"[trace] iter={iteration+1} tool={tc.name} args={tc.arguments} → {result[:120]}")

            client.add_tool_results(messages, response, results)

        # 최대 반복 초과 → 에스컬레이션
        logger.warning("에이전트 최대 반복 초과. 에스컬레이션.")
        _log_trace(trace, user_message)
        return AgentResult(
            answer="요청을 처리하는 데 시간이 걸리고 있습니다. 상담원에게 연결해 드리겠습니다.",
            intent=TOOL_TO_INTENT.get(tools_used[0], "other") if tools_used else "escalation",
            escalated=True,
            tools_used=tools_used,
            trace=trace,
        )

    # ── 도구 디스패치 ─────────────────────────────────────────────────────

    async def _dispatch_tool(
        self, tc: ToolCall, db: Session, user_id: int | None, session_id: int | None = None
    ) -> str:
        args = tc.arguments
        try:
            match tc.name:
                case "search_faq":
                    return await self._tool_search_faq(**args)
                case "search_storage_guide":
                    return await self._tool_search_storage_guide(**args)
                case "search_season_info":
                    return await self._tool_search_season_info(**args)
                case "search_policy":
                    return await self._tool_search_policy(**args)
                case "get_order_status":
                    args.pop("user_id", None)  # 서버 세션의 user_id를 신뢰, LLM 값 무시
                    return await self._tool_get_order_status(db, user_id, **args)
                case "search_products":
                    return await self._tool_search_products(db, **args)
                case "get_product_detail":
                    return await self._tool_get_product_detail(db, **args)
                case "search_farm_info":
                    return await self._tool_search_farm_info(**args)
                case "create_exchange_request":
                    args.pop("user_id", None)
                    return await self._tool_create_exchange_request(db, user_id, session_id, **args)
                case "confirm_pending_action":
                    return await self._tool_confirm_pending_action(db, user_id, session_id)
                case "cancel_pending_action":
                    return await self._tool_cancel_pending_action(db, user_id, session_id)
                case "escalate_to_agent":
                    return self._tool_escalate_to_agent(**args)
                case _:
                    return f"[오류] 알 수 없는 도구: {tc.name}"
        except Exception as e:
            logger.error(f"도구 실행 오류 ({tc.name}): {e}")
            return f"[오류] {tc.name} 실행 중 문제가 발생했습니다."

    # ── 도구 구현 ─────────────────────────────────────────────────────────

    async def _tool_search_faq(self, query: str, top_k: int = 3) -> str:
        docs = self.rag.retrieve(query, "faq", top_k=top_k, distance_threshold=0.45)
        if not docs:
            return "FAQ에서 관련 내용을 찾을 수 없습니다."
        return "\n\n".join(docs)

    async def _tool_search_storage_guide(self, product_name: str, query: str) -> str:
        docs = self.rag.retrieve(
            query, "storage_guide", top_k=3, distance_threshold=0.40,
            where={"product_name": product_name} if product_name else None,
        )
        if not docs:
            # 메타데이터 필터 없이 재시도
            docs = self.rag.retrieve(query, "storage_guide", top_k=3, distance_threshold=0.45)
        if not docs:
            return f"'{product_name}' 보관법 정보를 찾을 수 없습니다."
        return "\n\n".join(docs)

    async def _tool_search_season_info(self, query: str, season: str | None = None) -> str:
        where = {"season": season} if season else None
        docs = self.rag.retrieve(query, "season_info", top_k=3, distance_threshold=0.45, where=where)
        if not docs:
            return "제철 정보를 찾을 수 없습니다."
        return "\n\n".join(docs)

    async def _tool_search_policy(self, query: str, policy_type: str = "all") -> str:
        collections = POLICY_COLLECTIONS.get(policy_type, POLICY_COLLECTIONS["all"])
        docs = self.rag.retrieve_multiple(query, collections, top_k_per=2, distance_threshold=0.50)
        if not docs:
            return "관련 정책 정보를 찾을 수 없습니다."
        return "\n\n".join(docs)

    async def _tool_get_order_status(
        self, db: Session, user_id: int | None, order_id: int | None = None, **_
    ) -> str:
        if not user_id:
            return "주문 조회는 로그인이 필요합니다."

        from app.models.order import Order
        from app.models.shipment import Shipment

        try:
            query = db.query(Order).filter(Order.user_id == user_id)
            if order_id:
                query = query.filter(Order.id == order_id)
            else:
                query = query.order_by(Order.created_at.desc()).limit(3)

            orders = query.all()
            if not orders:
                return "조회된 주문이 없습니다."

            parts = []
            for order in orders:
                shipment = db.query(Shipment).filter(Shipment.order_id == order.id).first()
                items_summary = ", ".join(
                    f"{item.product.name} x{item.quantity}"
                    for item in order.items
                    if item.product
                )
                part = (
                    f"주문번호: #{order.id}\n"
                    f"주문일: {order.created_at.strftime('%Y-%m-%d')}\n"
                    f"상품: {items_summary or '정보 없음'}\n"
                    f"금액: {order.total_price:,}원\n"
                    f"주문상태: {order.status}"
                )
                if shipment:
                    part += (
                        f"\n택배사: {shipment.carrier}"
                        f"\n송장번호: {shipment.tracking_number}"
                        f"\n배송상태: {shipment.status}"
                    )
                    if shipment.expected_arrival:
                        arrival = await self._adjust_arrival_date(shipment.expected_arrival)
                        part += arrival
                else:
                    part += "\n배송정보: 아직 등록되지 않았습니다"
                parts.append(part)

            return "\n\n---\n\n".join(parts)

        except Exception as e:
            logger.error(f"주문 조회 오류: {e}")
            return "주문 조회 중 오류가 발생했습니다."

    async def _adjust_arrival_date(self, raw_arrival: datetime) -> str:
        """expected_arrival을 공휴일/주말 기준으로 조정하여 문자열로 반환.

        공공데이터포털 API 키가 없으면 원본 날짜를 그대로 반환합니다.
        """
        api_key = settings.anniversary_api_key
        arrival_date = raw_arrival.date() if isinstance(raw_arrival, datetime) else raw_arrival

        if not api_key:
            return f"\n도착예정: {arrival_date.strftime('%Y-%m-%d')}"

        try:
            from ai.agent.holiday import next_business_day
            adjusted, skipped = await next_business_day(arrival_date, api_key)

            if not skipped:
                return f"\n도착예정: {adjusted.strftime('%Y-%m-%d')} ({adjusted.strftime('%A')})"

            skip_summary = ", ".join(skipped)
            return (
                f"\n도착예정: {adjusted.strftime('%Y-%m-%d')} "
                f"(원래 {arrival_date.strftime('%Y-%m-%d')}이었으나 {skip_summary} 제외하여 조정)"
            )
        except Exception as e:
            logger.warning(f"영업일 조정 실패: {e}")
            return f"\n도착예정: {arrival_date.strftime('%Y-%m-%d')}"

    async def _tool_search_products(
        self, db: Session, query: str, check_stock: bool = False, limit: int = 5
    ) -> str:
        limit = max(1, min(limit, 20))  # LLM이 넘긴 limit을 1~20 범위로 제한
        from app.models.product import Product

        try:
            q = db.query(Product).filter(Product.name.ilike(f"%{query}%"))
            if check_stock:
                q = q.filter(Product.stock > 0)
            products = q.order_by(Product.sales_count.desc()).limit(limit).all()

            if not products:
                return f"'{query}' 검색 결과가 없습니다."

            lines = []
            for p in products:
                discounted = int(p.price * (1 - p.discount_rate / 100)) if p.discount_rate else p.price
                stock_info = f"재고 {p.stock}개" if p.stock > 0 else "품절"
                line = f"- [{p.id}] {p.name} / {discounted:,}원"
                if p.discount_rate:
                    line += f" (할인율 {p.discount_rate}%)"
                line += f" / {stock_info} / 평점 {p.rating:.1f}"
                lines.append(line)

            return f"'{query}' 검색 결과 ({len(products)}건):\n" + "\n".join(lines)

        except Exception as e:
            logger.error(f"상품 검색 오류: {e}")
            return "상품 검색 중 오류가 발생했습니다."

    async def _tool_get_product_detail(
        self, db: Session, product_id: int | None = None, product_name: str | None = None
    ) -> str:
        from app.models.product import Product

        try:
            if product_id:
                product = db.query(Product).filter(Product.id == product_id).first()
            elif product_name:
                product = db.query(Product).filter(
                    Product.name.ilike(f"%{product_name}%")
                ).first()
            else:
                return "상품 ID 또는 상품명을 입력해 주세요."

            if not product:
                return "해당 상품을 찾을 수 없습니다."

            discounted = int(product.price * (1 - product.discount_rate / 100)) if product.discount_rate else product.price
            stock_status = f"{product.stock}개 재고" if product.stock > 0 else "품절"
            if product.stock == 0 and product.restock_date:
                stock_status += f" (입고 예정: {product.restock_date.strftime('%Y-%m-%d')})"

            return (
                f"상품명: {product.name}\n"
                f"가격: {discounted:,}원"
                + (f" (정가 {product.price:,}원, {product.discount_rate}% 할인)" if product.discount_rate else "") + "\n"
                f"재고: {stock_status}\n"
                f"평점: {product.rating:.1f}점 ({product.review_count}개 리뷰)\n"
                f"누적 판매: {product.sales_count}건\n"
                + (f"설명: {product.description}\n" if product.description else "")
            )

        except Exception as e:
            logger.error(f"상품 상세 조회 오류: {e}")
            return "상품 정보 조회 중 오류가 발생했습니다."

    async def _tool_search_farm_info(self, query: str) -> str:
        docs = self.rag.retrieve(query, "farm_intro", top_k=3, distance_threshold=0.50)
        if not docs:
            return (
                "FarmOS는 검증된 농장의 신선 농산물을 산지 직송으로 연결하는 플랫폼입니다. "
                "유기농·친환경 인증 상품을 중심으로 엄선된 농가와 협력하고 있습니다."
            )
        return "\n\n".join(docs)

    def _tool_escalate_to_agent(self, reason: str, urgency: str = "normal") -> str:
        safe_reason = reason.strip()[:200] if reason else ""
        logger.info("에스컬레이션 요청: urgency=%s reason=%s", urgency, safe_reason)
        if urgency == "high":
            return (
                "우선 처리 요청으로 접수되었습니다. "
                "상담원이 최대한 빠르게 연결될 예정입니다. "
                "고객센터 직통 번호: 1588-0000"
            )
        return (
            "상담원 연결을 요청하셨습니다. "
            "잠시만 기다려 주시면 담당 상담원이 연결됩니다. "
            "운영시간: 평일 오전 9시 ~ 오후 6시 / 고객센터: 1588-0000"
        )

    # ── 쓰기 도구 (Human-in-the-Loop) ─────────────────────────────────────

    async def _tool_create_exchange_request(
        self,
        db: Session,
        user_id: int | None,
        session_id: int | None,
        order_id: int,
        reason: str,
        order_item_id: int | None = None,
    ) -> str:
        """교환 신청 초안을 생성하고 사용자 확인을 요청합니다."""
        if not user_id:
            return "교환 신청은 로그인이 필요합니다."
        if not session_id:
            return "세션 정보가 없어 교환 신청을 처리할 수 없습니다."

        from app.models.order import Order, OrderItem
        from app.models.exchange_request import ExchangeRequest
        from app.models.chat_session import ChatSession

        try:
            # 주문 소유권 검증
            order = db.query(Order).filter(
                Order.id == order_id, Order.user_id == user_id
            ).first()
            if not order:
                return f"주문 #{order_id}을 찾을 수 없거나 접근 권한이 없습니다."

            # order_item_id가 해당 주문에 속하는지 검증
            if order_item_id is not None:
                item = db.query(OrderItem).filter(
                    OrderItem.id == order_item_id, OrderItem.order_id == order_id
                ).first()
                if not item:
                    return f"주문 #{order_id}에 해당 상품 항목이 존재하지 않습니다."

            # 교환 가능 상태 확인 (배송완료 또는 배송중)
            if order.status not in ("delivered", "shipping"):
                return (
                    f"주문 #{order_id}은 현재 '{order.status}' 상태로 교환 신청이 불가합니다. "
                    "교환은 배송중 또는 배송완료 상태에서만 가능합니다."
                )

            # 주문 상품 요약
            items_summary = ", ".join(
                f"{item.product.name} x{item.quantity}"
                for item in order.items
                if item.product
            ) or "상품 정보 없음"

            # 중복 방지: 동일 주문에 대기 중인 교환 신청이 있으면 재사용
            # (Primary→Fallback 전환 시 도구 재실행으로 인한 중복 생성 방지)
            existing = db.query(ExchangeRequest).filter(
                ExchangeRequest.user_id == user_id,
                ExchangeRequest.order_id == order_id,
                ExchangeRequest.status == "pending_confirm",
            ).first()

            if existing:
                exchange = existing
            else:
                # 교환 신청 초안 생성 (pending_confirm 상태)
                exchange = ExchangeRequest(
                    user_id=user_id,
                    order_id=order_id,
                    order_item_id=order_item_id,
                    reason=reason,
                    status="pending_confirm",
                )
                db.add(exchange)
                db.flush()  # ID 확보 (commit 전)

            # 세션에 대기 액션 저장 (소유권 검증 포함)
            session = db.query(ChatSession).filter(
                ChatSession.id == session_id, ChatSession.user_id == user_id
            ).first()
            if session:
                session.pending_action = json.dumps({
                    "type": "exchange_request",
                    "exchange_request_id": exchange.id,
                    "summary": f"주문 #{order_id} / {items_summary} / 사유: {reason}",
                }, ensure_ascii=False)
                db.add(session)

            db.commit()

            return (
                f"교환 신청 내용을 확인해 주세요.\n\n"
                f"주문번호: #{order_id}\n"
                f"상품: {items_summary}\n"
                f"교환 사유: {reason}\n\n"
                f"위 내용으로 교환을 신청하시겠어요? (확인/취소)"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"교환 신청 초안 생성 오류: {e}")
            return "교환 신청 처리 중 오류가 발생했습니다."

    async def _tool_confirm_pending_action(
        self,
        db: Session,
        user_id: int | None,
        session_id: int | None,
    ) -> str:
        """대기 중인 액션을 확인하여 최종 실행합니다."""
        if not session_id:
            return "확인할 대기 중인 요청이 없습니다."

        from app.models.chat_session import ChatSession
        from app.models.exchange_request import ExchangeRequest

        try:
            session = db.query(ChatSession).filter(
                ChatSession.id == session_id, ChatSession.user_id == user_id
            ).first()
            if not session or not session.pending_action:
                return "확인할 대기 중인 요청이 없습니다."

            action = json.loads(session.pending_action)

            if action.get("type") == "exchange_request":
                exchange_id = action["exchange_request_id"]
                exchange = db.query(ExchangeRequest).filter(
                    ExchangeRequest.id == exchange_id,
                    ExchangeRequest.user_id == user_id,
                ).first()

                if not exchange or exchange.status != "pending_confirm":
                    session.pending_action = None
                    db.commit()
                    return "이미 처리되었거나 유효하지 않은 요청입니다."

                exchange.status = "confirmed"
                exchange.confirmed_at = datetime.now(timezone.utc)
                session.pending_action = None
                db.commit()

                return (
                    f"교환 신청이 완료됐습니다.\n"
                    f"접수번호: #{exchange.id}\n"
                    f"처리까지 1~3 영업일이 소요됩니다. "
                    f"진행 상황은 마이페이지 > 교환/반품 내역에서 확인하실 수 있습니다."
                )

            return "알 수 없는 액션 유형입니다."

        except Exception as e:
            db.rollback()
            logger.error(f"액션 확인 오류: {e}")
            return "요청 처리 중 오류가 발생했습니다."

    async def _tool_cancel_pending_action(
        self,
        db: Session,
        user_id: int | None,
        session_id: int | None,
    ) -> str:
        """대기 중인 액션을 취소합니다."""
        if not session_id:
            return "취소할 대기 중인 요청이 없습니다."

        from app.models.chat_session import ChatSession
        from app.models.exchange_request import ExchangeRequest

        try:
            session = db.query(ChatSession).filter(
                ChatSession.id == session_id, ChatSession.user_id == user_id
            ).first()
            if not session or not session.pending_action:
                return "취소할 대기 중인 요청이 없습니다."

            action = json.loads(session.pending_action)

            if action.get("type") == "exchange_request":
                exchange_id = action["exchange_request_id"]
                exchange = db.query(ExchangeRequest).filter(
                    ExchangeRequest.id == exchange_id,
                    ExchangeRequest.user_id == user_id,  # 소유권 검증
                ).first()
                if exchange and exchange.status == "pending_confirm":
                    exchange.status = "cancelled"
                    db.add(exchange)

            session.pending_action = None
            db.commit()
            return "교환 신청을 취소했습니다. 다른 도움이 필요하시면 말씀해 주세요."

        except Exception as e:
            db.rollback()
            logger.error(f"액션 취소 오류: {e}")
            return "취소 처리 중 오류가 발생했습니다."
