# 백오피스 자동화 Design Document

> **Summary**: AI 모델 기반 쇼핑몰 백오피스 자동화 — 상세 설계
>
> **Project**: FarmOS - Shopping Mall Backoffice
> **Version**: 0.1.0
> **Author**: clover0309
> **Date**: 2026-04-02
> **Status**: Draft
> **Planning Doc**: [backoffice-automation.plan.md](../01-plan/features/backoffice-automation.plan.md)
> **Prerequisites**: GPU 환경 (로컬 LLM 추론용)

---

## 1. System Architecture

### 1.1 전체 시스템 구성

```
┌──────────────────────────────────────────────────────────────────────┐
│                        관리자 (Browser)                              │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────────┐
│            Backoffice Frontend (React+Vite, port 5175)               │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │ Dashboard  │ │ Chatbot  │ │ Calendar │ │ Reports  │ │Analytic│  │
│  │  Page      │ │ Monitor  │ │  Page    │ │  Page    │ │s Page  │  │
│  └────────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘  │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ HTTP REST
┌──────────────────────────▼───────────────────────────────────────────┐
│         Shopping Mall Backend (FastAPI, port 4000) — 확장             │
│                                                                      │
│  ┌─ 기존 라우터 ──────────────────────────────────────────────────┐  │
│  │ products, categories, cart, orders, users, reviews, stores     │  │
│  └───────────────────────────────────────────────────────────────-┘  │
│                                                                      │
│  ┌─ 신규 라우터 ──────────────────────────────────────────────────┐  │
│  │ chatbot, calendar, shipments, reports, analytics               │  │
│  └───────────────────────────────────────────────────────────────-┘  │
│                                                                      │
│  ┌─ 신규 서비스 ──────────────────────────────────────────────────┐  │
│  │ ai_chatbot, ai_classifier, ai_report, shipping_tracker,       │  │
│  │ rfm_analyzer, demand_forecaster                                │  │
│  └──────────────────────┬────────────────────────────────────────-┘  │
│                          │                                           │
│  ┌─ 스케줄러 ────────────┤───────────────────────────────────────-┐  │
│  │ APScheduler: 배송조회(1h), 리포트(주1회), 세그먼트(일1회)     │  │
│  └───────────────────────┘───────────────────────────────────────-┘  │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   PostgreSQL     │ │  ChromaDB    │ │ LLM Server   │
│  (farmos DB)   │ │ (RAG 벡터)   │ │ (Ollama)     │
│  기존+신규   │ │  port 8001   │ │  port 11434  │
│  테이블      │ │              │ │  Llama 3.1   │
└──────────────┘ └──────────────┘ └──────────────┘
```

### 1.2 포트 맵 (전체)

| Service | Port | GPU | 비고 |
|---------|:----:|:---:|------|
| FarmOS Backend | 8000 | No | 기존 |
| FarmOS Frontend | 5173 | No | 기존 |
| Shopping Mall Backend | 4000 | No | 기존 + 백오피스 API 확장 |
| Shopping Mall Frontend | 5174 | No | 기존 고객용 |
| **Backoffice Frontend** | **5175** | No | 신규 관리자용 |
| **Ollama (LLM)** | **11434** | **Yes** | 신규 LLM 추론 |
| **ChromaDB** | **8001** | No | 기존 FarmOS 설정 활용 가능 |

---

## 2. AI 모델 설계

### 2.1 LLM 서빙 (Ollama)

```
┌─────────────────────────────────────────┐
│  Ollama Server (port 11434, GPU)        │
│                                         │
│  Models:                                │
│  ├─ llama3.1:8b    (챗봇, 리포트)       │
│  └─ nomic-embed-text (임베딩, RAG)      │
│                                         │
│  API: POST http://localhost:11434/api/   │
│  ├─ /generate  (텍스트 생성)            │
│  ├─ /chat      (대화형)                 │
│  └─ /embeddings (벡터화)                │
└─────────────────────────────────────────┘
```

#### Ollama 클라이언트 인터페이스

