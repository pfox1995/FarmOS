# Review Analysis Automation Design Document

> **Project**: FarmOS - Review Analysis Module
> **Version**: 0.1.0
> **Author**: clover0309
> **Date**: 2026-04-10
> **Architecture**: Option C — Pragmatic Balance
> **Status**: Draft

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

### 1.1 Architecture Decision

**Option C — Pragmatic Balance** 선택.

| 결정 | 근거 |
|------|------|
| LLM 추상화를 단일 파일로 구현 | 배포 환경 전환 필요 + 과도한 분리 불필요 |
| 모듈별 1파일 구조 | 학습 친화적: 파일 하나씩 구현하며 RAG 원리 이해 |
| 기존 vectordb.py 재활용 | ChromaDB 클라이언트 이미 검증됨, 중복 구현 불필요 |
| shopping_mall 코드 비의존 | backend/app/ 내에서 독립적으로 구현, 참고만 함 |

### 1.2 Design Principles

1. **1파일 = 1역할**: 각 파일이 하나의 명확한 책임을 가짐
2. **학습 순서 = 구현 순서**: 임베딩 → RAG 검색 → LLM 분석 → 트렌드 → API → UI
3. **비용 최소화**: LLM 1회 호출로 3가지 분석 동시 수행
4. **환경 독립**: .env 설정만으로 Ollama ↔ OpenRouter ↔ RunPod 전환

---

## 2. System Architecture

### 2.1 전체 구조도

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite, port 5173)                         │
│                                                             │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐ │
│  │ ReviewsPage  │  │ RAGSearchPanel│  │ AnalysisSettings │ │
│  │ (대시보드)    │  │ (의미검색)     │  │ Modal (설정)     │ │
│  └──────┬───────┘  └──────┬────────┘  └────────┬─────────┘ │
│         └────────────┬────┘────────────────────┘           │
│                      ↓                                      │
│              useReviewAnalysis.ts (API 훅)                   │
└─────────────────────┬───────────────────────────────────────┘
                      ↓ HTTP (REST API)
┌─────────────────────┴───────────────────────────────────────┐
│  Backend (FastAPI, port 8000)                                │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │  api/review_analysis.py (API Router)                │     │
│  │                                                    │     │
│  │  POST /api/v1/reviews/analyze                      │     │
│  │  POST /api/v1/reviews/search                       │     │
│  │  GET  /api/v1/reviews/analysis                     │     │
│  │  GET  /api/v1/reviews/trends                       │     │
│  │  GET  /api/v1/reviews/report/pdf                   │     │
│  │  POST /api/v1/reviews/embed                        │     │
│  │  GET/PUT /api/v1/reviews/settings                  │     │
│  └──────────────────┬─────────────────────────────────┘     │
│                     ↓                                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Core Services (1파일 = 1역할)                        │    │
│  │                                                     │    │
│  │  ┌──────────────────┐   ┌────────────────────┐     │    │
│  │  │  review_rag.py   │   │  review_analyzer.py│     │    │
│  │  │                  │   │                    │     │    │
│  │  │  ReviewRAG       │   │  ReviewAnalyzer    │     │    │
│  │  │  - embed_reviews │──→│  - analyze_batch   │     │    │
│  │  │  - search        │   │  - parse_response  │     │    │
│  │  │  - sync_from_mock│   │  (감성+키워드+요약) │     │    │
│  │  └────────┬─────────┘   └─────────┬──────────┘     │    │
│  │           │                       │                 │    │
│  │           ↓                       ↓                 │    │
│  │  ┌──────────────┐   ┌──────────────────────┐       │    │
│  │  │  vectordb.py │   │  llm_client_base.py  │       │    │
│  │  │  (기존)       │   │                      │       │    │
│  │  │  ChromaDB    │   │  BaseLLMClient (ABC) │       │    │
│  │  │  - get_client│   │  ├─ OllamaClient     │       │    │
│  │  │  - get_coll. │   │  ├─ OpenRouterClient │       │    │
│  │  └──────────────┘   │  ├─ RemoteOllamaClient│      │    │
│  │                     │  └─ get_llm_client()  │       │    │
│  │                     └──────────────────────┘       │    │
│  │                                                     │    │
│  │  ┌──────────────────┐   ┌────────────────────┐     │    │
│  │  │ trend_detector.py│   │  review_report.py  │     │    │
│  │  │                  │   │                    │     │    │
│  │  │ TrendDetector    │   │ ReviewReportGen    │     │    │
│  │  │ - weekly_stats   │   │ - generate_pdf     │     │    │
│  │  │ - detect_anomaly │   │ (fpdf2 활용)       │     │    │
│  │  │ (LLM 불필요)     │   │                    │     │    │
│  │  └──────────────────┘   └────────────────────┘     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────┐   ┌──────────────┐                        │
│  │  PostgreSQL   │   │  ChromaDB    │                        │
│  │  (분석 결과)   │   │  (벡터 저장)  │                        │
│  │  review_      │   │  "reviews"   │                        │
│  │  analyses     │   │  collection  │                        │
│  │  review_      │   │              │                        │
│  │  sentiments   │   │              │                        │
│  └──────────────┘   └──────────────┘                        │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 데이터 흐름

