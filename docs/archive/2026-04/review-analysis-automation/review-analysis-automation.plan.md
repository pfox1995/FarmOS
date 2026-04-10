# Review Analysis Automation Planning Document

> **Summary**: 리뷰 데이터를 RAG/임베딩 기반으로 분석(감성분석, 키워드추출, 요약, 트렌드탐지)하고 대시보드/리포팅으로 제공하는 자동화 시스템
>
> **Project**: FarmOS - Review Analysis Module
> **Version**: 0.1.0
> **Author**: clover0309
> **Date**: 2026-04-10
> **Status**: Draft

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | 현재 리뷰 분석이 Mock 데이터 기반 프론트엔드에만 존재하며, 실제 NLP/AI 분석 로직이 없어 리뷰 데이터의 인사이트를 자동으로 추출할 수 없다 |
| **Solution** | ChromaDB 임베딩 + RAG 파이프라인으로 리뷰를 벡터 저장/의미 검색하고, LLM 추상화 클라이언트로 감성분석/키워드/요약을 1회 호출로 동시 처리 |
| **Function/UX Effect** | 농업인 판매자는 자기 상품 리뷰 인사이트를 대시보드로 확인, 관리자는 전체 리포트를 PDF로 출력. 수동 분석 + 자동 배치 모두 지원 |
| **Core Value** | RAG/임베딩을 직접 구현하여 학습 효과 극대화 + 기존 ChromaDB/Ollama 인프라를 재활용하여 추가 비용 최소화 |

---

## Context Anchor

| Anchor | Content |
|--------|---------|
| **WHY** | 리뷰 데이터에서 품질/배송/포장 등 개선점을 자동 추출하여 농산물 판매 전략에 반영하기 위함 |
| **WHO** | 농업인 판매자 (자기 상품 분석) + 관리자/운영자 (전체 모니터링) |
| **RISK** | LLM 비용 증가, 분석 정확도 불안정, Ollama 로컬 환경 의존성 |
| **SUCCESS** | 리뷰 임베딩→검색→분석 파이프라인 동작, 감성분석 정확도 80%+, 대시보드 실시간 표시 |
| **SCOPE** | 감성분석 + 키워드추출 + 요약 + 트렌드/이상탐지 + 대시보드/리포팅 (5가지) |

---

## 1. Overview

### 1.1 Purpose

FarmOS 쇼핑몰의 리뷰 데이터를 RAG(Retrieval-Augmented Generation)/임베딩 기반으로 자동 분석하는 시스템을 구축한다. ChromaDB에 리뷰를 벡터로 저장하고, 의미 검색을 통해 관련 리뷰를 추출한 뒤, LLM으로 감성분석/키워드추출/요약을 수행한다.

### 1.2 Background

- 현재 리뷰 페이지(`ReviewsPage.tsx`)는 Mock 데이터 50개 기반으로 시각화만 구현
- 백엔드에 실제 감성분석/키워드추출 로직 없음
- ChromaDB(`backend/app/core/vectordb.py`)와 RAG 패턴(`shopping_mall/backend/ai/rag.py`)이 이미 프로젝트에 존재
- LLM 클라이언트가 2종 존재: Ollama 로컬(`shopping_mall/backend/ai/llm_client.py`), OpenRouter 클라우드(`backend/app/core/ai_agent.py`)
- 학습 목표: RAG/임베딩 원리를 직접 구현하며 이해

### 1.3 Related Documents

- 쇼핑몰 Plan: `docs/01-plan/features/shopping-mall.plan.md`
- 쇼핑몰 Design: `docs/02-design/features/shopping-mall.design.md`
- IoT AI Agent Plan: `docs/01-plan/features/iot-ai-agent-automation.plan.md`
- 기존 벡터DB: `backend/app/core/vectordb.py`
- 기존 RAG 서비스: `shopping_mall/backend/ai/rag.py`
- 기존 LLM 클라이언트: `shopping_mall/backend/ai/llm_client.py`

---

## 2. Requirements

### 2.1 Functional Requirements

#### FR-01: 리뷰 임베딩 및 벡터 저장

| 항목 | 내용 |
|------|------|
| **설명** | 리뷰 텍스트를 ChromaDB에 벡터로 저장하고 의미 기반 검색 지원 |
| **입력** | 리뷰 텍스트, 평점, 플랫폼, 날짜, 상품ID |
| **처리** | ChromaDB 내장 임베딩 모델로 벡터 변환 후 저장. 메타데이터(평점, 플랫폼, 날짜)도 함께 저장 |
| **출력** | 저장 성공/실패 응답 |
| **비고** | ChromaDB의 기본 임베딩 모델(all-MiniLM-L6-v2) 사용, 외부 API 호출 불필요 |