```python
# ai/llm_client.py
class LLMClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.model = "llama3.1:8b"

    async def generate(self, prompt: str, system: str = "") -> str:
        """단일 텍스트 생성"""

    async def chat(self, messages: list[dict]) -> str:
        """대화형 생성 (챗봇용)"""

    async def embed(self, text: str) -> list[float]:
        """텍스트 벡터화 (RAG용)"""

    async def classify_intent(self, query: str) -> str:
        """의도 분류 — 반환: delivery|storage|season|stock|exchange|other"""

    async def generate_report(self, data: dict) -> str:
        """매출 데이터 기반 주간 리포트 생성"""

    async def classify_expense(self, description: str) -> str:
        """비용 항목 자동 분류 — 반환: packaging|shipping|material|labor|etc"""
```

### 2.2 RAG 파이프라인 (ChromaDB)

```
[사용자 질문]
    │
    ▼
[임베딩] ──→ nomic-embed-text (Ollama)
    │
    ▼
[ChromaDB 유사도 검색] ──→ top-3 문서 검색
    │
    ▼
[컨텍스트 + 질문 조합] ──→ LLM 프롬프트 구성
    │
    ▼
[LLM 응답 생성] ──→ llama3.1:8b
```

#### ChromaDB 컬렉션 구조

| Collection | 문서 내용 | 문서 수 | 갱신 주기 |
|------------|----------|:-------:|----------|
| `faq` | 자주 묻는 질문/답변 | 30+ | 수동 |
| `storage_guide` | 농산물별 보관법 | 40+ | 시즌별 |
| `season_info` | 수확 시기, 제철 정보 | 30+ | 연 1회 |
| `product_info` | 상품 설명, 특징 | 상품 수만큼 | 상품 등록 시 |
| `policy` | 교환/반품/배송 정책 | 10+ | 수동 |

#### RAG 서비스

```python
# ai/rag.py
class RAGService:
    def __init__(self, chroma_client, llm_client: LLMClient):
        self.chroma = chroma_client
        self.llm = llm_client

    async def query(self, question: str, collection: str, top_k: int = 3) -> str:
        """컬렉션에서 관련 문서 검색 후 LLM 응답 생성"""

    async def add_documents(self, collection: str, docs: list[dict]) -> None:
        """문서 추가 (텍스트 + 메타데이터)"""

    async def update_product_docs(self, products: list) -> None:
        """상품 DB에서 product_info 컬렉션 자동 갱신"""
```

---

## 3. Data Model (신규 테이블)

### 3.1 SQLAlchemy Models

