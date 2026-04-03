"""LLM client using Ollama API with graceful fallback."""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3"


class LLMClient:
    """Async client for Ollama LLM API with fallback responses."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = DEFAULT_MODEL):
        self.base_url = base_url
        self.model = model

    async def generate(self, prompt: str, system: str = "") -> str:
        """Generate text from a prompt. Falls back to placeholder on error."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                }
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                return resp.json().get("response", "")
        except Exception as e:
            logger.warning(f"Ollama generate failed: {e}")
            return self._fallback_generate(prompt)

    async def chat(self, messages: list[dict]) -> str:
        """Chat completion. Falls back to placeholder on error."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                }
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", "")
        except Exception as e:
            logger.warning(f"Ollama chat failed: {e}")
            return "[AI 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.]"

    async def embed(self, text: str) -> list[float]:
        """Get text embedding. Returns empty list on error."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "model": self.model,
                    "input": text,
                }
                resp = await client.post(f"{self.base_url}/api/embed", json=payload)
                resp.raise_for_status()
                data = resp.json()
                embeddings = data.get("embeddings", [[]])
                return embeddings[0] if embeddings else []
        except Exception as e:
            logger.warning(f"Ollama embed failed: {e}")
            return []

    async def classify_intent(self, query: str) -> str:
        """Classify user intent from a query string."""
        prompt = (
            "사용자 질문의 의도를 다음 중 하나로 분류하세요: "
            "delivery(배송), stock(재고), storage(보관방법), season(제철정보), "
            "exchange(교환/환불), other(기타)\n\n"
            f"질문: {query}\n\n"
            "의도(영어 한 단어만):"
        )
        result = await self.generate(prompt, system="당신은 의도 분류 전문가입니다. 영어 한 단어로만 답하세요.")
        result = result.strip().lower()
        valid_intents = {"delivery", "stock", "storage", "season", "exchange", "other"}
        for intent in valid_intents:
            if intent in result:
                return intent
        return "other"

    async def generate_report(self, data: dict) -> str:
        """Generate weekly report insight text from aggregated data."""
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
        """Classify an expense description into a category."""
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

    def _fallback_generate(self, prompt: str) -> str:
        """Provide rule-based fallback when LLM is unavailable."""
        prompt_lower = prompt.lower()
        if "분류" in prompt_lower or "classify" in prompt_lower:
            return "other"
        if "보고서" in prompt_lower or "report" in prompt_lower or "인사이트" in prompt_lower:
            return "AI 분석 서비스를 이용할 수 없어 자동 리포트를 생성할 수 없습니다. 데이터 수치를 참고해 주세요."
        return "[AI 서비스 연결 불가 - 폴백 응답]"