```
[흐름 1: 리뷰 임베딩 저장]
Mock 데이터 / DB 리뷰
    → review_rag.py: embed_reviews()
    → vectordb.py: get_collection("reviews")
    → ChromaDB.add(documents, metadatas, ids)
    → 내장 임베딩 모델이 자동 벡터 변환 (all-MiniLM-L6-v2)

[흐름 2: RAG 의미 검색]
사용자 질의 "포장 관련 불만"
    → review_rag.py: search(query, filters, top_k)
    → ChromaDB.query(query_texts, where, n_results)
    → 코사인 유사도 기반 상위 N개 리뷰 반환

[흐름 3: LLM 분석 (감성 + 키워드 + 요약)]
리뷰 배치 (RAG 결과 또는 전체)
    → review_analyzer.py: analyze_batch(reviews)
    → llm_client_base.py: get_llm_client().generate(prompt)
    → LLM 응답 (JSON) 파싱
    → { sentiments, keywords, summary } 반환

[흐름 4: 트렌드/이상 탐지]
저장된 분석 결과 (review_analyses 테이블)
    → trend_detector.py: detect_trends(period)
    → 주간/월간 집계 → 이동평균 → 편차 계산
    → { trends, anomalies } 반환 (LLM 호출 없음)

[흐름 5: PDF 리포트]
분석 결과 데이터
    → review_report.py: generate_pdf(analysis_data)
    → fpdf2로 PDF 생성
    → StreamingResponse로 다운로드
```

---

## 3. Module Design

### 3.1 llm_client_base.py — LLM 추상화 클라이언트

```python
"""LLM 클라이언트 추상화.

학습 포인트:
- ABC(Abstract Base Class)를 이용한 인터페이스 정의
- 팩토리 패턴으로 환경에 따른 클라이언트 생성
- .env 설정만으로 Ollama ↔ OpenRouter ↔ RunPod 전환
"""

from abc import ABC, abstractmethod
from app.core.config import settings

class BaseLLMClient(ABC):
    """LLM 클라이언트 인터페이스."""

    @abstractmethod
    async def generate(self, prompt: str, system: str = "") -> str:
        """텍스트 생성."""
        ...

    @abstractmethod
    async def chat(self, messages: list[dict]) -> str:
        """채팅 형식 생성."""
        ...


class OllamaClient(BaseLLMClient):
    """로컬 Ollama LLM 클라이언트.

    - 개발 환경에서 사용
    - 비용: 0원 (로컬 실행)
    - 모델: llama3 (기본)
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url
        self.model = model

    async def generate(self, prompt: str, system: str = "") -> str:
        # POST http://localhost:11434/api/generate
        ...

    async def chat(self, messages: list[dict]) -> str:
        # POST http://localhost:11434/api/chat
        ...


class OpenRouterClient(BaseLLMClient):
    """OpenRouter 클라우드 LLM 클라이언트.

    - 배포 환경 A (GPU 없는 서버)에서 사용
    - 비용: API 호출당 과금
    - 모델: openai/gpt-4o-mini (기본, 저비용)
    """

    def __init__(self, api_key: str, model: str = "openai/gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

    async def generate(self, prompt: str, system: str = "") -> str:
        # POST https://openrouter.ai/api/v1/chat/completions
        # Authorization: Bearer {api_key}
        ...

    async def chat(self, messages: list[dict]) -> str:
        ...


class RemoteOllamaClient(BaseLLMClient):
    """원격 Ollama 클라이언트 (RunPod 등).

    - 배포 환경 B (RunPod GPU)에서 사용
    - OllamaClient와 동일 프로토콜, URL만 다름
    """

    def __init__(self, base_url: str, model: str = "llama3"):
        self.base_url = base_url  # e.g., "https://xxx.runpod.io:11434"
        self.model = model

    # OllamaClient와 동일한 generate/chat 구현


def get_llm_client() -> BaseLLMClient:
    """환경변수 기반 LLM 클라이언트 팩토리.

    .env 설정:
        LLM_PROVIDER=ollama          → OllamaClient
        LLM_PROVIDER=openrouter      → OpenRouterClient
        LLM_PROVIDER=ollama_remote   → RemoteOllamaClient
    """
    provider = settings.LLM_PROVIDER  # .env에서 읽기

    if provider == "openrouter":
        return OpenRouterClient(api_key=settings.OPENROUTER_API_KEY)
    elif provider == "ollama_remote":
        return RemoteOllamaClient(base_url=settings.OLLAMA_REMOTE_URL)
    else:  # 기본값: ollama
        return OllamaClient()
```

**설정 추가 (.env)**:
```env
# LLM Provider 설정
LLM_PROVIDER=ollama                    # ollama | openrouter | ollama_remote
LLM_MODEL=llama3                       # 사용할 모델명

# OpenRouter (배포 A)
OPENROUTER_API_KEY=sk-or-xxx

# Remote Ollama (배포 B: RunPod)
OLLAMA_REMOTE_URL=https://xxx.runpod.io:11434
```

---

### 3.2 review_rag.py — RAG 서비스 (임베딩 + 검색)