```python
# app/models/shipment.py
class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    carrier: Mapped[str] = mapped_column(String(20), nullable=False)       # cj, hanjin, logen
    tracking_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="registered")  # registered, picked_up, in_transit, delivered
    last_checked_at: Mapped[datetime | None] = mapped_column()
    delivered_at: Mapped[datetime | None] = mapped_column()
    tracking_history: Mapped[str | None] = mapped_column(Text)             # JSON array
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    order: Mapped["Order"] = relationship()


# app/models/harvest.py
class HarvestSchedule(Base):
    __tablename__ = "harvest_schedule"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    harvest_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    estimated_quantity: Mapped[int | None] = mapped_column()
    actual_quantity: Mapped[int | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="planned")     # planned, harvested, shipped

    product: Mapped["Product"] = relationship()


# app/models/revenue.py
class RevenueEntry(Base):
    __tablename__ = "revenue_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int | None] = mapped_column()
    unit_price: Mapped[int | None] = mapped_column()
    total_amount: Mapped[int] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(String(20), default="sales")     # sales, refund


# app/models/expense.py
class ExpenseEntry(Base):
    __tablename__ = "expense_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[int] = mapped_column(nullable=False)
    category: Mapped[str | None] = mapped_column(String(30))               # packaging, shipping, material, labor, etc
    auto_classified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())


# app/models/weekly_report.py
class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    week_start: Mapped[str] = mapped_column(String(10), nullable=False)
    week_end: Mapped[str] = mapped_column(String(10), nullable=False)
    total_revenue: Mapped[int] = mapped_column(default=0)
    total_expense: Mapped[int] = mapped_column(default=0)
    net_profit: Mapped[int] = mapped_column(default=0)
    report_content: Mapped[str | None] = mapped_column(Text)               # 마크다운 본문
    generated_at: Mapped[datetime] = mapped_column(default=func.now())


# app/models/customer_segment.py
class CustomerSegment(Base):
    __tablename__ = "customer_segments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    segment: Mapped[str] = mapped_column(String(20), nullable=False)       # vip, loyal, repeat, new, at_risk, dormant
    recency_days: Mapped[int] = mapped_column(default=0)
    frequency: Mapped[int] = mapped_column(default=0)
    monetary: Mapped[int] = mapped_column(default=0)
    last_updated: Mapped[datetime] = mapped_column(default=func.now())

    user: Mapped["User"] = relationship()


# app/models/chat_log.py
class ChatLog(Base):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    intent: Mapped[str] = mapped_column(String(30))                        # delivery, storage, season, stock, exchange, other
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    escalated: Mapped[bool] = mapped_column(default=False)
    rating: Mapped[int | None] = mapped_column()                           # 1-5 사용자 평가
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

### 3.2 Entity Relationships (신규)

```
[Order] 1 ──── 1 [Shipment]
[Product] 1 ──── N [HarvestSchedule]
[Order] 1 ──── N [RevenueEntry]
[User] 1 ──── 1 [CustomerSegment]
[User] 1 ──── N [ChatLog]
```

---

## 4. API Specification (신규 라우터)

### 4.1 챗봇 API (`/api/chatbot`)

| Method | Endpoint | 설명 | GPU |
|--------|----------|------|:---:|
| POST | `/api/chatbot/ask` | 질문 → AI 자동응답 | Yes |
| GET | `/api/chatbot/logs` | 대화 로그 조회 | No |
| GET | `/api/chatbot/logs/escalated` | 에스컬레이션 목록 | No |
| PUT | `/api/chatbot/logs/{id}/rating` | 응답 평가 | No |

#### `POST /api/chatbot/ask`

**Request:**
```json
{
  "userId": 1,
  "question": "사과는 어떻게 보관하나요?"
}
```

**Response (200):**
```json
{
  "answer": "사과는 비닐봉지에 넣어 냉장고 야채칸에 보관하시면 2-3주간 신선하게 드실 수 있습니다. 에틸렌 가스를 많이 배출하므로 다른 과일과 분리 보관하시는 것을 추천드립니다.",
  "intent": "storage",
  "escalated": false,
  "sources": ["storage_guide: 사과 보관법"]
}
```

#### 챗봇 처리 플로우 (서비스 내부)

```python
# app/services/ai_chatbot.py
class ChatbotService:
    def __init__(self, llm: LLMClient, rag: RAGService, db: Session):
        ...

    async def answer(self, user_id: int, question: str) -> dict:
        # 1. 의도 분류
        intent = await self.llm.classify_intent(question)

        # 2. 의도별 처리
        if intent in ("delivery", "stock"):
            # DB에서 실시간 정보 조회
            context = self._query_db(intent, user_id)
            answer = await self.llm.generate(
                prompt=f"질문: {question}\n정보: {context}\n친절하게 답변해주세요.",
                system="당신은 FarmOS 마켓의 친절한 고객 상담사입니다."
            )
        elif intent in ("storage", "season", "exchange"):
            # RAG 검색
            collection = {"storage": "storage_guide", "season": "season_info", "exchange": "policy"}[intent]
            answer = await self.rag.query(question, collection)
        else:
            # 에스컬레이션
            answer = "죄송합니다. 해당 문의는 상담원이 확인 후 답변 드리겠습니다."
            escalated = True

        # 3. 로그 저장
        self._save_log(user_id, intent, question, answer, escalated)
        return {"answer": answer, "intent": intent, "escalated": escalated}
