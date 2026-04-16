"""리포트/비용분류용 LLM 클라이언트 — OpenAI 호환 API."""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI 호환 클라이언트 — Ollama·OpenRouter·OpenAI 모두 지원."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = (base_url or settings.utility_llm_base_url).rstrip("/")
        self.api_key = api_key or settings.utility_llm_api_key
        self.model = model or settings.utility_llm_model

    async def generate(self, prompt: str, system: str = "") -> str:
        """단일 프롬프트로 텍스트를 생성합니다. 실패 시 폴백 반환."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json={"model": self.model, "messages": messages},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"LLM generate failed: {e}")
            return self._fallback(prompt)

    async def generate_report(self, data: dict) -> str:
        """주간 매출 데이터를 분석해 인사이트 텍스트를 생성합니다."""
        prompt = (
            "다음 주간 매출 데이터를 분석하여 한국어로 인사이트를 작성하세요.\n\n"
            f"기간: {data.get('week_start', '')} ~ {data.get('week_end', '')}\n"
            f"총 매출: {data.get('total_revenue', 0):,}원\n"
            f"총 비용: {data.get('total_expense', 0):,}원\n"
            f"순이익: {data.get('net_profit', 0):,}원\n"
            f"인기 상품: {data.get('top_items', [])}\n\n"
            "3-5문장으로 핵심 인사이트를 작성하세요:"
        )
        return await self.generate(prompt, system="당신은 농산물 쇼핑몰 비즈니스 분석가입니다.")

    async def classify_expense(self, description: str) -> str:
        """비용 설명을 카테고리로 분류합니다."""
        prompt = (
            "다음 비용 설명을 카테고리로 분류하세요. "
            "카테고리: packaging, shipping, material, labor, utility, marketing, other\n\n"
            f"설명: {description}\n\n"
            "카테고리(영어 한 단어만):"
        )
        result = await self.generate(prompt, system="비용 분류 전문가입니다. 영어 한 단어로만 답하세요.")
        result = result.strip().lower()
        valid = {"packaging", "shipping", "material", "labor", "utility", "marketing", "other"}
        for cat in valid:
            if cat in result:
                return cat
        return "other"

    def _fallback(self, prompt: str) -> str:
        """LLM 연결 불가 시 규칙 기반 폴백."""
        prompt_lower = prompt.lower()
        if "분류" in prompt_lower or "classify" in prompt_lower:
            return "other"
        if "보고서" in prompt_lower or "report" in prompt_lower or "인사이트" in prompt_lower:
            return "AI 분석 서비스를 이용할 수 없어 자동 리포트를 생성할 수 없습니다. 데이터 수치를 참고해 주세요."
        return "[AI 서비스 연결 불가 - 폴백 응답]"
