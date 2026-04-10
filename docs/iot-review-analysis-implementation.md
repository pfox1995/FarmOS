# Review Analysis Automation — 구현 정리 문서

> **작성일**: 2026-04-10
> **작성자**: clover0309
> **PDCA Match Rate**: 96%
> **상태**: 구현 완료 (아카이브 완료)

---

## 1. 개요

FarmOS 쇼핑몰의 리뷰 데이터를 **RAG/임베딩 기반으로 자동 분석**하는 시스템.
ChromaDB에 리뷰를 벡터로 저장하고, 의미 검색을 통해 관련 리뷰를 추출한 뒤,
LLM으로 감성분석/키워드추출/요약을 수행한다.

### 핵심 특징

- **RAG 직접 구현**: LangChain 없이 ChromaDB + LLM 직접 연동
- **LLM 추상화**: .env 설정만으로 Ollama(로컬) / OpenRouter(클라우드) / RunPod(원격) 전환
- **1회 LLM 호출 = 3가지 분석**: 감성분석 + 키워드추출 + 요약을 단일 프롬프트로 동시 처리
- **비용 최소화**: ChromaDB 내장 임베딩(비용 0원) + 배치 처리로 LLM 호출 횟수 최소화

---

## 2. 기술 스택

| 구분 | 기술 | 비고 |
|------|------|------|
| 벡터DB | ChromaDB 1.5.5 | 내장 임베딩 모델 (all-MiniLM-L6-v2) |
| LLM (개발) | Ollama (llama3) | 로컬 실행, 비용 0원 |
| LLM (배포 A) | OpenRouter API | GPU 없는 서버용 |
| LLM (배포 B) | Ollama on RunPod | GPU 서버 원격 실행 |
| 백엔드 | FastAPI + SQLAlchemy (asyncpg) | 기존 FarmOS 스택 |
| 프론트엔드 | React + Vite + Recharts | 기존 FarmOS 스택 |
| PDF 생성 | fpdf2 2.8.0 | 한글 폰트 지원 (맑은 고딕) |
| 트렌드 분석 | Python statistics (내장) | 이동평균 + 표준편차 기반 이상 탐지 |

---

## 3. 아키텍처

### 3.1 시스템 구조

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React + Vite, :5173)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ ReviewsPage  │  │RAGSearchPanel│  │SettingsModal  │ │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘ │
│         └──────────────┬───┘─────────────────┘          │
│              useReviewAnalysis.ts (Hook)                 │
└──────────────────┬──────────────────────────────────────┘
                   ↓  REST API (:8000)
┌──────────────────┴──────────────────────────────────────┐
│  Backend (FastAPI)                                       │
│  ┌─────────────────────────────────────────────────┐    │
│  │  api/review_analysis.py (8 endpoints, JWT 인증)  │    │
│  └───────────────────┬─────────────────────────────┘    │
│                      ↓                                   │
│  ┌────────────┐ ┌──────────────┐ ┌───────────────────┐ │
│  │review_rag  │ │review_analyzer│ │ trend_detector   │ │
│  │(ChromaDB)  │ │(LLM 분석)     │ │ (통계, LLM 불필요)│ │
│  └─────┬──────┘ └──────┬───────┘ └───────────────────┘ │
│        ↓               ↓                                 │
│  ┌──────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ChromaDB  │  │llm_client_base   │  │review_report  │ │
│  │(벡터DB)   │  │(Ollama/OpenRouter)│  │(PDF, fpdf2)   │ │
│  └──────────┘  └──────────────────┘  └───────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 3.2 RAG 파이프라인

```
[저장] 리뷰 텍스트 → ChromaDB.add() → 내장 임베딩 → 벡터 저장 (비용 0원)
[검색] 자연어 질의 → ChromaDB.query() → 코사인 유사도 → 상위 N개 반환
[분석] 검색된 리뷰 → LLM 1회 호출 → { 감성, 키워드, 요약 } JSON 반환
[탐지] 분석 결과 → 이동평균 + 표준편차 → 이상 탐지 (LLM 불필요)
```

### 3.3 LLM 추상화