```

### 4.2 배송 관리 API (`/api/shipments`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/shipments` | 송장 등록 |
| GET | `/api/shipments` | 배송 목록 (필터: status) |
| GET | `/api/shipments/{id}` | 배송 상세 (추적 이력) |
| POST | `/api/shipments/{id}/check` | 수동 상태 조회 트리거 |

#### `POST /api/shipments`

**Request:**
```json
{
  "orderId": 1,
  "carrier": "cj",
  "trackingNumber": "1234567890"
}
```

### 4.3 판매 캘린더 API (`/api/calendar`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/calendar` | 월별 판매 가능 물량 캘린더 |
| POST | `/api/calendar/harvest` | 출하 일정 등록 |
| PUT | `/api/calendar/harvest/{id}` | 출하 일정 수정 |
| GET | `/api/calendar/forecast/{productId}` | 수요 예측 (AI) |

### 4.4 리포트 API (`/api/reports`)

| Method | Endpoint | 설명 | GPU |
|--------|----------|------|:---:|
| GET | `/api/reports/weekly` | 주간 리포트 목록 | No |
| GET | `/api/reports/weekly/{id}` | 리포트 상세 (마크다운) | No |
| POST | `/api/reports/weekly/generate` | 수동 리포트 생성 트리거 | Yes |
| GET | `/api/reports/revenue` | 매출 현황 (기간별) | No |
| GET | `/api/reports/expenses` | 비용 현황 (기간별) | No |
| POST | `/api/reports/expenses` | 비용 입력 | No |
| POST | `/api/reports/expenses/classify` | 미분류 비용 AI 자동 분류 | Yes |

### 4.5 분석 API (`/api/analytics`)

| Method | Endpoint | 설명 | GPU |
|--------|----------|------|:---:|
| GET | `/api/analytics/segments` | 고객 세그먼트 현황 | No |
| GET | `/api/analytics/segments/{segment}` | 특정 세그먼트 고객 목록 | No |
| POST | `/api/analytics/segments/refresh` | 세그먼트 재계산 트리거 | No |
| GET | `/api/analytics/popular-items` | 인기 품목 TOP N | No |
| GET | `/api/analytics/dashboard` | 대시보드 통합 데이터 | No |

#### `GET /api/analytics/dashboard`

**Response:**
```json
{
  "today": {
    "revenue": 450000,
    "orderCount": 12,
    "newCustomers": 3
  },
  "thisWeek": {
    "revenue": 3250000,
    "orderCount": 85,
    "revenueChange": 12.5
  },
  "segments": {
    "vip": 5,
    "loyal": 12,
    "repeat": 28,
    "new": 45,
    "atRisk": 8,
    "dormant": 15
  },
  "popularItems": [
    {"productId": 1, "name": "유기농 사과 3kg", "orderCount": 85, "revenue": 2125000}
  ],
  "pendingEscalations": 3
}
```

---

## 5. Services 설계

### 5.1 서비스 의존성

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│  ChatbotService │────▶│  LLMClient   │────▶│ Ollama(GPU)  │
│                 │────▶│  RAGService  │────▶│ ChromaDB     │
├─────────────────┤     └──────────────┘     └──────────────┘
│ ClassifierSvc   │────▶│  LLMClient   │
├─────────────────┤     └──────────────┘
│ ReportService   │────▶│  LLMClient   │
│                 │────▶│  DB (PostgreSQL) │
├─────────────────┤     └──────────────┘
│ ShippingTracker │────▶│  택배 API    │ (더미/실제)
├─────────────────┤     └──────────────┘
│ RFMAnalyzer     │────▶│  DB (PostgreSQL) │
│                 │────▶│ scikit-learn │
├─────────────────┤     └──────────────┘
│ DemandForecaster│────▶│  DB (PostgreSQL) │
│                 │────▶│ statsmodels  │
└─────────────────┘     └──────────────┘
```

### 5.2 RFM 분석 서비스

```python
# app/services/rfm_analyzer.py
class RFMAnalyzer:
    SEGMENT_RULES = {
        "vip":      lambda r, f, m: r < 30 and f >= 5 and m >= 500000,
        "loyal":    lambda r, f, m: r < 60 and f >= 3,
        "repeat":   lambda r, f, m: f >= 2,
        "new":      lambda r, f, m: f == 1 and r < 30,
        "at_risk":  lambda r, f, m: r > 60 and f >= 2,
        "dormant":  lambda r, f, m: r > 90,
    }

    def analyze_all(self, db: Session) -> list[dict]:
        """전체 고객 RFM 계산 + 세그먼트 분류"""
        # 1. 주문 데이터에서 R/F/M 계산
        # 2. 규칙 기반 세그먼트 분류
        # 3. customer_segments 테이블 upsert
        # 4. 결과 반환

    def get_segment_summary(self, db: Session) -> dict:
        """세그먼트별 고객 수 집계"""
