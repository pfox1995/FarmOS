# 판매/운영 백오피스 자동화 Planning Document

> **Summary**: AI 모델 기반 쇼핑몰 백오피스 자동화 — 챗봇, 매출 분석, 고객 세그먼트, 배송 관리
>
> **Project**: FarmOS - Shopping Mall Backoffice
> **Version**: 0.1.0
> **Author**: clover0309
> **Date**: 2026-04-02
> **Status**: Draft
> **Prerequisites**: GPU 환경 (로컬 LLM 추론용)

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | 농산물 쇼핑몰 운영 시 반복 문의 응대, 매출 정리, 배송 관리 등 수작업이 과도하다 |
| **Solution** | 로컬 AI 모델(LLM + 분석 모델) 기반 백오피스 자동화 시스템 구축 |
| **Function/UX Effect** | 문의 자동 응답, 매출/손익 자동 리포트, 고객 세그먼트 분석, 배송 상태 자동 정리 |
| **Core Value** | 1인 운영자가 AI 어시스턴트와 함께 대규모 주문을 효율적으로 처리할 수 있는 자동화 체계 |

---

## 1. Overview

### 1.1 Purpose

쇼핑몰 운영에서 발생하는 반복 업무를 AI 모델 기반으로 자동화한다.
GPU 서버에서 로컬 LLM을 실행하여 문의 응대, 매출 분석, 고객 관리를 자동 처리한다.

### 1.2 Background

- 기존 `shopping_mall/` 쇼핑몰 프론트+백엔드 위에 백오피스 레이어 추가
- AI 모델은 GPU 필수 → 노트북이 아닌 GPU 탑재 PC에서 진행
- 농산물 특성 (시즌성, 보관법, 수확 시기 등) 반영 필요

---

## 2. 기능 모듈 설계

### Module 1: 주문/문의 응답 챗봇

| 항목 | 내용 |
|------|------|
| **핵심 기능** | 고객 문의에 대한 자동 응답 |
| **AI 모델** | 로컬 LLM (Llama 3.1 8B 또는 Gemma 2 9B) |
| **프레임워크** | vLLM 또는 Ollama (GPU 추론 서버) |
| **RAG 연동** | ChromaDB (FarmOS 기존 설정 활용) + 상품/배송/FAQ 벡터 저장 |

#### 자동 응답 카테고리

| 카테고리 | 예시 질문 | 응답 소스 |
|----------|----------|----------|
| **배송일** | "언제 배송되나요?" | 주문 상태 DB + 택배 API |
| **보관법** | "사과는 어떻게 보관하나요?" | 상품별 보관법 RAG 문서 |
| **수확 시기** | "딸기 수확 시기가 언제예요?" | 농산물 시즌 DB |
| **품절 여부** | "이 상품 재입고 되나요?" | 재고 DB 실시간 조회 |
| **교환/반품** | "교환하고 싶어요" | 정책 문서 RAG |
| **기타** | 분류 불가 → 사람에게 에스컬레이션 | 관리자 알림 |

#### 아키텍처

```
[고객 문의]
    │
    ▼
[의도 분류 (LLM)] ──→ 카테고리 판별
    │
    ├─ 배송/품절 ──→ [DB 조회] ──→ 팩트 기반 응답 생성
    ├─ 보관/수확 ──→ [RAG 검색] ──→ 문서 기반 응답 생성
    └─ 복잡/불만 ──→ [에스컬레이션] ──→ 관리자 알림
    │
    ▼
[응답 생성 (LLM)] ──→ 톤/매너 조정 ──→ 고객에게 전달
```

---

### Module 2: 출하 가능 물량 기반 판매 캘린더

| 항목 | 내용 |
|------|------|
| **핵심 기능** | 재고 + 수확 예측 기반 판매 가능 일정 캘린더 |
| **데이터 소스** | 재고 DB, 수확 시기 DB, 과거 판매 이력 |
| **AI 활용** | 시계열 예측 (수요 예측) — Prophet 또는 간단한 이동평균 |

#### 데이터 모델

```sql
-- 출하 물량 테이블
CREATE TABLE harvest_schedule (
    id INTEGER PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    harvest_date DATE NOT NULL,
    estimated_quantity INTEGER,       -- 예상 출하량 (kg 또는 박스)
    actual_quantity INTEGER,          -- 실제 출하량
    status TEXT DEFAULT 'planned'     -- planned, harvested, shipped
);

-- 판매 캘린더 뷰
CREATE TABLE sales_calendar (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    product_id INTEGER REFERENCES products(id),
    available_quantity INTEGER,       -- 판매 가능 물량
    reserved_quantity INTEGER,        -- 예약된 물량
    price INTEGER                     -- 해당일 판매 가격
);
```