#### FR-02: 의미 기반 리뷰 검색 (RAG Retrieval)

| 항목 | 내용 |
|------|------|
| **설명** | 자연어 질의로 관련 리뷰를 의미 검색 |
| **입력** | 검색 질의 텍스트, 필터 조건(플랫폼, 기간, 평점 범위), top_k |
| **처리** | 질의를 벡터로 변환 → ChromaDB에서 코사인 유사도 기반 검색 → 메타데이터 필터 적용 |
| **출력** | 유사 리뷰 목록 (텍스트, 유사도 점수, 메타데이터) |
| **비고** | 예: "포장 관련 불만" → 포장 관련 부정 리뷰 반환 |

#### FR-03: 감성 분석 (Sentiment Analysis)

| 항목 | 내용 |
|------|------|
| **설명** | 리뷰 텍스트의 감성을 긍정/부정/중립으로 분류하고 감성 점수 부여 |
| **입력** | 리뷰 텍스트 (단건 또는 배치) |
| **처리** | LLM에게 리뷰 전달 → JSON 형식으로 감성 분류 + 점수(-1.0~1.0) 반환 요청 |
| **출력** | `{ sentiment: "positive"|"negative"|"neutral", score: float, reason: string }` |
| **비고** | 배치 처리 시 여러 리뷰를 1회 LLM 호출로 동시 분석하여 비용 절감 |

#### FR-04: 토픽/키워드 추출 (Topic & Keyword Extraction)

| 항목 | 내용 |
|------|------|
| **설명** | 리뷰 모음에서 주요 토픽과 키워드를 자동 추출 |
| **입력** | 리뷰 텍스트 배치 (RAG 검색 결과 또는 전체) |
| **처리** | LLM에게 리뷰 배치 전달 → 키워드별 빈도/감성 태깅 요청. FR-03과 동일 LLM 호출에서 동시 처리 |
| **출력** | `[{ word: string, count: number, sentiment: string }]` |
| **비고** | 감성분석(FR-03)과 1회 LLM 호출로 동시 처리하여 비용 최소화 |

#### FR-05: 리뷰 요약 (Summary Generation)

| 항목 | 내용 |
|------|------|
| **설명** | 다수 리뷰를 LLM으로 요약하여 핵심 인사이트 생성 |
| **입력** | 리뷰 배치 (전체 또는 RAG 검색 결과), 요약 유형(전체/긍정/부정) |
| **처리** | RAG로 관련 리뷰 검색 → LLM에게 요약 요청 → 구조화된 요약 반환 |
| **출력** | `{ overall: string, positives: string[], negatives: string[], suggestions: string[] }` |
| **비고** | FR-03, FR-04와 1회 LLM 호출로 통합 가능 (프롬프트에 감성+키워드+요약 동시 요청) |

#### FR-06: 트렌드/이상 탐지 (Trend & Anomaly Detection)

| 항목 | 내용 |
|------|------|
| **설명** | 시계열 기반으로 감성 추이, 키워드 변동, 이상 패턴을 탐지 |
| **입력** | 기간별 분석 결과 (감성 비율, 키워드 빈도 등) |
| **처리** | 주간/월간 감성 비율 계산 → 이동평균 대비 편차 계산 → 임계값 초과 시 이상 탐지 |
| **출력** | `{ trends: TrendData[], anomalies: AnomalyAlert[] }` |
| **비고** | 통계 기반 로직으로 LLM 호출 불필요. 부정 리뷰 급증, 특정 키워드 급등 등 탐지 |

#### FR-07: 대시보드/리포팅 (Dashboard & Reporting)

| 항목 | 내용 |
|------|------|
| **설명** | 분석 결과를 시각화 대시보드와 PDF 리포트로 제공 |
| **입력** | 분석 결과 데이터 (감성, 키워드, 요약, 트렌드) |
| **처리** | 기존 ReviewsPage.tsx UI를 실제 API 연동으로 전환 + PDF 리포트 생성 (fpdf2 활용) |
| **출력** | 판매자용 대시보드 (웹), 관리자용 PDF 리포트 |
| **비고** | 기존 Recharts 차트 컴포넌트 재활용, PDF는 fpdf2(이미 설치됨) 사용 |