```

### 5.3 주간 리포트 생성 서비스

```python
# app/services/ai_report.py
class ReportService:
    def __init__(self, llm: LLMClient, db: Session):
        ...

    async def generate_weekly(self, week_start: str, week_end: str) -> WeeklyReport:
        # 1. 매출 집계 (revenue_entries)
        revenue = self._sum_revenue(week_start, week_end)

        # 2. 비용 집계 + 미분류 항목 자동 분류
        expenses = self._sum_expenses(week_start, week_end)

        # 3. TOP 상품, 전주 대비 변화 계산
        top_items = self._get_top_items(week_start, week_end)
        prev_revenue = self._sum_revenue(prev_start, prev_end)

        # 4. LLM으로 인사이트 생성
        insight = await self.llm.generate_report({
            "revenue": revenue, "expenses": expenses,
            "profit": revenue - expenses,
            "change": ((revenue - prev_revenue) / prev_revenue * 100),
            "top_items": top_items
        })

        # 5. 마크다운 리포트 조합 + DB 저장
        report = self._build_markdown(revenue, expenses, top_items, insight)
        return self._save_report(week_start, week_end, revenue, expenses, report)
```

---

## 6. 스케줄러 설계

### 6.1 APScheduler Jobs

| Job | 주기 | 서비스 | GPU |
|-----|------|--------|:---:|
| `check_shipments` | 매 1시간 | ShippingTracker | No |
| `generate_weekly_report` | 매주 월 00:00 | ReportService | Yes |
| `update_segments` | 매일 03:00 | RFMAnalyzer | No |
| `auto_classify_expenses` | 매일 02:00 | ClassifierService | Yes |
| `sync_revenue` | 매 30분 | RevenueSync | No |

```python
# jobs/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