```
.env: LLM_PROVIDER=ollama|openrouter|ollama_remote

get_llm_client()  ← 팩토리 함수
  ├─ OllamaClient        (로컬, http://localhost:11434)
  ├─ OpenRouterClient     (클라우드, https://openrouter.ai/api/v1)
  └─ RemoteOllamaClient   (RunPod, OllamaClient 상속)
```

---

## 4. 파일 구조

### 4.1 백엔드 (8개 파일)

```
backend/app/
├── api/
│   └── review_analysis.py       # API 라우터 (8 endpoints, JWT 인증)  ~340줄
├── core/
│   ├── llm_client_base.py       # LLM 추상화 (ABC + 3 클라이언트 + Factory)  ~230줄
│   ├── review_rag.py            # RAG: 임베딩 저장 + 의미 검색  ~220줄
│   ├── review_analyzer.py       # 감성분석 + 키워드 + 요약 (LLM)  ~220줄
│   ├── trend_detector.py        # 트렌드/이상 탐지 (통계)  ~200줄
│   ├── review_report.py         # PDF 리포트 생성 (fpdf2)  ~200줄
│   ├── config.py                # [수정] LLM 설정 7개 추가
│   └── vectordb.py              # [기존] ChromaDB 클라이언트
├── models/
│   └── review_analysis.py       # SQLAlchemy 모델 2개  ~45줄
├── schemas/
│   └── review_analysis.py       # Pydantic 스키마 14개  ~165줄
└── main.py                      # [수정] 라우터 등록 + 모델 import
```

### 4.2 프론트엔드 (5개 파일)

```
frontend/src/
├── hooks/
│   └── useReviewAnalysis.ts         # API 통신 훅 (8개 함수)  ~160줄
├── modules/reviews/
│   ├── ReviewsPage.tsx              # [수정] Mock→API 연동, 액션바, 이상탐지 알림  ~200줄
│   ├── RAGSearchPanel.tsx           # [신규] 자연어 의미 검색 + 필터  ~115줄
│   └── AnalysisSettingsModal.tsx    # [신규] 자동 분석 설정 모달  ~115줄
└── types/
    └── index.ts                     # [수정] 7개 분석 타입 추가
```

### 4.3 설정 파일 변경

```env
# .env에 추가할 항목
LLM_PROVIDER=ollama                     # ollama | openrouter | ollama_remote
LLM_MODEL=llama3
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_REMOTE_URL=                      # RunPod 사용 시
OPENROUTER_API_KEY=                     # OpenRouter 사용 시
REVIEW_ANALYSIS_BATCH_SIZE=20
REVIEW_ANALYSIS_MAX_RETRIES=2
```

---

## 5. API 엔드포인트

