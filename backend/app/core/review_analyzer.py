"""리뷰 분석 서비스 (감성분석 + 키워드 추출 + 요약).

# Design Ref: §3.3 — LLM 분석 서비스
# Plan SC: SC-02 (감성분석 정확도 80%+), SC-03 (1회 LLM 호출로 3가지 동시)

학습 포인트:
    프롬프트 엔지니어링 (Prompt Engineering):
        LLM에게 "어떻게 답변해야 하는지"를 정확히 지시하는 기술입니다.
        핵심 원칙:
        1. 역할 부여: "당신은 농산물 리뷰 분석 전문가입니다"
        2. 출력 형식 명시: "반드시 JSON 형식으로 응답하세요"
        3. 예시 제공: 기대하는 출력 구조를 보여줌
        4. 제약 조건: "JSON 외의 텍스트는 포함하지 마세요"

    배치 처리 (Batch Processing):
        리뷰 50개를 하나씩 분석하면 LLM 50번 호출 = 비용 50배.
        20개씩 묶어서 3번 호출하면 비용 3배로 줄어듭니다.
        게다가 1회 호출로 감성+키워드+요약을 동시에 받으면 더 절감됩니다.

    JSON 파싱 전략:
        LLM은 항상 완벽한 JSON을 반환하지 않습니다.
        ```json ... ``` 코드블록으로 감싸거나, 앞뒤에 설명 텍스트를 넣기도 합니다.
        따라서 3단계 파싱 전략이 필요합니다.

사용 예시:
    from app.core.review_analyzer import ReviewAnalyzer

    analyzer = ReviewAnalyzer()
    result = await analyzer.analyze_batch([
        {"id": "rev-01", "text": "딸기가 달아요", "rating": 5, "platform": "네이버"},
    ])
    print(result["sentiments"])   # 감성 분석 결과
    print(result["keywords"])     # 키워드 추출 결과
    print(result["summary"])      # 요약
"""

import asyncio
import json
import logging
import time

import httpx

from app.core.llm_client_base import BaseLLMClient, get_llm_client
from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 프롬프트 템플릿
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "당신은 농산물 쇼핑몰 리뷰 분석 전문가입니다.\n"
    "리뷰를 분석하여 반드시 유효한 JSON 형식으로만 응답하세요.\n"
    "JSON 외의 텍스트는 절대 포함하지 마세요."
)

ANALYSIS_PROMPT_TEMPLATE = """다음 {count}개의 농산물 리뷰를 분석하세요.

리뷰 목록:
{reviews_text}

다음 JSON 형식으로 정확히 반환하세요 (JSON만 출력, 다른 텍스트 금지):
{{
  "sentiments": [
    {{"id": "리뷰ID", "sentiment": "positive 또는 negative 또는 neutral"}}
  ],
  "keywords": [
    {{"word": "키워드", "count": 출현횟수정수, "sentiment": "positive 또는 negative 또는 neutral"}}
  ],
  "summary": {{
    "overall": "전체 요약 2-3문장",
    "positives": ["긍정 포인트1", "긍정 포인트2"],
    "negatives": ["부정 포인트1", "부정 포인트2"],
    "suggestions": ["개선 제안1", "개선 제안2"]
  }}
}}"""


# ---------------------------------------------------------------------------
# ReviewAnalyzer 클래스
# ---------------------------------------------------------------------------