scheduler.add_job(check_shipments, "interval", hours=1)
scheduler.add_job(generate_weekly_report, "cron", day_of_week="mon", hour=0)
scheduler.add_job(update_segments, "cron", hour=3)
scheduler.add_job(auto_classify_expenses, "cron", hour=2)
scheduler.add_job(sync_revenue, "interval", minutes=30)
```

---

## 7. Backoffice Frontend 설계

### 7.1 페이지 구조

| Page | Route | 주요 컴포넌트 |
|------|-------|-------------|
| DashboardPage | `/` | 매출 차트, 주문 수, 세그먼트 파이차트, 에스컬레이션 알림 |
| ChatbotPage | `/chatbot` | 대화 로그 테이블, 에스컬레이션 목록, 의도별 통계 |
| CalendarPage | `/calendar` | 월별 캘린더 뷰, 출하 일정, 수요 예측 그래프 |
| ShipmentsPage | `/shipments` | 송장 등록 폼, 배송 상태 테이블, 필터 |
| ReportsPage | `/reports` | 주간 리포트 목록, 마크다운 렌더러, 수동 생성 버튼 |
| AnalyticsPage | `/analytics` | 세그먼트 테이블, 인기 품목 차트, RFM 산점도 |
| ExpensesPage | `/expenses` | 비용 입력 폼, 분류 현황, AI 자동 분류 버튼 |

### 7.2 대시보드 와이어프레임

```
┌────────────────────────────────────────────────────────────────┐
│  FarmOS 백오피스                              [관리자: 홍길동] │
├──────────┬─────────────────────────────────────────────────────┤
│          │                                                     │
│ 대시보드 │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│ 챗봇     │  │ 오늘매출 │ │ 주문수   │ │ 신규고객 │            │
│ 캘린더   │  │ 450,000  │ │   12건   │ │   3명   │            │
│ 배송관리 │  └──────────┘ └──────────┘ └──────────┘            │
│ 리포트   │                                                     │
│ 분석     │  ┌─────────────────────┐ ┌──────────────────────┐  │
│ 비용관리 │  │  주간 매출 추이     │ │  고객 세그먼트       │  │
│          │  │  (라인 차트)        │ │  (파이 차트)         │  │
│          │  │                     │ │  VIP: 5              │  │
│          │  │                     │ │  충성: 12            │  │
│          │  └─────────────────────┘ │  이탈위험: 8         │  │
│          │                          └──────────────────────┘  │
│          │  ┌─────────────────────────────────────────────┐   │
│          │  │ 미처리 에스컬레이션 (3건)                    │   │
│          │  │ • "배송이 너무 늦어요" — 2시간 전            │   │
│          │  │ • "상품이 파손되었어요" — 5시간 전            │   │
│          │  └─────────────────────────────────────────────┘   │
└──────────┴─────────────────────────────────────────────────────┘
```

### 7.3 기술 스택

| 항목 | 기술 | 비고 |
|------|------|------|
| Framework | React 19 + Vite | 쇼핑몰과 동일 |
| Routing | React Router DOM v7 | |
| Styling | Tailwind CSS | |
| Charts | Recharts | FarmOS 프론트엔드에서 이미 사용 |
| Data Fetching | TanStack Query + axios | |
| Markdown | react-markdown | 리포트 렌더링 |
| Date | date-fns | 캘린더, 날짜 처리 |

---

## 8. Prompt Templates

### 8.1 의도 분류 프롬프트

```python
# ai/prompts/chatbot.py
INTENT_CLASSIFY_PROMPT = """
당신은 농산물 쇼핑몰 고객 문의를 분류하는 시스템입니다.
아래 카테고리 중 하나만 답하세요:

- delivery: 배송일, 배송 상태, 도착 예정
- storage: 보관법, 보관 방법
- season: 수확 시기, 제철 정보
- stock: 품절, 재입고, 재고
- exchange: 교환, 반품, 환불
- other: 위에 해당하지 않는 문의

고객 질문: {question}
카테고리:"""