#### FR-08: 분석 실행 방식 (수동 + 자동)

| 항목 | 내용 |
|------|------|
| **설명** | 수동 버튼 클릭 분석 + 자동 배치 분석 모두 지원 |
| **수동** | 대시보드에서 "분석 실행" 버튼 클릭 → 즉시 분석 실행 |
| **자동** | 신규 리뷰가 N건 이상 누적 시 또는 설정된 주기(일간/주간)에 자동 실행 |
| **비고** | 기본값은 수동, 설정 페이지에서 자동 배치 ON/OFF 전환 가능 |

### 2.2 Non-Functional Requirements

| ID | 항목 | 요구사항 |
|----|------|---------|
| NFR-01 | **LLM 비용 최소화** | 1회 호출로 감성+키워드+요약 동시 처리. 배치 분석 시 리뷰 10~20개씩 묶어서 호출 |
| NFR-02 | **LLM 추상화** | 개발(Ollama 로컬) / 배포(OpenRouter 또는 RunPod) 환경을 .env로 전환 가능 |
| NFR-03 | **응답 시간** | 단건 분석 < 5초, 배치 분석(50건) < 30초 |
| NFR-04 | **학습 친화성** | RAG/임베딩을 LangChain 없이 직접 구현. 코드에 학습용 주석 포함 |
| NFR-05 | **데이터 시작** | Mock 데이터 50건으로 개발 시작, 추후 DB(shop_reviews) 연동으로 확장 |
| NFR-06 | **기존 코드 재활용** | ChromaDB(vectordb.py), RAG 패턴(rag.py), LLM 클라이언트(llm_client.py) 활용 |

---

## 3. Architecture Overview

### 3.1 시스템 구조

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ ReviewDashboard │  │ AnalysisPanel   │  │ ReportExport   │  │
│  │ (판매자용)       │  │ (RAG 검색/질의)  │  │ (PDF 다운로드)  │  │
│  └────────┬────────┘  └────────┬────────┘  └───────┬────────┘  │
│           └──────────────┬─────┘───────────────────┘            │
│                          ↓ REST API                             │
├─────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI)                                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Review Analysis API                     │   │
│  │  POST /api/v1/reviews/analyze      (수동 분석 실행)      │   │
│  │  GET  /api/v1/reviews/analysis     (분석 결과 조회)      │   │
│  │  POST /api/v1/reviews/search       (RAG 의미 검색)      │   │
│  │  GET  /api/v1/reviews/trends       (트렌드 데이터)       │   │
│  │  GET  /api/v1/reviews/report/pdf   (PDF 리포트 다운로드)  │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           ↓                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐    │
│  │ ReviewRAG    │  │ LLMClient    │  │ TrendDetector     │    │
│  │ Service      │  │ (추상화)      │  │ (통계 기반)        │    │
│  │              │  │              │  │                   │    │
│  │ - embed      │  │ - Ollama     │  │ - 이동평균         │    │
│  │ - search     │  │ - OpenRouter │  │ - 이상탐지         │    │
│  │ - analyze    │  │ - (RunPod)   │  │ - 주간/월간 집계   │    │
│  └──────┬───────┘  └──────┬───────┘  └───────────────────┘    │
│         ↓                  ↓                                    │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │  ChromaDB    │  │  LLM API     │                            │
│  │  (로컬 벡터DB)│  │  (로컬/클라우드)│                            │
│  │  - reviews   │  │              │                            │
│  │    collection│  │              │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 RAG 파이프라인 상세

```
[리뷰 저장 흐름]
리뷰 텍스트 → ChromaDB.add() → 내장 임베딩 모델 → 벡터 저장
                                (all-MiniLM-L6-v2)   (로컬, 비용 0원)

[분석 흐름]
분석 요청 → ChromaDB.query() → 관련 리뷰 N개 검색
                ↓
         검색된 리뷰 + 프롬프트 → LLM 1회 호출
                ↓
         JSON 응답 파싱 → { 감성분석, 키워드, 요약 } 동시 반환

[트렌드 흐름]
저장된 분석 결과 → 주간/월간 집계 → 이동평균 계산 → 이상 탐지
                                                  (LLM 호출 없음)
```

### 3.3 LLM 추상화 클라이언트