---

### Module 3: 택배 송장/배송 상태 자동 정리

| 항목 | 내용 |
|------|------|
| **핵심 기능** | 송장 번호 등록, 배송 상태 자동 추적, 상태 업데이트 |
| **연동** | 택배사 API (CJ대한통운, 한진, 로젠 등) 또는 스마트택배 API |
| **자동화** | Cron 기반 주기적 상태 조회 + 주문 상태 자동 변경 |

#### 배송 상태 흐름

```
[주문 생성] → [송장 등록] → [집하] → [배송중] → [배달완료]
     │              │           │          │           │
     ▼              ▼           ▼          ▼           ▼
  pending      shipping     shipping   shipping    delivered
                                                      │
                                                      ▼
                                              [자동 구매확정 (7일)]
```

#### 데이터 모델

```sql
CREATE TABLE shipments (
    id INTEGER PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    carrier TEXT NOT NULL,              -- cj, hanjin, logen
    tracking_number TEXT NOT NULL,
    status TEXT DEFAULT 'registered',   -- registered, picked_up, in_transit, delivered
    last_checked_at TIMESTAMP,
    delivered_at TIMESTAMP,
    tracking_history TEXT               -- JSON array of status updates
);
```

---

### Module 4: 매출/비용 자동 분류 + 주간 손익 리포트

| 항목 | 내용 |
|------|------|
| **핵심 기능** | 매출/비용 항목 자동 분류, 주간 손익 리포트 자동 생성 |
| **AI 활용** | LLM 기반 비용 항목 자동 분류 (포장비, 배송비, 원재료 등) |
| **리포트** | 마크다운/PDF 자동 생성, 이메일/슬랙 알림 |

#### 매출/비용 스키마

```sql
-- 매출 (주문 기반 자동 집계)
CREATE TABLE revenue_entries (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER,
    quantity INTEGER,
    unit_price INTEGER,
    total_amount INTEGER,
    category TEXT DEFAULT 'sales'      -- sales, refund
);

-- 비용
CREATE TABLE expense_entries (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    description TEXT NOT NULL,
    amount INTEGER NOT NULL,
    category TEXT,                      -- packaging, shipping, material, labor, etc.
    auto_classified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 주간 리포트
CREATE TABLE weekly_reports (
    id INTEGER PRIMARY KEY,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    total_revenue INTEGER,
    total_expense INTEGER,
    net_profit INTEGER,
    report_content TEXT,               -- 마크다운 리포트 본문
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 주간 리포트 자동 생성 파이프라인

```
[매주 월요일 00:00 Cron]
    │
    ▼
[지난주 매출 집계] ──→ orders 테이블에서 자동 합산
    │
    ▼
[지난주 비용 집계] ──→ expense_entries 미분류 항목 LLM 자동 분류
    │
    ▼
[손익 계산] ──→ 매출 - 비용 = 순이익
    │
    ▼
[LLM 리포트 생성] ──→ 주요 지표 + 전주 대비 + 인사이트
    │
    ▼
[저장 + 알림] ──→ DB 저장, 이메일/슬랙 발송
```

#### 리포트 예시

```markdown
## 주간 손익 리포트 (2026.03.24 ~ 2026.03.30)

| 항목 | 금액 | 전주 대비 |
|------|------|----------|
| 총 매출 | 3,250,000원 | +12.5% |
| 총 비용 | 1,890,000원 | +5.2% |
| 순이익 | 1,360,000원 | +23.8% |

### 매출 TOP 3
1. 유기농 사과 3kg (85건, 2,125,000원)
2. 한우 등심 1kg (12건, 660,000원)
3. 제주 감귤 5kg (23건, 465,000원)

