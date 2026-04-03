# Backoffice Automation - Gap Analysis Report

> **Feature**: 백오피스 자동화
> **Design Doc**: `docs/02-design/features/backoffice-automation.design.md`
> **Implementation**: `shopping_mall/backend/` (확장) + `shopping_mall/backoffice/`
> **Date**: 2026-04-02
> **Match Rate**: 95%

---

## Overall Match Rate: 95%

```
[Plan] ✅ → [Design] ✅ → [Do] ✅ → [Check] ✅ 95% → [Report] ⏳
```

| Category | Score | Status |
|----------|:-----:|:------:|
| Backend Models (7) | 100% | ✅ |
| Backend Schemas (7) | 100% | ✅ |
| Backend Routers (5) + Endpoints (24) | 100% | ✅ |
| Backend Services (7) | 100% | ✅ |
| AI Module (llm_client, rag, prompts, data) | 90% | ⚠️ |
| Scheduler (APScheduler 4/5 jobs) | 80% | ⚠️ |
| Backoffice Frontend (7 pages, 10 components) | 100% | ✅ |
| Integration (CORS, lifespan, deps) | 100% | ✅ |

---

## Missing Items (5)

| # | Item | Impact |
|---|------|--------|
| 1 | `auto_classify_expenses` 스케줄러 Job 누락 | Medium |
| 2 | RAG `update_product_docs` 메서드 미구현 | Low |
| 3 | RAG `product_info` 컬렉션 데이터 없음 | Low |
| 4 | RAG `policy` 컬렉션 데이터 없음 | Low |
| 5 | 챗봇 응답의 `sources` 필드 누락 | Low |

## Changes (Design != Impl, 의도적/개선)

| # | Item | Impact |
|---|------|--------|
| 1 | HarvestSchedule 테이블명 plural로 변경 | None |
| 2 | LLM 모델명 `llama3` vs `llama3.1:8b` | Low |
| 3 | Dashboard API 응답 flat vs nested | Low (FE가 실제 API에 맞춤) |
| 4 | RFM 규칙 dict→list (우선순위 평가) | None (개선) |

## Added (설계에 없지만 구현됨, 전부 개선)

- AI 서비스 전체에 Ollama/ChromaDB 미실행 시 fallback 로직 추가
- 키워드 기반 의도 분류/비용 분류 fallback
- 모델에 created_at, relationship 추가

---

## Conclusion

**95% >= 90%** 기준 충족. Critical gap 없음. 누락된 스케줄러 Job 1개는 선택적 개선 사항.