```python
# 환경변수로 전환 (.env)
LLM_PROVIDER=ollama          # 개발 환경
# LLM_PROVIDER=openrouter    # 배포 A: GPU 없는 서버
# LLM_PROVIDER=ollama_remote # 배포 B: RunPod GPU

# 인터페이스
class BaseLLMClient(ABC):
    async def generate(prompt, system) -> str
    async def chat(messages) -> str

class OllamaClient(BaseLLMClient):      # 로컬 Ollama
class OpenRouterClient(BaseLLMClient):   # 클라우드 API
class RemoteOllamaClient(BaseLLMClient): # RunPod 원격 Ollama
```

---

## 4. Data Model

### 4.1 ChromaDB Collection: `reviews`

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 리뷰 고유 ID (예: `review-001`) |
| `document` | string | 리뷰 텍스트 (임베딩 대상) |
| `metadata.product_id` | int | 상품 ID |
| `metadata.rating` | int | 평점 (1~5) |
| `metadata.platform` | string | 플랫폼 (네이버스마트스토어, 쿠팡) |
| `metadata.date` | string | 리뷰 작성일 (YYYY-MM-DD) |
| `metadata.sentiment` | string | 분석된 감성 (분석 후 업데이트) |
| `metadata.analyzed_at` | string | 분석 수행 일시 |

### 4.2 PostgreSQL 테이블 (분석 결과 저장)

```sql
-- 분석 실행 기록
CREATE TABLE review_analyses (
    id SERIAL PRIMARY KEY,
    analysis_type VARCHAR(20),      -- 'manual' | 'batch'
    target_scope VARCHAR(50),       -- 'all' | 'product:{id}' | 'platform:{name}'
    review_count INTEGER,           -- 분석 대상 리뷰 수
    sentiment_summary JSONB,        -- { positive: n, negative: n, neutral: n }
    keywords JSONB,                 -- [{ word, count, sentiment }]
    summary TEXT,                   -- LLM 생성 요약
    trends JSONB,                   -- 트렌드 데이터
    anomalies JSONB,                -- 이상 탐지 결과
    llm_provider VARCHAR(20),       -- 사용된 LLM (ollama, openrouter)
    llm_model VARCHAR(50),          -- 사용된 모델명
    processing_time_ms INTEGER,     -- 처리 소요 시간
    created_at TIMESTAMP DEFAULT NOW()
);

-- 개별 리뷰 감성 분석 결과 캐시
CREATE TABLE review_sentiments (
    id SERIAL PRIMARY KEY,
    review_id INTEGER REFERENCES shop_reviews(id),
    sentiment VARCHAR(10),          -- positive | negative | neutral
    score FLOAT,                    -- -1.0 ~ 1.0
    reason TEXT,                    -- 판단 근거
    keywords TEXT[],                -- 추출된 키워드
    analyzed_at TIMESTAMP DEFAULT NOW()
);
```

---

## 5. API Design

### 5.1 리뷰 분석 API

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| POST | `/api/v1/reviews/analyze` | 분석 실행 (수동/배치) | 판매자/관리자 |
| GET | `/api/v1/reviews/analysis` | 최신 분석 결과 조회 | 판매자/관리자 |
| GET | `/api/v1/reviews/analysis/{id}` | 특정 분석 결과 상세 | 판매자/관리자 |
| POST | `/api/v1/reviews/search` | RAG 의미 검색 | 판매자/관리자 |
| GET | `/api/v1/reviews/trends` | 트렌드/이상 탐지 데이터 | 판매자/관리자 |
| GET | `/api/v1/reviews/report/pdf` | PDF 리포트 다운로드 | 관리자 |
| POST | `/api/v1/reviews/embed` | 리뷰 임베딩 저장 (수동) | 관리자 |
| GET | `/api/v1/reviews/settings` | 자동 분석 설정 조회 | 판매자/관리자 |
| PUT | `/api/v1/reviews/settings` | 자동 분석 설정 변경 | 관리자 |

### 5.2 주요 API 상세

#### POST `/api/v1/reviews/analyze`

```json
// Request
{
  "scope": "all",                    // "all" | "product:123" | "platform:네이버"
  "analysis_types": ["sentiment", "keywords", "summary"],
  "batch_size": 20                   // LLM 1회 호출당 리뷰 수
}

// Response
{
  "analysis_id": 1,
  "status": "completed",
  "review_count": 50,
  "sentiment_summary": {
    "positive": 35, "negative": 8, "neutral": 7, "total": 50
  },
  "keywords": [
    { "word": "당도", "count": 12, "sentiment": "positive" },
    { "word": "포장", "count": 9, "sentiment": "negative" }
  ],
  "summary": {
    "overall": "전반적으로 과일 품질에 대한 만족도가 높으나...",
    "positives": ["당도와 신선도에 대한 긍정적 반응이 다수"],
    "negatives": ["포장 파손 및 배송 중 멍 발생 불만"],
    "suggestions": ["완충재 보강", "당도 Brix 표기 도입"]
  },
  "processing_time_ms": 3200,
  "llm_provider": "ollama",
  "llm_model": "llama3"
}
```