모든 엔드포인트는 JWT 인증(`farmos_token` 쿠키) 필요.

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/reviews/embed` | Mock 리뷰 50건을 ChromaDB에 임베딩 저장 |
| POST | `/api/v1/reviews/analyze` | LLM 감성분석 + 키워드 + 요약 실행 |
| GET | `/api/v1/reviews/analysis` | 최신 분석 결과 조회 |
| POST | `/api/v1/reviews/search` | RAG 의미 검색 (자연어 → 유사 리뷰) |
| GET | `/api/v1/reviews/trends?period=weekly` | 트렌드/이상 탐지 데이터 |
| GET | `/api/v1/reviews/report/pdf?analysis_id=N` | PDF 리포트 다운로드 |
| GET | `/api/v1/reviews/settings` | 자동 분석 설정 조회 |
| PUT | `/api/v1/reviews/settings` | 자동 분석 설정 변경 |

---

## 6. DB 테이블

```sql
-- 분석 실행 기록
CREATE TABLE review_analyses (
    id SERIAL PRIMARY KEY,
    analysis_type VARCHAR(20),          -- 'manual' | 'batch'
    target_scope VARCHAR(50),           -- 'all' | 'product:{id}' | 'platform:{name}'
    review_count INTEGER,
    sentiment_summary JSONB,            -- { positive, negative, neutral, total }
    keywords JSONB,                     -- [{ word, count, sentiment }]
    summary TEXT,                       -- JSON 문자열
    trends JSONB,
    anomalies JSONB,
    llm_provider VARCHAR(30),
    llm_model VARCHAR(50),
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 개별 리뷰 감성 캐시
CREATE TABLE review_sentiments (
    id SERIAL PRIMARY KEY,
    review_id VARCHAR(50),              -- ChromaDB 리뷰 ID
    sentiment VARCHAR(10),
    score FLOAT,
    reason TEXT,
    keywords JSONB,
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

> 참고: 테이블은 FastAPI 서버 시작 시 `init_db()`에서 자동 생성됩니다 (SQLAlchemy `Base.metadata.create_all`).

---

## 7. 테스트 방법

### 7.1 사전 준비

```bash
# 1. 백엔드 의존성 확인
cd backend
uv sync

# 2. PostgreSQL 실행 확인
# farmos DB가 있어야 함

# 3. Ollama 설치 및 실행 (LLM 분석 테스트 시 필요)
# https://ollama.ai 에서 설치
ollama serve                    # Ollama 서버 시작
ollama pull llama3              # llama3 모델 다운로드 (최초 1회)

# 4. 프론트엔드 의존성
cd frontend
npm install
```

### 7.2 백엔드 단위 테스트 (Ollama 없이 가능)

```bash
cd backend

# 1. 모듈 import 테스트
uv run python -c "
from app.core.llm_client_base import get_llm_client, OllamaClient, OpenRouterClient
from app.core.review_rag import ReviewRAG
from app.core.review_analyzer import ReviewAnalyzer
from app.core.trend_detector import TrendDetector
from app.core.review_report import ReviewReportGenerator
from app.models.review_analysis import ReviewAnalysis, ReviewSentiment
from app.schemas.review_analysis import AnalyzeRequest, SearchRequest
from app.api.review_analysis import router
print('All imports OK')
print(f'Router routes: {len(router.routes)}')
"

# 2. LLM 팩토리 테스트
uv run python -c "
from app.core.llm_client_base import get_llm_client
client = get_llm_client()
print(f'Provider: {client.provider_name}')
print(f'Model: {client.model}')
"

# 3. ChromaDB 임베딩 + 검색 테스트 (Ollama 불필요)
uv run python -c "
from app.core.review_rag import ReviewRAG

rag = ReviewRAG()
mock = [
    {'id': 'test-01', 'text': '딸기가 달고 맛있어요', 'rating': 5, 'platform': '네이버스마트스토어', 'date': '2026-03-01'},
    {'id': 'test-02', 'text': '포장이 엉망이에요', 'rating': 1, 'platform': '쿠팡', 'date': '2026-03-02'},
    {'id': 'test-03', 'text': '배송이 느려요', 'rating': 2, 'platform': '쿠팡', 'date': '2026-03-03'},
    {'id': 'test-04', 'text': '신선하고 아삭해요', 'rating': 5, 'platform': '네이버스마트스토어', 'date': '2026-03-04'},
]

added = rag.sync_from_mock(mock)
print(f'임베딩 저장: {added}건, 전체: {rag.get_count()}건')

# 의미 검색 테스트
results = rag.search('포장 관련 불만', top_k=3)
for r in results:
    print(f'  [{r[\"similarity\"]:.3f}] {r[\"text\"]}')

# 필터 검색 테스트
results = rag.search('불만', top_k=3, filters={'platform': '쿠팡', 'rating_max': 3})
for r in results:
    print(f'  [{r[\"similarity\"]:.3f}] {r[\"text\"]} (platform={r[\"metadata\"][\"platform\"]})')
"

# 4. 트렌드/이상 탐지 테스트 (LLM 불필요)
uv run python -c "
from app.core.trend_detector import TrendDetector

detector = TrendDetector()
trends = detector.generate_simple_trends([
    {'week': '1주차', 'positive': 7, 'negative': 2, 'neutral': 1},
    {'week': '2주차', 'positive': 9, 'negative': 2, 'neutral': 2},
    {'week': '3주차', 'positive': 10, 'negative': 2, 'neutral': 2},
    {'week': '4주차', 'positive': 9, 'negative': 2, 'neutral': 2},
    {'week': '5주차', 'positive': 5, 'negative': 8, 'neutral': 2},  # 부정 급증!
])

anomalies = detector.detect_anomalies(trends)
print(f'이상 탐지: {len(anomalies)}건')
for a in anomalies:
    print(f'  {a[\"message\"]}')
"

# 5. PDF 생성 테스트 (LLM 불필요)
uv run python -c "
from app.core.review_report import ReviewReportGenerator

gen = ReviewReportGenerator()
pdf = gen.generate_pdf({
    'sentiment_summary': {'positive': 35, 'negative': 8, 'neutral': 7, 'total': 50},
    'keywords': [
        {'word': 'sweetness', 'count': 12, 'sentiment': 'positive'},
        {'word': 'packaging', 'count': 9, 'sentiment': 'negative'},
    ],
    'summary': {
        'overall': 'Overall satisfaction is high.',
        'positives': ['High sweetness'],
        'negatives': ['Packaging issues'],
        'suggestions': ['Improve cushioning'],
    },
    'anomalies': [],
    'processing_time_ms': 3200,
    'llm_provider': 'OllamaClient',
    'llm_model': 'llama3',
})
print(f'PDF 생성 성공: {pdf.getbuffer().nbytes} bytes')
"
```

### 7.3 API 통합 테스트 (서버 실행 필요)

```bash
# 1. 백엔드 서버 시작
cd backend
uv run uvicorn app.main:app --reload --port 8000

# 2. 로그인 (쿠키 획득)
curl -s -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"id": "farmer01", "password": "farm1234"}'

# 3. 임베딩 저장
curl -s -b cookies.txt -X POST http://localhost:8000/api/v1/reviews/embed \
  -H "Content-Type: application/json" \
  -d '{"source": "mock"}' | python -m json.tool

# 4. RAG 의미 검색
curl -s -b cookies.txt -X POST http://localhost:8000/api/v1/reviews/search \
  -H "Content-Type: application/json" \
  -d '{"query": "포장 관련 불만", "top_k": 5}' | python -m json.tool

# 5. AI 분석 실행 (Ollama 실행 필요!)
curl -s -b cookies.txt -X POST http://localhost:8000/api/v1/reviews/analyze \
  -H "Content-Type: application/json" \
  -d '{"scope": "all", "batch_size": 20}' | python -m json.tool

# 6. 분석 결과 조회
curl -s -b cookies.txt http://localhost:8000/api/v1/reviews/analysis | python -m json.tool

# 7. 트렌드 조회
curl -s -b cookies.txt http://localhost:8000/api/v1/reviews/trends?period=weekly | python -m json.tool

# 8. PDF 다운로드
curl -s -b cookies.txt http://localhost:8000/api/v1/reviews/report/pdf -o report.pdf
# report.pdf 파일 확인

# 9. 설정 조회
curl -s -b cookies.txt http://localhost:8000/api/v1/reviews/settings | python -m json.tool

# 10. 설정 변경
curl -s -b cookies.txt -X PUT http://localhost:8000/api/v1/reviews/settings \
  -H "Content-Type: application/json" \
  -d '{"auto_batch_enabled": true, "default_batch_size": 30}' | python -m json.tool

# 11. 인증 없이 호출 (401 확인)
curl -s -X POST http://localhost:8000/api/v1/reviews/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' -w "\nHTTP Status: %{http_code}\n"
# → HTTP Status: 401 이어야 정상
```

### 7.4 프론트엔드 테스트

```bash
# 1. 빌드 테스트
cd frontend
npx tsc --noEmit            # TypeScript 타입 체크 (에러 없어야 함)
npx vite build              # 빌드 성공 확인

# 2. 개발 서버 실행
npm run dev                 # http://localhost:5173

# 3. 브라우저에서 확인
# - http://localhost:5173 접속 후 로그인
# - 리뷰 분석 페이지로 이동
# - "임베딩 저장" 버튼 클릭 → 성공 확인
# - "AI 분석 실행" 버튼 클릭 → 분석 결과 대시보드 표시 (Ollama 필요)
# - RAG 검색창에 "포장 불만" 입력 → 유사도 순 결과 표시
# - 설정(톱니바퀴) 클릭 → 배치 설정 변경 → 저장
# - "PDF 리포트" 버튼 클릭 → PDF 다운로드
```

### 7.5 Ollama 없이 테스트 가능한 범위

| 기능 | Ollama 필요? | 설명 |
|------|:-----------:|------|
| 임베딩 저장 (POST /embed) | **아니오** | ChromaDB 내장 임베딩 사용 |
| RAG 의미 검색 (POST /search) | **아니오** | ChromaDB 내장 모델로 검색 |
| 트렌드/이상 탐지 (GET /trends) | **아니오** | 순수 통계 기반 |
| PDF 리포트 (GET /report/pdf) | **아니오** | 저장된 분석 결과 기반 |
| 설정 CRUD (GET/PUT /settings) | **아니오** | 인메모리 저장 |
| **AI 분석 실행 (POST /analyze)** | **예** | LLM 호출 필요 |
| 분석 결과 조회 (GET /analysis) | **조건부** | 분석 실행 후에만 조회 가능 |

---

## 8. 주요 학습 포인트

### 8.1 RAG (Retrieval-Augmented Generation)

```
RAG = 검색(Retrieval) + 생성(Generation)

1. 왜 RAG?
   LLM에게 리뷰 500개를 매번 다 보내면 비용 폭증 + 토큰 한도 초과.
   RAG로 관련 리뷰 5~10개만 골라서 보내면 비용 1/50, 정확도는 오히려 향상.

2. 임베딩이란?
   텍스트를 숫자 배열(벡터)로 변환. 의미가 비슷하면 벡터도 가까움.
   "딸기가 달아요" → [0.12, -0.34, 0.56, ...]  (384차원)

3. 코사인 유사도?
   두 벡터 간 각도로 유사도 측정. 1.0=동일, 0.0=무관, -1.0=반대

4. ChromaDB 핵심 API
   collection.add(documents=[...])       # 텍스트 → 벡터 → 저장
   collection.query(query_texts=[...])   # 텍스트 → 벡터 → 유사도 검색
```

### 8.2 LLM 추상화 패턴

```python
# ABC (추상 클래스) + 팩토리 패턴
class BaseLLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt, system) -> str: ...

class OllamaClient(BaseLLMClient): ...
class OpenRouterClient(BaseLLMClient): ...

def get_llm_client() -> BaseLLMClient:  # .env 기반 선택
```

### 8.3 프롬프트 엔지니어링

```
핵심 원칙:
1. 역할 부여: "당신은 농산물 리뷰 분석 전문가입니다"
2. 출력 형식 명시: "반드시 JSON으로만 응답하세요"
3. JSON 외 텍스트 금지 명시
4. 1회 호출로 3가지 분석 동시 요청 → 비용 1/3
```

### 8.4 JSON 파싱 3단계 전략

```
LLM은 항상 완벽한 JSON을 반환하지 않으므로:
1단계: 직접 json.loads() 시도
2단계: ```json ... ``` 코드블록에서 추출
3단계: 첫 { ~ 마지막 } 사이 추출
실패 시: 최대 2회 재시도
```

---

## 9. 미구현 항목 (추후 작업)

| 항목 | 우선순위 | 설명 |
|------|:--------:|------|
| SC-02 런타임 검증 | Medium | Ollama 실행 후 감성분석 정확도 80%+ 측정 |
| 자동 배치 스케줄러 | Low | APScheduler 또는 BackgroundTasks로 주기적 자동 분석 |
| `GET /analysis/{id}` | Low | 특정 분석 ID로 조회 (현재 최신만) |
| DB 리뷰 연동 | Future | Mock → shop_reviews 테이블 직접 조회로 전환 |
| 다국어 리뷰 분석 | Future | 영문 리뷰 지원 (ChromaDB 임베딩은 다국어 지원) |

---

## 10. 환경별 배포 설정

### 개발 환경 (로컬)

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3
```

### 배포 A: GPU 없는 서버

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-your-key
OPENROUTER_MODEL=openai/gpt-4o-mini
```

### 배포 B: RunPod GPU 서버

```env
LLM_PROVIDER=ollama_remote
OLLAMA_REMOTE_URL=https://your-pod-id-11434.proxy.runpod.net
LLM_MODEL=llama3
```