```python
"""리뷰 RAG (Retrieval-Augmented Generation) 서비스.

학습 포인트:
- 임베딩: 텍스트를 벡터(숫자 배열)로 변환
- ChromaDB: add()로 저장, query()로 유사도 검색
- 메타데이터 필터: where 조건으로 플랫폼/평점/기간 필터링
- 코사인 유사도: 1에 가까울수록 의미가 유사
"""

from app.core.vectordb import get_collection

COLLECTION_NAME = "reviews"

class ReviewRAG:
    """리뷰 벡터 저장 및 의미 검색 서비스."""

    def __init__(self):
        self.collection = get_collection(COLLECTION_NAME)

    def embed_reviews(self, reviews: list[dict]) -> int:
        """리뷰를 ChromaDB에 임베딩하여 저장.

        Args:
            reviews: [{ id, text, rating, platform, date, product_id }]

        Returns:
            저장된 리뷰 수

        학습 포인트:
            ChromaDB.add()에 documents(텍스트)를 넣으면
            내장 임베딩 모델(all-MiniLM-L6-v2)이 자동으로
            벡터로 변환하여 저장합니다.
        """
        self.collection.add(
            documents=[r["text"] for r in reviews],
            metadatas=[{
                "product_id": r.get("product_id", 0),
                "rating": r["rating"],
                "platform": r["platform"],
                "date": r["date"],
            } for r in reviews],
            ids=[str(r["id"]) for r in reviews],
        )
        return len(reviews)

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[dict]:
        """자연어 질의로 유사 리뷰 검색.

        Args:
            query: 검색 질의 (예: "포장 관련 불만")
            top_k: 반환할 최대 결과 수
            filters: 메타데이터 필터 (platform, rating_min/max, date_from/to)

        Returns:
            [{ id, text, similarity, metadata }]

        학습 포인트:
            query_texts에 자연어를 넣으면 ChromaDB가
            내부에서 벡터로 변환 후 코사인 유사도 기반으로
            가장 가까운 문서를 찾아줍니다.
        """
        where_filter = self._build_where_filter(filters)

        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter if where_filter else None,
        )

        return self._format_results(results)

    def get_all_reviews(self, limit: int = 100) -> list[dict]:
        """저장된 전체 리뷰 조회 (분석용)."""
        results = self.collection.get(limit=limit)
        return self._format_get_results(results)

    def sync_from_mock(self, mock_reviews: list[dict]) -> int:
        """Mock 데이터를 ChromaDB에 동기화 (개발용).

        기존 데이터가 있으면 스킵, 없는 것만 추가.
        """
        existing = self.collection.get()
        existing_ids = set(existing["ids"]) if existing["ids"] else set()

        new_reviews = [r for r in mock_reviews if str(r["id"]) not in existing_ids]
        if not new_reviews:
            return 0

        return self.embed_reviews(new_reviews)

    def _build_where_filter(self, filters: dict | None) -> dict | None:
        """ChromaDB where 필터 구성.

        학습 포인트:
            ChromaDB의 where 필터는 메타데이터 기반 필터링입니다.
            $and, $or로 복합 조건을 만들 수 있습니다.
            벡터 유사도 검색 + 메타데이터 필터 = 정밀한 검색
        """
        if not filters:
            return None

        conditions = []

        if "platform" in filters:
            conditions.append({"platform": {"$eq": filters["platform"]}})
        if "rating_min" in filters:
            conditions.append({"rating": {"$gte": filters["rating_min"]}})
        if "rating_max" in filters:
            conditions.append({"rating": {"$lte": filters["rating_max"]}})

        if len(conditions) == 0:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}

    def _format_results(self, results: dict) -> list[dict]:
        """ChromaDB query 결과를 API 응답 형식으로 변환."""
        formatted = []
        if not results["ids"][0]:
            return formatted

        for i, doc_id in enumerate(results["ids"][0]):
            formatted.append({
                "id": doc_id,
                "text": results["documents"][0][i],
                "similarity": round(1 - results["distances"][0][i], 4),  # distance → similarity
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            })
        return formatted

    def _format_get_results(self, results: dict) -> list[dict]:
        """ChromaDB get 결과를 변환."""
        formatted = []
        if not results["ids"]:
            return formatted

        for i, doc_id in enumerate(results["ids"]):
            formatted.append({
                "id": doc_id,
                "text": results["documents"][i],
                "metadata": results["metadatas"][i] if results["metadatas"] else {},
            })
        return formatted
```

---

### 3.3 review_analyzer.py — LLM 분석 서비스

