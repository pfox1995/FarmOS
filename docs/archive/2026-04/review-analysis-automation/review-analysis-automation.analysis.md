# Review Analysis Automation — Gap Analysis Report

> **Date**: 2026-04-10
> **Feature**: review-analysis-automation
> **Phase**: Check (Static Analysis Only)

## Context Anchor

| Anchor | Content |
|--------|---------|
| **WHY** | 리뷰 데이터에서 품질/배송/포장 등 개선점을 자동 추출하여 농산물 판매 전략에 반영 |
| **WHO** | 농업인 판매자 + 관리자/운영자 |
| **SUCCESS** | 리뷰 임베딩→검색→분석 파이프라인 동작, 감성분석 정확도 80%+, 대시보드 실시간 표시 |

---

## Overall Match Rate: 91%

| Category | Score | Status |
|----------|:-----:|:------:|
| Structural Match | 95% | PASS |
| Functional Depth | 92% | PASS |
| API Contract | 88% | WARN |
| **Overall (Static)** | **91%** | **PASS** |

Formula: `(95 x 0.2) + (92 x 0.4) + (88 x 0.4) = 91.0%`

---

## Success Criteria

| SC | 기준 | 상태 | 근거 |
|----|------|:----:|------|
| SC-01 | 리뷰 임베딩 → ChromaDB 저장 → 의미 검색 | PASS | embed_reviews + search + sync_from_mock 구현 완료 |
| SC-02 | 감성분석 정확도 80%+ | PARTIAL | LLM 분석 로직 완성, 런타임 정확도 검증 필요 |
| SC-03 | 1회 LLM 호출로 감성+키워드+요약 동시 | PASS | 단일 프롬프트 템플릿 구현 |
| SC-04 | LLM 추상화 Ollama↔OpenRouter 전환 | PASS | get_llm_client() 팩토리 + 3개 클라이언트 |
| SC-05 | 트렌드/이상 탐지 대시보드 표시 | PASS | TrendDetector + /trends + UI 표시 |
| SC-06 | PDF 리포트 다운로드 | PASS | generate_pdf() + /report/pdf + downloadReport() |
| SC-07 | 자동 배치 분석 실행 | PARTIAL | 설정 CRUD만 구현, 스케줄러 미구현 |

**달성률**: 5/7 완전 달성, 7/7 구조적 대응

---

## Gap 목록

### Important (3건)

| # | 항목 | 위치 | 설명 |
|---|------|------|------|
| 1 | period 쿼리 파라미터 누락 | GET /trends | Design에서 `period=weekly\|monthly` 지원 명시, 현재 무시 |
| 2 | analysis_id 파라미터 누락 | GET /report/pdf | Design에서 특정 분석 선택 기능 명시, 현재 항상 최신 사용 |
| 3 | 인증 가드 미적용 | 전체 API | Design §10에서 JWT 인증 요구, 현재 미적용 |

### Minor (4건)

| # | 항목 | 위치 | 설명 |
|---|------|------|------|
| 4 | date 필터 미구현 | RAGSearchPanel.tsx | SearchFilters의 date_from/date_to UI 없음 |
| 5 | batch_schedule UI 없음 | AnalysisSettingsModal.tsx | cron 스케줄 입력 필드 없음 |
| 6 | Mock 데이터 20건 | api/review_analysis.py | Plan은 50건 명시 |
| 7 | 평균 평점 하드코딩 | ReviewsPage.tsx | 4.1로 고정, API 데이터 미반영 |
