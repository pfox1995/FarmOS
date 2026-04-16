# ai/

AI 기능 모음. 크게 **유틸리티**와 **에이전트 서브패키지**로 나뉩니다.

## 파일

| 파일 | 역할 |
|------|------|
| `embeddings.py` | 임베딩 함수 팩토리 — `EMBED_PROVIDER` 설정에 따라 provider 선택 |
| `llm_client.py` | Utility LLM 클라이언트 — 리포트 생성·비용 분류 전용. 챗봇 에이전트와 무관 |
| `rag.py` | ChromaDB 검색 서비스 — `retrieve()` / `retrieve_multiple()`로 관련 문서 반환 |
| `seed_rag.py` | ChromaDB 초기 데이터 적재 스크립트. JSON 및 PDF/DOCX를 파싱해 컬렉션에 upsert |

## 서브패키지

| 디렉터리 | 역할 |
|----------|------|
| `agent/` | tool_use 에이전트 전체 (executor, 도구, 클라이언트, 프롬프트) |
| `data/` | RAG JSON 원본 데이터 (`faq.json`, `storage_guide.json`, `season_info.json`) |
| `docs/` | 정책 문서 PDF/DOCX — gitignore 처리, 로컬에 직접 배치 필요 |

## ChromaDB 컬렉션

```
faq / storage_guide / season_info          ← JSON (ai/data/)
payment_policy / delivery_policy /
return_policy / quality_policy /           ← PDF/DOCX (ai/docs/)
service_policy / membership_policy
```

---

## 팀원 셋업 가이드

### 1단계 — 임베딩 provider 선택

`.env`에서 본인 환경에 맞는 옵션을 선택합니다.
**시딩과 서버 실행 시 반드시 동일한 provider + model을 사용해야 합니다.**

**OpenRouter 키가 있는 경우 (권장)**
```env
EMBED_PROVIDER=openrouter
EMBED_MODEL=openai/text-embedding-3-small
# PRIMARY_LLM_API_KEY를 자동으로 재사용 — 추가 키 불필요
```

**Ollama가 설치된 경우**
```env
EMBED_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=embeddinggemma:latest
```

**둘 다 없는 경우 — 로컬 실행 (API 키·서버 불필요)**
```env
EMBED_PROVIDER=sentence_transformers
EMBED_MODEL=jhgan/ko-sroberta-multitask
```
```bash
uv add sentence-transformers   # 최초 1회
```
> 첫 실행 시 HuggingFace에서 모델을 자동 다운로드합니다 (~400MB).

### 2단계 — 정책 문서 배치

`ai/docs/` 폴더에 정책 문서(PDF/DOCX)를 넣습니다.
폴더가 없으면 직접 생성하세요 (gitignore 처리되어 있습니다).

```
ai/docs/
├── 01_주문및결제정책.pdf
├── 02_배송정책.docx
└── ...
```

### 3단계 — 시딩

```bash
uv run python ai/seed_rag.py

# 시딩 + 검색 검증 한번에
uv run python scripts/seed_and_verify.py
```