ANSWER_PROMPT = """
당신은 FarmOS 마켓의 친절한 고객 상담사입니다.
아래 정보를 바탕으로 고객에게 친절하게 답변해주세요.
추측하지 말고, 제공된 정보만 사용하세요.

참고 정보:
{context}

고객 질문: {question}
답변:"""
```

### 8.2 리포트 생성 프롬프트

```python
# ai/prompts/report.py
WEEKLY_REPORT_PROMPT = """
아래 농산물 쇼핑몰의 주간 매출 데이터를 분석하여 인사이트를 작성해주세요.
3-4문장으로 간결하게, 실행 가능한 제안을 포함해주세요.

주간 데이터:
- 총 매출: {revenue}원 (전주 대비 {change}%)
- 총 비용: {expenses}원
- 순이익: {profit}원
- TOP 상품: {top_items}

인사이트:"""
```

### 8.3 비용 분류 프롬프트

```python
# ai/prompts/classifier.py
EXPENSE_CLASSIFY_PROMPT = """
아래 비용 항목을 다음 카테고리 중 하나로 분류해주세요.
카테고리명만 답하세요.

카테고리: packaging, shipping, material, labor, marketing, rent, utility, tax, other

비용 설명: {description}
카테고리:"""
```

---

## 9. Implementation Order

### Phase 1: DB + 기본 API (GPU 불필요)

1. [ ] 신규 모델 7개 추가 (shipment, harvest, revenue, expense, weekly_report, customer_segment, chat_log)
2. [ ] `app/models/__init__.py` 업데이트
3. [ ] 신규 Pydantic 스키마 (shipment, harvest, revenue, expense, report, segment, chatlog)
4. [ ] 라우터: `/api/shipments` (CRUD)
5. [ ] 라우터: `/api/calendar` (출하 일정 CRUD)
6. [ ] 라우터: `/api/reports/revenue`, `/api/reports/expenses` (매출/비용 조회/입력)
7. [ ] 라우터: `/api/analytics/segments`, `/api/analytics/popular-items`, `/api/analytics/dashboard`
8. [ ] RFM 분석 서비스 (`rfm_analyzer.py`) — SQL + Python, GPU 불필요
9. [ ] 매출 자동 동기화 서비스 (주문 → revenue_entries)
10. [ ] 시드 데이터 확장 (배송, 출하, 비용, 세그먼트 더미)

### Phase 2: AI 모델 연동 (GPU 필요)

11. [ ] Ollama 설치 + Llama 3.1 8B 모델 다운로드
12. [ ] `ai/llm_client.py` — Ollama API 클라이언트
13. [ ] ChromaDB 컬렉션 생성 + RAG 문서 로드 (`ai/data/`)
14. [ ] `ai/rag.py` — RAG 서비스
15. [ ] `ai/prompts/` — 프롬프트 템플릿 3개
16. [ ] 챗봇 서비스 (`ai_chatbot.py`)
17. [ ] 라우터: `/api/chatbot/ask`, `/api/chatbot/logs`
18. [ ] 비용 자동 분류 서비스 (`ai_classifier.py`)
19. [ ] 주간 리포트 자동 생성 서비스 (`ai_report.py`)

### Phase 3: 스케줄러 + 배송 추적

20. [ ] APScheduler 설정 (`jobs/scheduler.py`)
21. [ ] 배송 상태 자동 조회 job (더미 택배 API 또는 실제)
22. [ ] 주간 리포트 자동 생성 job (월요일 Cron)
23. [ ] 고객 세그먼트 자동 갱신 job (일일 배치)
24. [ ] 비용 자동 분류 job (일일 배치)
25. [ ] FastAPI lifespan에 스케줄러 통합

### Phase 4: 관리자 프론트엔드

26. [ ] `shopping_mall/backoffice/` React+Vite 초기화 (port 5175)
27. [ ] 라우터 + 사이드바 레이아웃
28. [ ] DashboardPage (매출 차트, 세그먼트 파이, 에스컬레이션)
29. [ ] ChatbotPage (대화 로그, 에스컬레이션 관리)
30. [ ] ShipmentsPage (송장 등록, 상태 추적)
31. [ ] CalendarPage (출하 캘린더)
32. [ ] ReportsPage (주간 리포트 마크다운 뷰어)
33. [ ] AnalyticsPage (세그먼트 + 인기 품목)
34. [ ] ExpensesPage (비용 입력 + AI 분류)

---

## 10. Dependencies (추가 설치)

### Backend (`pyproject.toml` 추가)

```toml
# Phase 1
"apscheduler>=3.10.0",

# Phase 2 (GPU 환경에서)
"httpx>=0.27.0",              # Ollama API 호출 (async)
"chromadb>=0.5.0",            # 벡터 DB
"scikit-learn>=1.5.0",        # RFM 클러스터링 (선택)
```

### Backoffice Frontend (`package.json`)

```json
{
  "dependencies": {
    "react": "^19",
    "react-dom": "^19",
    "react-router-dom": "^7",
    "@tanstack/react-query": "^5",
    "axios": "^1",
    "zustand": "^5",
    "recharts": "^2",
    "react-markdown": "^9",
    "date-fns": "^4"
  }
}
```

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-02 | Initial design | clover0309 |