### AI 인사이트
- 사과 매출이 전주 대비 30% 증가, 시즌 피크 진입 예상
- 배송비 비중이 18%로 높음, 묶음 배송 검토 권장
```

---

### Module 5: 고객 세그먼트 분석

| 항목 | 내용 |
|------|------|
| **핵심 기능** | 고객을 자동 세그먼트 분류하여 타겟 마케팅 지원 |
| **AI 활용** | RFM 분석 + K-Means 클러스터링 (scikit-learn) |
| **세그먼트** | 재구매 고객, 이탈 가능 고객, VIP, 신규, 휴면 |

#### RFM 모델

```
R (Recency)    — 마지막 구매 후 경과 일수
F (Frequency)  — 총 구매 횟수
M (Monetary)   — 총 구매 금액
```

#### 세그먼트 정의

| 세그먼트 | 조건 | 액션 |
|----------|------|------|
| **VIP** | R<30, F>=5, M>=500,000 | 전용 쿠폰, 신상품 우선 안내 |
| **충성 고객** | R<60, F>=3 | 재구매 할인 쿠폰 |
| **재구매 고객** | F>=2 | 관련 상품 추천 |
| **신규 고객** | F=1, R<30 | 첫 구매 감사 + 2회차 쿠폰 |
| **이탈 위험** | R>60, F>=2 | 복귀 쿠폰, "다시 오세요" 메시지 |
| **휴면 고객** | R>90 | 재활성화 캠페인 |

#### 인기 품목 분석

```sql
-- 인기 품목 뷰
SELECT 
    p.name,
    COUNT(DISTINCT oi.order_id) AS order_count,
    SUM(oi.quantity) AS total_quantity,
    SUM(oi.price * oi.quantity) AS total_revenue,
    AVG(r.rating) AS avg_rating
FROM order_items oi
JOIN products p ON oi.product_id = p.id
LEFT JOIN reviews r ON r.product_id = p.id
GROUP BY p.id
ORDER BY total_revenue DESC;
```

---

## 3. 기술 스택

### AI/ML 스택

| 구분 | 기술 | 용도 | GPU 필요 |
|------|------|------|:--------:|
| **LLM 추론** | vLLM + Llama 3.1 8B | 챗봇, 비용 분류, 리포트 생성 | Yes |
| **LLM 대안** | Ollama + Gemma 2 9B | 간편 설정, 동일 용도 | Yes |
| **임베딩** | sentence-transformers (all-MiniLM) | RAG 벡터화 | Optional |
| **벡터 DB** | ChromaDB | FAQ/상품 정보 RAG 검색 | No |
| **분석** | scikit-learn | RFM 클러스터링, 고객 세그먼트 | No |
| **시계열** | Prophet 또는 statsmodels | 수요 예측 (판매 캘린더) | No |

### 백엔드 스택

| 구분 | 기술 | 비고 |
|------|------|------|
| **API 서버** | FastAPI (기존 확장) | `shopping_mall/backend`에 모듈 추가 |
| **작업 스케줄러** | APScheduler 또는 Celery | 주기적 배송 조회, 리포트 생성 |
| **DB** | SQLite (기존 확장) | 새 테이블 추가 |

### GPU 요구사항

| 모델 | VRAM | 비고 |
|------|------|------|
| Llama 3.1 8B (4bit) | 6GB+ | 최소 사양 |
| Llama 3.1 8B (FP16) | 16GB+ | 권장 사양 |
| Gemma 2 9B (4bit) | 8GB+ | 대안 |
| 임베딩 모델 | 1-2GB | 선택적 GPU |

---

## 4. 폴더 구조 (확장)

```
shopping_mall/
├── frontend/                    # 기존 React 쇼핑몰
├── backend/                     # 기존 FastAPI
│   ├── app/
│   │   ├── models/              # 기존 + 신규 테이블 추가
│   │   │   ├── shipment.py      # [신규] 배송 추적
│   │   │   ├── harvest.py       # [신규] 출하 물량
│   │   │   ├── revenue.py       # [신규] 매출
│   │   │   ├── expense.py       # [신규] 비용
│   │   │   ├── weekly_report.py # [신규] 주간 리포트
│   │   │   └── customer_segment.py  # [신규] 고객 세그먼트
│   │   ├── routers/
│   │   │   ├── chatbot.py       # [신규] 챗봇 API
│   │   │   ├── calendar.py      # [신규] 판매 캘린더 API
│   │   │   ├── shipments.py     # [신규] 배송 관리 API
│   │   │   ├── reports.py       # [신규] 리포트 API
│   │   │   └── analytics.py     # [신규] 고객/매출 분석 API
│   │   └── services/            # [신규] 비즈니스 로직
│   │       ├── ai_chatbot.py    # LLM 챗봇 서비스
│   │       ├── ai_classifier.py # 비용 자동 분류
│   │       ├── ai_report.py     # 리포트 자동 생성
│   │       ├── shipping_tracker.py  # 배송 추적 서비스
│   │       ├── rfm_analyzer.py  # RFM 고객 분석
│   │       └── demand_forecaster.py # 수요 예측
│   ├── ai/                      # [신규] AI 모델 설정
│   │   ├── llm_client.py        # vLLM/Ollama 클라이언트
│   │   ├── rag.py               # ChromaDB RAG 파이프라인
│   │   ├── prompts/             # 프롬프트 템플릿
│   │   │   ├── chatbot.py
│   │   │   ├── classifier.py
│   │   │   └── report.py
│   │   └── data/                # RAG 문서 (보관법, FAQ 등)
│   │       ├── faq.json
│   │       ├── storage_guide.json
│   │       └── season_info.json
│   └── jobs/                    # [신규] 스케줄 작업
│       ├── scheduler.py         # APScheduler 설정
│       ├── check_shipments.py   # 배송 상태 자동 조회
│       ├── generate_report.py   # 주간 리포트 생성
│       └── update_segments.py   # 고객 세그먼트 갱신
│
└── backoffice/                  # [신규] 관리자 프론트엔드 (별도 패키지)
    ├── package.json
    ├── vite.config.ts           # port 5175
    └── src/
        ├── pages/
        │   ├── DashboardPage.tsx     # 매출/주문 대시보드
        │   ├── ChatbotPage.tsx       # 챗봇 모니터링/설정
        │   ├── CalendarPage.tsx      # 판매 캘린더
        │   ├── ShipmentsPage.tsx     # 배송 관리
        │   ├── ReportsPage.tsx       # 주간 리포트 뷰어
        │   └── AnalyticsPage.tsx     # 고객 세그먼트/인기 품목
        └── components/