class ReviewAnalyzer:
    """리뷰 분석기 — 1회 LLM 호출로 감성+키워드+요약 동시 처리.

    학습 포인트:
        이 클래스는 RAG 파이프라인의 "G" (Generation, 생성) 부분입니다.
        review_rag.py에서 검색한 리뷰를 받아서 LLM으로 분석합니다.

        핵심 설계 결정:
        - 1회 호출로 3가지 분석 동시 수행 → 비용 1/3
        - 배치 처리로 여러 리뷰를 묶어서 호출 → 호출 횟수 최소화
        - JSON 파싱 실패 시 재시도 → 안정성 확보
    """

    def __init__(self, llm_client: BaseLLMClient | None = None):
        self.llm = llm_client or get_llm_client()

    async def analyze_batch(
        self,
        reviews: list[dict],
        batch_size: int | None = None,
    ) -> dict:
        """리뷰 배치 분석을 수행합니다.

        학습 포인트:
            리뷰가 50개이고 batch_size=20이면:
            - 배치 1: 리뷰 1~20 → LLM 호출 1회
            - 배치 2: 리뷰 21~40 → LLM 호출 1회
            - 배치 3: 리뷰 41~50 → LLM 호출 1회
            총 3회 호출로 50개 리뷰의 감성+키워드+요약을 모두 얻습니다.

        Args:
            reviews: 리뷰 딕셔너리 리스트
                [{ id, text, rating, platform }]
            batch_size: 1회 LLM 호출당 리뷰 수 (기본: settings 값)

        Returns:
            {
                "sentiments": [...],
                "keywords": [...],
                "summary": {...},
                "sentiment_summary": { positive, negative, neutral, total },
                "processing_time_ms": int,
                "llm_provider": str,
                "llm_model": str,
            }
        """
        if not reviews:
            return self._empty_result()

        batch_size = batch_size or settings.REVIEW_ANALYSIS_BATCH_SIZE
        start_time = time.time()

        # 배치 분할
        batches = [reviews[i:i + batch_size] for i in range(0, len(reviews), batch_size)]
        total_batches = len(batches)
        logger.info(f"총 {len(reviews)}건 → {total_batches}배치 병렬 분석 시작")

        # 모든 배치를 동시에 LLM 호출 (클라우드 API는 병렬 가능)
        tasks = [self._analyze_single_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_sentiments: list[dict] = []
        all_keywords: dict[str, dict] = {}
        batch_summaries: list[dict] = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"배치 {i+1} 실패: {result}")
                continue
            if result:
                all_sentiments.extend(result.get("sentiments", []))
                self._merge_keywords(all_keywords, result.get("keywords", []))
                if result.get("summary"):
                    batch_summaries.append(result["summary"])

        # 결과 집계
        sentiment_summary = self._calculate_sentiment_summary(all_sentiments)

        sorted_keywords = sorted(
            [{"word": w, **v} for w, v in all_keywords.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:20]  # 상위 20개

        final_summary = batch_summaries[-1] if batch_summaries else {}
        elapsed_ms = int((time.time() - start_time) * 1000)

        return {
            "sentiments": all_sentiments,
            "keywords": sorted_keywords,
            "summary": final_summary,
            "sentiment_summary": sentiment_summary,
            "processing_time_ms": elapsed_ms,
            "llm_provider": self.llm.provider_name,
            "llm_model": getattr(self.llm, "model", settings.LLM_MODEL),
        }

    async def analyze_batch_with_progress(
        self,
        reviews: list[dict],
        batch_size: int | None = None,
    ):
        """진행률을 yield하며 배치 분석을 수행합니다 (SSE용).

        클라우드 API일 때 모든 배치를 병렬 호출하여 속도를 극대화합니다.

        Yields:
            { "progress": 0~100, "batch": int, "total_batches": int, "message": str }
            마지막에 { "progress": 100, "result": {...}, "message": "분석 완료" }
        """
        if not reviews:
            yield {"progress": 100, "result": self._empty_result(), "message": "분석할 리뷰가 없습니다."}
            return

        batch_size = batch_size or settings.REVIEW_ANALYSIS_BATCH_SIZE
        start_time = time.time()

        batches = [reviews[i:i + batch_size] for i in range(0, len(reviews), batch_size)]
        total_batches = len(batches)

        yield {
            "progress": 5,
            "batch": 0,
            "total_batches": total_batches,
            "message": f"LLM {total_batches}개 배치 병렬 분석 시작...",
        }

        # 모든 배치를 동시에 LLM 호출
        tasks = [self._analyze_single_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_sentiments: list[dict] = []
        all_keywords: dict[str, dict] = {}
        batch_summaries: list[dict] = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"배치 {i+1} 실패: {result}")
                continue
            if result:
                all_sentiments.extend(result.get("sentiments", []))
                self._merge_keywords(all_keywords, result.get("keywords", []))
                if result.get("summary"):
                    batch_summaries.append(result["summary"])

        yield {"progress": 90, "batch": total_batches, "total_batches": total_batches, "message": "결과 집계 중..."}

        sentiment_summary = self._calculate_sentiment_summary(all_sentiments)
        sorted_keywords = sorted(
            [{"word": w, **v} for w, v in all_keywords.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:20]
        final_summary = batch_summaries[-1] if batch_summaries else {}
        elapsed_ms = int((time.time() - start_time) * 1000)

        final_result = {
            "sentiments": all_sentiments,
            "keywords": sorted_keywords,
            "summary": final_summary,
            "sentiment_summary": sentiment_summary,
            "processing_time_ms": elapsed_ms,
            "llm_provider": self.llm.provider_name,
            "llm_model": getattr(self.llm, "model", settings.LLM_MODEL),
        }

        yield {"progress": 100, "result": final_result, "message": "분석 완료"}

    # ------------------------------------------------------------------
    # 단일 배치 분석
    # ------------------------------------------------------------------

    async def _analyze_single_batch(self, reviews: list[dict]) -> dict | None:
        """단일 배치를 LLM으로 분석합니다 (재시도 포함).

        학습 포인트:
            LLM 응답이 항상 완벽한 JSON이 아닐 수 있으므로
            파싱 실패 시 최대 N회 재시도합니다.
            재시도 시에도 같은 프롬프트를 보내지만,
            LLM의 비결정적 특성으로 다른 결과가 나올 수 있습니다.
        """
        reviews_text = self._format_reviews_for_prompt(reviews)
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            count=len(reviews),
            reviews_text=reviews_text,
        )

        max_retries = settings.REVIEW_ANALYSIS_MAX_RETRIES
        for attempt in range(max_retries + 1):
            try:
                response = await self.llm.generate(prompt, system=SYSTEM_PROMPT)
                parsed = self._parse_json_response(response)
                logger.info(f"배치 분석 성공 (시도 {attempt + 1})")
                return parsed
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"LLM 응답 파싱 실패 (시도 {attempt + 1}/{max_retries + 1}): {e}")
                if attempt == max_retries:
                    logger.error("LLM 분석 최대 재시도 초과, 이 배치 건너뜀")
                    return None
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status != 429 and status < 500:
                    body = (e.response.text or "")[:500]
                    logger.error(
                        f"LLM HTTP {status} 비재시도 오류, 이 배치 건너뜀: {body}"
                    )
                    return None
                wait = 2 ** attempt
                logger.warning(
                    f"LLM HTTP {status} (시도 {attempt + 1}/{max_retries + 1}): {e} → {wait}초 후 재시도"
                )
                if attempt == max_retries:
                    logger.error("LLM HTTP 최대 재시도 초과, 이 배치 건너뜀")
                    return None
                await asyncio.sleep(wait)
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                # Cloudflare 504 / 네트워크 일시 오류 등 — 지수 백오프 후 재시도
                wait = 2 ** attempt
                logger.warning(
                    f"LLM 네트워크 오류 (시도 {attempt + 1}/{max_retries + 1}): {e} → {wait}초 후 재시도"
                )
                if attempt == max_retries:
                    logger.error("LLM 네트워크 최대 재시도 초과, 이 배치 건너뜀")
                    return None
                await asyncio.sleep(wait)

    # ------------------------------------------------------------------
    # 프롬프트 포맷팅
    # ------------------------------------------------------------------

    def _format_reviews_for_prompt(self, reviews: list[dict]) -> str:
        """리뷰를 LLM 프롬프트용 텍스트로 포맷합니다.

        학습 포인트:
            LLM에게 리뷰를 보낼 때 구조화된 형식으로 전달하면
            분석 정확도가 높아집니다.
            각 리뷰에 ID, 평점, 플랫폼 정보를 함께 제공합니다.
        """
        lines = []
        for r in reviews:
            rating = int(r.get("rating", 0))
            stars = "★" * rating + "☆" * (5 - rating)
            platform = r.get("platform", "")
            lines.append(f'{r["id"]}. "{r["text"]}" ({stars}, {platform})')
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # JSON 파싱
    # ------------------------------------------------------------------

    def _parse_json_response(self, response: str) -> dict:
        """LLM 응답에서 JSON을 추출하고 파싱합니다.

        학습 포인트:
            LLM 응답에서 JSON을 추출하는 3단계 전략:

            1단계: 그대로 파싱 시도
                응답이 순수 JSON이면 바로 성공

            2단계: ```json ... ``` 코드블록에서 추출
                LLM이 마크다운 코드블록으로 감싼 경우

            3단계: 첫 번째 { 에서 마지막 } 까지 추출
                앞뒤에 설명 텍스트가 붙은 경우

            이 3단계로도 실패하면 json.JSONDecodeError를 발생시켜
            재시도 로직이 동작하도록 합니다.
        """
        text = response.strip()

        # 1단계: 직접 파싱
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2단계: ```json ... ``` 코드블록 추출
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            return json.loads(text[start:end].strip())

        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            candidate = text[start:end].strip()
            if candidate.startswith("{"):
                return json.loads(candidate)

        # 3단계: 첫 { ~ 마지막 } 추출
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return json.loads(text[first_brace:last_brace + 1])

        raise json.JSONDecodeError("JSON을 찾을 수 없음", text, 0)

    # ------------------------------------------------------------------
    # 결과 집계 헬퍼
    # ------------------------------------------------------------------

    def _calculate_sentiment_summary(self, sentiments: list[dict]) -> dict:
        """감성 분석 결과를 통계로 집계합니다."""
        summary = {"positive": 0, "negative": 0, "neutral": 0, "total": len(sentiments)}
        for s in sentiments:
            sentiment = s.get("sentiment", "neutral").lower()
            if sentiment in summary:
                summary[sentiment] += 1
        return summary

    def _merge_keywords(self, accumulated: dict, new_keywords: list[dict]):
        """여러 배치의 키워드를 병합합니다.

        학습 포인트:
            여러 배치에서 같은 키워드가 나올 수 있습니다.
            예: 배치1에서 "당도" 5회, 배치2에서 "당도" 3회
            → 병합 결과: "당도" 8회
        """
        for kw in new_keywords:
            if isinstance(kw, str):
                kw = {"word": kw, "count": 1, "sentiment": "neutral"}
            word = kw.get("word", "").strip()
            if not word:
                continue

            if word in accumulated:
                accumulated[word]["count"] += kw.get("count", 1)
            else:
                accumulated[word] = {
                    "count": kw.get("count", 1),
                    "sentiment": kw.get("sentiment", "neutral"),
                }

    def _empty_result(self) -> dict:
        """빈 결과를 반환합니다."""
        return {
            "sentiments": [],
            "keywords": [],
            "summary": {},
            "sentiment_summary": {"positive": 0, "negative": 0, "neutral": 0, "total": 0},
            "processing_time_ms": 0,
            "llm_provider": self.llm.provider_name,
            "llm_model": getattr(self.llm, "model", settings.LLM_MODEL),
        }