#### POST `/api/v1/reviews/search`

```json
// Request
{
  "query": "포장이 별로라는 리뷰",
  "top_k": 10,
  "filters": {
    "platform": "네이버스마트스토어",
    "rating_max": 3,
    "date_from": "2026-03-01"
  }
}

// Response
{
  "results": [
    {
      "review_id": "review-023",
      "text": "포장이 엉망이에요. 딸기가 다 으깨져서 왔어요.",
      "similarity": 0.92,
      "rating": 1,
      "platform": "네이버스마트스토어",
      "date": "2026-03-10"
    }
  ],
  "total": 8
}
```

---

## 6. Implementation Plan

### 6.1 구현 단계

| 단계 | 모듈 | 내용 | 핵심 학습 포인트 |
|:----:|------|------|-----------------|
| **1** | ReviewEmbedding | 리뷰 → ChromaDB 임베딩 저장 | 벡터 임베딩이란? 코사인 유사도란? |
| **2** | ReviewRAGSearch | 자연어 질의 → 유사 리뷰 검색 | RAG의 Retrieval 단계, 메타데이터 필터링 |
| **3** | ReviewAnalyzer | 감성분석 + 키워드 + 요약 (LLM) | 프롬프트 엔지니어링, JSON 파싱 |
| **4** | LLMClientAbstract | LLM 추상화 (Ollama/OpenRouter) | 추상 클래스, 팩토리 패턴 |
| **5** | TrendDetector | 트렌드/이상 탐지 (통계 기반) | 이동평균, 표준편차, 이상 탐지 |
| **6** | ReviewAnalysisAPI | FastAPI 엔드포인트 | API 설계, 비동기 처리 |
| **7** | Dashboard UI | 프론트엔드 대시보드 연동 | 기존 ReviewsPage 실제 API 연동 |
| **8** | ReportGenerator | PDF 리포트 생성 | fpdf2 활용 |
| **9** | AutoBatch | 자동 배치 분석 (스케줄러) | 배경 작업, 설정 관리 |

### 6.2 LLM 통합 프롬프트 전략 (비용 최소화)

```
[단일 프롬프트로 3가지 분석 동시 수행]

시스템: 당신은 농산물 리뷰 분석 전문가입니다.
프롬프트:
  다음 리뷰들을 분석하여 아래 JSON 형식으로 반환하세요.
  
  리뷰:
  1. "딸기가 정말 달고 맛있어요" (★5, 네이버)
  2. "포장이 엉망이에요" (★1, 쿠팡)
  ...
  
  반환 형식:
  {
    "sentiments": [{ "id": 1, "sentiment": "positive", "score": 0.9 }, ...],
    "keywords": [{ "word": "당도", "count": 3, "sentiment": "positive" }, ...],
    "summary": { "overall": "...", "positives": [...], "negatives": [...] }
  }
```

이 방식으로 **LLM 1회 호출 = 감성분석 + 키워드 + 요약** 동시 처리.

---

## 7. Technology Stack

| 구분 | 기술 | 비고 |
|------|------|------|
| 벡터DB | ChromaDB 1.5.5 | 이미 설치됨, 내장 임베딩 모델 사용 |
| LLM (개발) | Ollama (llama3) | 로컬 실행, 비용 0원 |
| LLM (배포 A) | OpenRouter API (GPT-5-nano) | GPU 없는 서버용, 저비용 |
| LLM (배포 B) | Ollama on RunPod | GPU 서버 원격 실행 |
| 백엔드 | FastAPI + SQLAlchemy | 기존 스택 활용 |
| 프론트엔드 | React + Recharts | 기존 ReviewsPage 확장 |
| PDF 생성 | fpdf2 2.8.0 | 이미 설치됨 |
| 트렌드 분석 | Python 내장 (statistics) | 외부 라이브러리 불필요 |

---

## 8. File Structure (예상)