```python
"""리뷰 분석 서비스 (감성분석 + 키워드 추출 + 요약).

학습 포인트:
- 프롬프트 엔지니어링: 1회 LLM 호출로 3가지 분석 동시 수행
- JSON 응답 파싱: LLM 출력을 구조화된 데이터로 변환
- 배치 처리: 비용 최소화를 위해 여러 리뷰를 묶어서 분석
- 재시도 로직: JSON 파싱 실패 시 최대 2회 재시도
"""

import json
import logging
from app.core.llm_client_base import get_llm_client, BaseLLMClient

logger = logging.getLogger(__name__)

# 시스템 프롬프트
SYSTEM_PROMPT = """당신은 농산물 쇼핑몰 리뷰 분석 전문가입니다.
리뷰를 분석하여 반드시 유효한 JSON 형식으로만 응답하세요.
JSON 외의 텍스트는 포함하지 마세요."""

# 분석 프롬프트 템플릿
ANALYSIS_PROMPT_TEMPLATE = """다음 {count}개의 농산물 리뷰를 분석하세요.

리뷰 목록:
{reviews_text}

다음 JSON 형식으로 정확히 반환하세요:
{{
  "sentiments": [
    {{ "id": "리뷰ID", "sentiment": "positive|negative|neutral", "score": -1.0~1.0, "reason": "판단근거" }}
  ],
  "keywords": [
    {{ "word": "키워드", "count": 출현횟수, "sentiment": "positive|negative|neutral" }}
  ],
  "summary": {{
    "overall": "전체 요약 (2-3문장)",
    "positives": ["긍정 포인트1", "긍정 포인트2"],
    "negatives": ["부정 포인트1", "부정 포인트2"],
    "suggestions": ["개선 제안1", "개선 제안2"]
  }}
}}"""


class ReviewAnalyzer:
    """리뷰 분석기 — 1회 LLM 호출로 감성+키워드+요약 동시 처리."""

    def __init__(self, llm_client: BaseLLMClient | None = None):
        self.llm = llm_client or get_llm_client()

    async def analyze_batch(
        self,
        reviews: list[dict],
        batch_size: int = 20,
    ) -> dict:
        """리뷰 배치 분석.

        Args:
            reviews: [{ id, text, rating, platform }]
            batch_size: 1회 LLM 호출당 리뷰 수 (기본 20)

        Returns:
            {
                sentiments: [...],
                keywords: [...],
                summary: {...},
                sentiment_summary: { positive: n, negative: n, neutral: n, total: n }
            }

        학습 포인트:
            리뷰가 50개면 batch_size=20으로 3번 호출.
            각 배치 결과를 병합하여 최종 결과 생성.
            LLM 1회 호출 = 감성 + 키워드 + 요약 동시 처리 → 비용 1/3
        """
        all_sentiments = []
        all_keywords = {}
        batch_summaries = []

        # 배치 단위로 LLM 호출
        for i in range(0, len(reviews), batch_size):
            batch = reviews[i:i + batch_size]
            result = await self._analyze_single_batch(batch)

            if result:
                all_sentiments.extend(result.get("sentiments", []))
                self._merge_keywords(all_keywords, result.get("keywords", []))
                if result.get("summary"):
                    batch_summaries.append(result["summary"])

        # 감성 통계 집계
        sentiment_summary = self._calculate_sentiment_summary(all_sentiments)

        # 키워드 정렬 (빈도 내림차순)
        sorted_keywords = sorted(
            [{"word": w, **v} for w, v in all_keywords.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

        # 요약 병합 (배치가 여러 개면 마지막 배치 요약 사용)
        final_summary = batch_summaries[-1] if batch_summaries else {}

        return {
            "sentiments": all_sentiments,
            "keywords": sorted_keywords[:20],  # 상위 20개
            "summary": final_summary,
            "sentiment_summary": sentiment_summary,
        }

    async def _analyze_single_batch(self, reviews: list[dict]) -> dict | None:
        """단일 배치 LLM 분석 (재시도 포함).

        학습 포인트:
            LLM은 항상 완벽한 JSON을 반환하지 않습니다.
            마크다운 코드블록(```)으로 감싸거나 추가 텍스트를 넣을 수 있어서
            JSON 추출 로직이 필요합니다.
        """
        reviews_text = self._format_reviews_for_prompt(reviews)
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            count=len(reviews),
            reviews_text=reviews_text,
        )

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = await self.llm.generate(prompt, system=SYSTEM_PROMPT)
                return self._parse_json_response(response)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"LLM 응답 파싱 실패 (시도 {attempt + 1}): {e}")
                if attempt == max_retries:
                    logger.error("LLM 분석 최대 재시도 초과")
                    return None

    def _format_reviews_for_prompt(self, reviews: list[dict]) -> str:
        """리뷰를 LLM 프롬프트용 텍스트로 포맷."""
        lines = []
        for r in reviews:
            rating_stars = "★" * r.get("rating", 0)
            platform = r.get("platform", "")
            lines.append(f'{r["id"]}. "{r["text"]}" ({rating_stars}, {platform})')
        return "\n".join(lines)

    def _parse_json_response(self, response: str) -> dict:
        """LLM 응답에서 JSON 추출 및 파싱.

        학습 포인트:
            LLM 응답에서 JSON을 추출하는 3단계:
            1. 그대로 파싱 시도
            2. ```json ... ``` 코드블록에서 추출
            3. { ... } 패턴 찾기
        """
        # 1단계: 직접 파싱
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass

        # 2단계: 코드블록 추출
        if "```json" in response:
            start = response.index("```json") + 7
            end = response.index("```", start)
            return json.loads(response[start:end].strip())

        if "```" in response:
            start = response.index("```") + 3
            end = response.index("```", start)
            return json.loads(response[start:end].strip())

        # 3단계: { } 패턴 추출
        start = response.index("{")
        end = response.rindex("}") + 1
        return json.loads(response[start:end])

    def _calculate_sentiment_summary(self, sentiments: list[dict]) -> dict:
        """감성 분석 결과 통계 집계."""
        summary = {"positive": 0, "negative": 0, "neutral": 0, "total": len(sentiments)}
        for s in sentiments:
            sentiment = s.get("sentiment", "neutral")
            if sentiment in summary:
                summary[sentiment] += 1
        return summary

    def _merge_keywords(self, accumulated: dict, new_keywords: list[dict]):
        """여러 배치의 키워드를 병합."""
        for kw in new_keywords:
            word = kw.get("word", "")
            if word in accumulated:
                accumulated[word]["count"] += kw.get("count", 1)
            else:
                accumulated[word] = {
                    "count": kw.get("count", 1),
                    "sentiment": kw.get("sentiment", "neutral"),
                }
```

---

### 3.4 trend_detector.py — 트렌드/이상 탐지

```python
"""트렌드/이상 탐지 서비스 (통계 기반, LLM 불필요).