```

---

## 5. 구현 순서

### Phase 1: 데이터 기반 구축 (GPU 불필요)
1. [ ] 신규 DB 테이블 추가 (shipments, harvest, revenue, expense, weekly_reports)
2. [ ] 매출 자동 집계 로직 (주문 → revenue_entries 자동 기록)
3. [ ] 배송 추적 모델 + 더미 상태 업데이트
4. [ ] 기본 RFM 분석 (SQL + Python)

### Phase 2: AI 모델 연동 (GPU 필요)
5. [ ] vLLM 또는 Ollama 설치 + LLM 서빙
6. [ ] ChromaDB RAG 구축 (보관법, FAQ, 시즌 정보)
7. [ ] 챗봇 서비스 구현 (의도 분류 → 응답 생성)
8. [ ] 비용 자동 분류 (LLM 기반)

### Phase 3: 자동화 파이프라인
9. [ ] APScheduler 설정 (배송 조회 주기, 리포트 주기)
10. [ ] 주간 손익 리포트 자동 생성 (LLM 인사이트 포함)
11. [ ] 고객 세그먼트 자동 갱신 (일일 배치)
12. [ ] 판매 캘린더 (수확 일정 + 재고 기반)

### Phase 4: 관리자 프론트엔드
13. [ ] `backoffice/` React 프로젝트 초기화 (port 5175)
14. [ ] 대시보드 (매출/주문 차트)
15. [ ] 챗봇 모니터링 (대화 로그, 에스컬레이션 목록)
16. [ ] 배송 관리 (송장 등록, 상태 추적)
17. [ ] 리포트 뷰어 + 고객 세그먼트 시각화

---

## 6. 포트 구성 (전체)

| 서비스 | 포트 | 비고 |
|--------|------|------|
| FarmOS Backend | 8000 | 기존 |
| FarmOS Frontend | 5173 | 기존 |
| Shopping Mall Backend | 4000 | 쇼핑몰 API + AI 서비스 |
| Shopping Mall Frontend | 5174 | 쇼핑몰 고객용 |
| Backoffice Frontend | 5175 | 관리자용 (신규) |
| vLLM / Ollama | 8080 | LLM 추론 서버 (GPU) |
| ChromaDB | 8001 | 벡터 DB (기존 FarmOS 설정 공유 가능) |

---

## 7. GPU 환경 이전 체크리스트

- [ ] GPU PC에 프로젝트 클론 (`git clone`)
- [ ] Python 3.12 + uv 설치
- [ ] CUDA 드라이버 + PyTorch 설치
- [ ] vLLM 또는 Ollama 설치
- [ ] LLM 모델 다운로드 (Llama 3.1 8B 또는 Gemma 2 9B)
- [ ] `uv sync` + `python db/seed.py` 실행
- [ ] 기존 쇼핑몰 정상 동작 확인 후 백오피스 개발 시작

---

## 8. Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| GPU VRAM 부족 | High | 4bit 양자화 모델 사용, 작은 모델 대안 (Phi-3 등) |
| LLM 응답 품질 낮음 | Medium | 프롬프트 엔지니어링 + RAG로 팩트 기반 응답 강제 |
| 택배 API 제한 | Medium | 스마트택배 API 사용, 조회 주기 조절 |
| 실시간 추론 지연 | Medium | 비동기 처리, 캐싱, 배치 처리 병행 |

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-02 | Initial draft | clover0309 |