```
backend/app/
├── api/
│   └── review_analysis.py          # API 라우터 (신규)
├── core/
│   ├── vectordb.py                  # ChromaDB 클라이언트 (기존)
│   ├── review_rag.py                # 리뷰 RAG 서비스 (신규)
│   ├── review_analyzer.py           # 감성분석/키워드/요약 (신규)
│   ├── trend_detector.py            # 트렌드/이상 탐지 (신규)
│   ├── llm_client_base.py           # LLM 추상화 클라이언트 (신규)
│   └── report_generator.py          # PDF 리포트 생성 (신규)
├── models/
│   └── review_analysis.py           # SQLAlchemy 모델 (신규)
├── schemas/
│   └── review_analysis.py           # Pydantic 스키마 (신규)
└── main.py                          # 라우터 등록 (수정)

frontend/src/
├── modules/reviews/
│   ├── ReviewsPage.tsx              # 대시보드 (기존 수정)
│   ├── RAGSearchPanel.tsx           # RAG 검색 패널 (신규)
│   └── AnalysisSettingsModal.tsx    # 자동분석 설정 (신규)
├── hooks/
│   └── useReviewAnalysis.ts         # 분석 API 훅 (신규)
└── types/
    └── index.ts                     # 타입 확장 (수정)
```

---

## 9. Risk & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|:------:|:-----------:|------------|
| Ollama 로컬 모델 정확도 부족 | 중 | 중 | 프롬프트 최적화, 정확도 80% 미달 시 OpenRouter 폴백 |
| LLM 응답 JSON 파싱 실패 | 중 | 중 | JSON 스키마 명시 + 재시도 로직 (최대 2회) |
| ChromaDB 대량 데이터 성능 | 하 | 하 | 현재 규모(수백~수천 건)에서는 문제 없음 |
| LLM API 비용 초과 | 중 | 하 | 배치 처리 + 결과 캐싱 + 일일 호출 한도 설정 |
| 배포 환경 GPU 미확정 | 중 | 중 | LLM 추상화로 환경 전환 대비 완료 |
| Mock→실제DB 전환 시 이슈 | 하 | 중 | 데이터 인터페이스 통일, 단계적 전환 |

---

## 10. Success Criteria

| ID | 기준 | 측정 방법 |
|----|------|----------|
| SC-01 | 리뷰 임베딩 → ChromaDB 저장 → 의미 검색이 동작한다 | "포장 불만" 검색 시 관련 리뷰 반환 확인 |
| SC-02 | 감성분석 정확도 80% 이상 | Mock 리뷰 50건 수동 라벨 대비 일치율 |
| SC-03 | 1회 LLM 호출로 감성+키워드+요약 동시 반환 | API 응답에 3가지 결과 포함 확인 |
| SC-04 | LLM 추상화로 Ollama↔OpenRouter 전환 가능 | .env 변경만으로 동작 확인 |
| SC-05 | 트렌드 차트와 이상 탐지 알림이 대시보드에 표시 | UI에서 주간 추이 + 이상 탐지 배지 확인 |
| SC-06 | PDF 리포트 다운로드 가능 | 분석 결과가 포함된 PDF 파일 생성 확인 |
| SC-07 | 자동 배치 분석이 설정에 따라 실행 | N건 누적 시 자동 분석 트리거 확인 |

---

## 11. Glossary

| 용어 | 설명 |
|------|------|
| **RAG** | Retrieval-Augmented Generation. 관련 문서를 먼저 검색(Retrieval)한 후 LLM에게 전달하여 답변을 생성(Generation)하는 패턴 |
| **임베딩 (Embedding)** | 텍스트를 고차원 벡터(숫자 배열)로 변환하는 것. 의미가 비슷한 텍스트는 벡터 공간에서 가까이 위치 |
| **ChromaDB** | 오픈소스 벡터 데이터베이스. 텍스트를 자동으로 임베딩하여 저장하고 유사도 검색 지원 |
| **코사인 유사도** | 두 벡터 간의 각도를 이용한 유사도 측정. 1에 가까울수록 유사, 0에 가까울수록 무관 |
| **LLM** | Large Language Model. 대규모 언어 모델 (예: llama3, GPT-5-nano) |
| **배치 분석** | 여러 리뷰를 한번에 묶어서 분석하는 방식. LLM 호출 횟수를 줄여 비용 절감 |
| **트렌드 탐지** | 시계열 데이터에서 증가/감소 추세를 파악하는 것 |
| **이상 탐지 (Anomaly Detection)** | 정상 패턴에서 크게 벗어난 데이터 포인트를 자동으로 발견하는 것 |