학습 포인트:
- 이동평균(Moving Average): 최근 N기간의 평균으로 추세 파악
- 표준편차(Standard Deviation): 데이터 변동폭 측정
- 이상 탐지: 이동평균 ± 2σ 벗어나면 이상(anomaly)으로 판정
"""

from statistics import mean, stdev
from datetime import datetime, timedelta


class TrendDetector:
    """감성 추이 및 이상 패턴 탐지기."""

    def __init__(self, anomaly_threshold: float = 2.0):
        self.anomaly_threshold = anomaly_threshold  # 표준편차 배수

    def calculate_weekly_trends(self, analyses: list[dict]) -> list[dict]:
        """주간 감성 추이 계산.

        Args:
            analyses: 날짜별 분석 결과 [{ date, sentiment_summary }]

        Returns:
            [{ week, positive_ratio, negative_ratio, neutral_ratio, total }]
        """
        # 주차별 그룹핑 → 감성 비율 계산
        ...

    def detect_anomalies(self, weekly_trends: list[dict]) -> list[dict]:
        """이상 패턴 탐지.

        학습 포인트:
            이동평균 대비 현재 값이 2σ 이상 벗어나면 이상으로 판정.
            예: 부정 리뷰 비율 평소 15%인데 이번주 40% → 이상 탐지
        """
        if len(weekly_trends) < 3:  # 최소 3주 데이터 필요
            return []

        anomalies = []
        negative_ratios = [w["negative_ratio"] for w in weekly_trends]

        for i in range(2, len(negative_ratios)):
            window = negative_ratios[max(0, i - 4):i]  # 최근 4주 윈도우
            avg = mean(window)
            std = stdev(window) if len(window) > 1 else 0

            current = negative_ratios[i]
            if std > 0 and (current - avg) / std > self.anomaly_threshold:
                anomalies.append({
                    "week": weekly_trends[i]["week"],
                    "type": "negative_spike",
                    "value": current,
                    "expected": avg,
                    "deviation": round((current - avg) / std, 2),
                    "message": f"부정 리뷰 비율 급증: {current:.0%} (평소 {avg:.0%})",
                })

        return anomalies

    def detect_keyword_surge(
        self,
        current_keywords: list[dict],
        previous_keywords: list[dict],
        threshold: float = 2.0,
    ) -> list[dict]:
        """키워드 급등 탐지.

        이전 분석 대비 특정 키워드 빈도가 threshold배 이상 증가 시 탐지.
        """
        prev_map = {kw["word"]: kw["count"] for kw in previous_keywords}
        surges = []

        for kw in current_keywords:
            prev_count = prev_map.get(kw["word"], 0)
            if prev_count > 0 and kw["count"] / prev_count >= threshold:
                surges.append({
                    "keyword": kw["word"],
                    "current_count": kw["count"],
                    "previous_count": prev_count,
                    "growth_rate": round(kw["count"] / prev_count, 1),
                    "sentiment": kw["sentiment"],
                })

        return surges
```

---

### 3.5 review_report.py — PDF 리포트 생성

```python
"""PDF 리포트 생성 서비스 (fpdf2 활용).

학습 포인트:
- fpdf2: 가볍고 의존성 없는 PDF 생성 라이브러리
- 한글 지원: 폰트 등록 필요 (NanumGothic 등)
"""

from fpdf import FPDF
from io import BytesIO


class ReviewReportGenerator:
    """리뷰 분석 PDF 리포트 생성기."""

    def generate_pdf(self, analysis_data: dict) -> BytesIO:
        """분석 결과를 PDF로 생성.

        포함 내용:
        1. 요약 (감성 비율, 총 리뷰 수)
        2. 감성 분석 상세
        3. 주요 키워드 (상위 10개)
        4. AI 인사이트 (요약 및 제안)
        5. 트렌드 (이상 탐지 포함)

        Returns:
            PDF 바이너리 데이터 (BytesIO)
        """
        pdf = FPDF()
        pdf.add_page()

        # 한글 폰트 등록 (시스템 폰트 경로)
        # pdf.add_font("NanumGothic", "", "path/to/NanumGothic.ttf", uni=True)

        # 1. 제목
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Review Analysis Report", ln=True, align="C")
        pdf.ln(10)

        # 2. 감성 요약 테이블
        self._add_sentiment_summary(pdf, analysis_data.get("sentiment_summary", {}))

        # 3. 키워드 목록
        self._add_keywords(pdf, analysis_data.get("keywords", []))

        # 4. AI 인사이트
        self._add_summary(pdf, analysis_data.get("summary", {}))

        # 5. 이상 탐지 알림
        self._add_anomalies(pdf, analysis_data.get("anomalies", []))

        output = BytesIO()
        pdf.output(output)
        output.seek(0)
        return output

    def _add_sentiment_summary(self, pdf: FPDF, summary: dict):
        """감성 비율 섹션."""
        ...

    def _add_keywords(self, pdf: FPDF, keywords: list[dict]):
        """주요 키워드 섹션."""
        ...

    def _add_summary(self, pdf: FPDF, summary: dict):
        """AI 인사이트 섹션."""
        ...

    def _add_anomalies(self, pdf: FPDF, anomalies: list[dict]):
        """이상 탐지 알림 섹션."""
        ...
```

---

## 4. API Design

### 4.1 엔드포인트 상세

#### POST `/api/v1/reviews/analyze` — 분석 실행

```python
@router.post("/analyze")
async def analyze_reviews(request: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """리뷰 분석 실행 (수동/배치).

    1. ChromaDB에서 대상 리뷰 조회 (scope에 따라 필터링)
    2. ReviewAnalyzer로 LLM 분석 실행
    3. TrendDetector로 트렌드/이상 탐지
    4. 결과를 review_analyses 테이블에 저장
    5. 개별 감성 결과를 review_sentiments에 캐시
    """
```

**Request Schema**:
```python
class AnalyzeRequest(BaseModel):
    scope: str = "all"                           # "all" | "product:{id}" | "platform:{name}"
    analysis_types: list[str] = ["sentiment", "keywords", "summary"]
    batch_size: int = Field(default=20, ge=5, le=50)
```

**Response Schema**:
```python
class AnalyzeResponse(BaseModel):
    analysis_id: int
    status: str                                  # "completed" | "failed"
    review_count: int
    sentiment_summary: SentimentSummary
    keywords: list[KeywordItem]
    summary: SummaryData
    anomalies: list[AnomalyAlert]
    processing_time_ms: int
    llm_provider: str
    llm_model: str
```

#### POST `/api/v1/reviews/search` — RAG 의미 검색

```python
@router.post("/search")
async def search_reviews(request: SearchRequest):
    """RAG 기반 의미 검색.

    자연어 질의를 벡터로 변환하여 유사 리뷰를 검색합니다.
    """
```

**Request Schema**:
```python
class SearchRequest(BaseModel):
    query: str                                    # "포장 관련 불만"
    top_k: int = Field(default=10, ge=1, le=50)
    filters: SearchFilters | None = None

class SearchFilters(BaseModel):
    platform: str | None = None
    rating_min: int | None = Field(default=None, ge=1, le=5)
    rating_max: int | None = Field(default=None, ge=1, le=5)
    date_from: str | None = None                  # YYYY-MM-DD
    date_to: str | None = None
```

#### GET `/api/v1/reviews/analysis` — 분석 결과 조회

```python
@router.get("/analysis")
async def get_latest_analysis(db: AsyncSession = Depends(get_db)):
    """최신 분석 결과 조회. 대시보드에서 사용."""
```

#### GET `/api/v1/reviews/trends` — 트렌드 데이터

```python
@router.get("/trends")
async def get_trends(period: str = "weekly", db: AsyncSession = Depends(get_db)):
    """트렌드 데이터 + 이상 탐지 결과 조회.

    period: "weekly" | "monthly"
    """
```

#### GET `/api/v1/reviews/report/pdf` — PDF 다운로드

```python
@router.get("/report/pdf")
async def download_report(analysis_id: int | None = None, db: AsyncSession = Depends(get_db)):
    """PDF 리포트 다운로드.

    analysis_id 지정 시 해당 분석, 미지정 시 최신 분석 기준.
    """
    return StreamingResponse(pdf_bytes, media_type="application/pdf")
```

#### POST `/api/v1/reviews/embed` — 임베딩 저장

```python
@router.post("/embed")
async def embed_reviews(source: str = "mock"):
    """리뷰 데이터를 ChromaDB에 임베딩 저장.

    source: "mock" (Mock 데이터) | "db" (shop_reviews 테이블)
    개발 초기에는 "mock"으로 시작, 추후 "db"로 전환.
    """
```

#### GET/PUT `/api/v1/reviews/settings` — 자동 분석 설정

```python
class AnalysisSettings(BaseModel):
    auto_batch_enabled: bool = False              # 자동 배치 ON/OFF
    batch_trigger_count: int = 10                 # N건 누적 시 자동 실행
    batch_schedule: str | None = None             # cron 표현식 (예: "0 9 * * 1" = 매주 월요일 9시)
    default_batch_size: int = 20
```

---

## 5. Data Model

### 5.1 Pydantic Schemas (schemas/review_analysis.py)

```python
from pydantic import BaseModel, Field
from datetime import datetime


class SentimentSummary(BaseModel):
    positive: int = 0
    negative: int = 0
    neutral: int = 0
    total: int = 0

class KeywordItem(BaseModel):
    word: str
    count: int
    sentiment: str  # "positive" | "negative" | "neutral"

class SummaryData(BaseModel):
    overall: str = ""
    positives: list[str] = []
    negatives: list[str] = []
    suggestions: list[str] = []

class SentimentResult(BaseModel):
    id: str
    sentiment: str
    score: float = Field(ge=-1.0, le=1.0)
    reason: str = ""

class AnomalyAlert(BaseModel):
    week: str
    type: str                # "negative_spike" | "keyword_surge"
    value: float
    expected: float
    deviation: float
    message: str

class TrendData(BaseModel):
    week: str
    positive_ratio: float
    negative_ratio: float
    neutral_ratio: float
    total: int

class SearchResult(BaseModel):
    id: str
    text: str
    similarity: float
    metadata: dict = {}
```

### 5.2 SQLAlchemy Models (models/review_analysis.py)

```python
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class ReviewAnalysis(Base):
    """분석 실행 기록."""
    __tablename__ = "review_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_type = Column(String(20))          # "manual" | "batch"
    target_scope = Column(String(50))           # "all" | "product:123"
    review_count = Column(Integer)
    sentiment_summary = Column(JSON)
    keywords = Column(JSON)
    summary = Column(Text)
    trends = Column(JSON, nullable=True)
    anomalies = Column(JSON, nullable=True)
    llm_provider = Column(String(20))
    llm_model = Column(String(50))
    processing_time_ms = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())


class ReviewSentiment(Base):
    """개별 리뷰 감성 분석 캐시."""
    __tablename__ = "review_sentiments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(Integer)                 # shop_reviews.id 참조
    sentiment = Column(String(10))
    score = Column(Float)
    reason = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)      # 추출된 키워드 배열
    analyzed_at = Column(DateTime, server_default=func.now())
```

---

## 6. Frontend Design

### 6.1 컴포넌트 구조

```
ReviewsPage.tsx (기존 수정)
├── SummaryCards           (감성 비율, 총 리뷰 수, 평균 평점, AI 인사이트 수)
├── SentimentPieChart      (Recharts PieChart — 기존 유지)
├── WeeklyTrendChart       (Recharts BarChart — API 연동으로 전환)
├── KeywordCloud           (키워드 시각화 — API 연동으로 전환)
├── AnomalyAlerts (신규)   (이상 탐지 알림 배너)
├── AIStrategies           (AI 판매 전략 — API 연동으로 전환)
├── RAGSearchPanel (신규)  (의미 검색 입력/결과)
├── ReviewList             (리뷰 목록 — 기존 유지)
├── AnalysisSettingsModal (신규) (자동 분석 설정)
└── AnalyzeButton (신규)   (수동 분석 실행 버튼)
```

### 6.2 RAGSearchPanel 컴포넌트

```tsx
// 신규 컴포넌트: 자연어로 리뷰를 의미 검색
interface RAGSearchPanelProps {
  onSearchResults: (results: SearchResult[]) => void;
}

function RAGSearchPanel({ onSearchResults }: RAGSearchPanelProps) {
  // 검색 입력 → POST /api/v1/reviews/search → 결과 표시
  // 필터: 플랫폼, 평점 범위, 기간
  // 유사도 점수와 함께 리뷰 카드 표시
}
```

### 6.3 useReviewAnalysis Hook

```tsx
// 신규 Hook: 리뷰 분석 API와 통신
function useReviewAnalysis() {
  return {
    // 분석 실행
    analyzeReviews: (scope, batchSize) => POST /api/v1/reviews/analyze,
    isAnalyzing: boolean,

    // 분석 결과 조회
    analysis: AnalysisData | null,
    isLoading: boolean,

    // RAG 검색
    searchReviews: (query, filters) => POST /api/v1/reviews/search,
    searchResults: SearchResult[],

    // 트렌드
    trends: TrendData[],
    anomalies: AnomalyAlert[],

    // PDF 다운로드
    downloadReport: () => GET /api/v1/reviews/report/pdf,

    // 설정
    settings: AnalysisSettings,
    updateSettings: (settings) => PUT /api/v1/reviews/settings,

    // 임베딩
    embedReviews: (source) => POST /api/v1/reviews/embed,
  };
}
```

---

## 7. Configuration

### 7.1 환경 변수 (.env)

```env
# === LLM Provider ===
LLM_PROVIDER=ollama                     # ollama | openrouter | ollama_remote
LLM_MODEL=llama3                        # 모델명

# Ollama (로컬, 개발용)
OLLAMA_BASE_URL=http://localhost:11434

# OpenRouter (클라우드, 배포 A)
OPENROUTER_API_KEY=sk-or-xxx
OPENROUTER_MODEL=openai/gpt-4o-mini

# Remote Ollama (RunPod, 배포 B)
OLLAMA_REMOTE_URL=https://xxx.runpod.io:11434

# === ChromaDB ===
CHROMA_DB_PATH=./chroma_data            # 벡터DB 저장 경로 (기존)

# === Review Analysis ===
REVIEW_ANALYSIS_BATCH_SIZE=20           # LLM 1회 호출당 리뷰 수
REVIEW_ANALYSIS_MAX_RETRIES=2           # JSON 파싱 실패 시 재시도 횟수
```

### 7.2 config.py 추가 설정

```python
# app/core/config.py에 추가
class Settings(BaseSettings):
    # ... 기존 설정 ...

    # LLM
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "llama3"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OLLAMA_REMOTE_URL: str = ""

    # Review Analysis
    REVIEW_ANALYSIS_BATCH_SIZE: int = 20
    REVIEW_ANALYSIS_MAX_RETRIES: int = 2
```

---

## 8. Test Plan

### 8.1 단위 테스트

| 테스트 | 대상 | 검증 내용 |
|--------|------|----------|
| test_embed_reviews | ReviewRAG.embed_reviews | Mock 리뷰 저장 후 ChromaDB collection count 확인 |
| test_search_reviews | ReviewRAG.search | "포장" 검색 시 포장 관련 리뷰가 상위 반환 |
| test_search_with_filter | ReviewRAG.search | 평점 필터 적용 시 조건 일치 확인 |
| test_parse_json_response | ReviewAnalyzer._parse_json | 일반 JSON, 코드블록, 혼합 텍스트 파싱 |
| test_sentiment_summary | ReviewAnalyzer._calculate | 감성 통계 집계 정확도 |
| test_trend_detection | TrendDetector.detect_anomalies | 부정 비율 급증 시 anomaly 반환 |
| test_keyword_surge | TrendDetector.detect_keyword_surge | 키워드 빈도 2배 이상 시 탐지 |
| test_llm_factory | get_llm_client | 환경변수별 올바른 클라이언트 반환 |

### 8.2 통합 테스트

| 테스트 | 흐름 | 검증 내용 |
|--------|------|----------|
| test_full_pipeline | embed → search → analyze | 임베딩 → 검색 → 분석까지 전체 파이프라인 |
| test_analyze_api | POST /analyze → GET /analysis | API 호출 → DB 저장 → 조회 정합성 |
| test_pdf_report | GET /report/pdf | PDF 생성 및 다운로드 확인 |

---

## 9. Error Handling

| 에러 상황 | 처리 방식 |
|----------|----------|
| Ollama 서버 미실행 | 연결 실패 시 에러 메시지 반환 + LLM_PROVIDER 전환 안내 |
| LLM 응답 JSON 파싱 실패 | 최대 2회 재시도 → 실패 시 partial 결과 반환 |
| ChromaDB 컬렉션 비어있음 | embed 먼저 실행 안내 메시지 |
| OpenRouter API 키 미설정 | 서버 시작 시 경고 로그 + 403 응답 |
| 배치 분석 중 일부 실패 | 성공한 배치 결과만 반환 + 실패 배치 로그 |

---

## 10. Security Considerations

| 항목 | 대응 |
|------|------|
| API 키 노출 | .env에만 저장, 절대 코드/응답에 포함하지 않음 |
| LLM Prompt Injection | 사용자 입력(검색 질의)은 리뷰 텍스트와 분리된 프롬프트 구조 |
| 대용량 요청 | batch_size 상한(50), top_k 상한(50) 설정 |
| 인증 | 기존 FarmOS 인증 체계 활용 (JWT) |

---

## 11. Implementation Guide

### 11.1 구현 순서

| 순서 | 파일 | 의존성 | 예상 규모 |
|:----:|------|--------|----------|
| 1 | `core/llm_client_base.py` | config.py | ~120줄 |
| 2 | `core/review_rag.py` | vectordb.py | ~100줄 |
| 3 | `core/review_analyzer.py` | llm_client_base.py | ~150줄 |
| 4 | `core/trend_detector.py` | 없음 (독립) | ~80줄 |
| 5 | `core/review_report.py` | 없음 (독립) | ~100줄 |
| 6 | `models/review_analysis.py` | database.py | ~40줄 |
| 7 | `schemas/review_analysis.py` | 없음 | ~60줄 |
| 8 | `api/review_analysis.py` | 1~7 모두 | ~150줄 |
| 9 | `frontend/hooks/useReviewAnalysis.ts` | 없음 | ~80줄 |
| 10 | `frontend/modules/reviews/RAGSearchPanel.tsx` | hook | ~100줄 |
| 11 | `frontend/modules/reviews/ReviewsPage.tsx` | hook, 기존 수정 | ~50줄 변경 |
| 12 | `frontend/modules/reviews/AnalysisSettingsModal.tsx` | hook | ~80줄 |

### 11.2 Module Map

| Module | 파일 | 역할 | 세션 |
|--------|------|------|:----:|
| **module-1** | llm_client_base.py | LLM 추상화 (Base+Ollama+OpenRouter+Factory) | 1 |
| **module-2** | review_rag.py + vectordb.py | RAG: 임베딩 저장 + 의미 검색 | 1 |
| **module-3** | review_analyzer.py | LLM 분석: 감성+키워드+요약 | 2 |
| **module-4** | trend_detector.py | 통계 기반 트렌드/이상 탐지 | 2 |
| **module-5** | review_report.py | PDF 리포트 생성 | 2 |
| **module-6** | models + schemas + api | DB 모델 + API 라우터 | 3 |
| **module-7** | 프론트엔드 전체 | Hook + UI 컴포넌트 + 기존 페이지 수정 | 4 |

### 11.3 Session Guide

| 세션 | 모듈 | 핵심 학습 포인트 | 명령어 |
|:----:|------|-----------------|--------|
| **Session 1** | module-1, module-2 | 임베딩/벡터DB/RAG 검색 원리 | `/pdca do review-analysis-automation --scope module-1,module-2` |
| **Session 2** | module-3, module-4, module-5 | 프롬프트 엔지니어링, 통계 분석, PDF 생성 | `/pdca do review-analysis-automation --scope module-3,module-4,module-5` |
| **Session 3** | module-6 | FastAPI 라우터, DB 모델, API 통합 | `/pdca do review-analysis-automation --scope module-6` |
| **Session 4** | module-7 | React 훅, UI 컴포넌트, API 연동 | `/pdca do review-analysis-automation --scope module-7` |

**권장**: Session 1에서 임베딩/RAG를 충분히 이해한 후 Session 2로 넘어가세요.
각 세션 사이에 학습 내용을 정리하면 효과적입니다.
