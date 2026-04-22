"""LLM 클라이언트 추상화 모듈.

# Design Ref: §3.1 — LLM 추상화 클라이언트
# Plan SC: SC-04 (LLM 추상화로 Ollama↔OpenRouter 전환 가능)

학습 포인트:
- ABC(Abstract Base Class): 공통 인터페이스를 정의하는 파이썬 패턴.
  자식 클래스가 반드시 구현해야 할 메서드를 강제합니다.
- 팩토리 패턴: 환경변수에 따라 적절한 클라이언트를 생성합니다.
  코드 변경 없이 .env만 수정하면 LLM 제공자를 전환할 수 있습니다.

사용 예시:
    from app.core.llm_client_base import get_llm_client

    llm = get_llm_client()  # .env의 LLM_PROVIDER에 따라 자동 선택
    response = await llm.generate("리뷰를 분석해주세요", system="분석 전문가")
"""

import json
import logging
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 추상 인터페이스
# ---------------------------------------------------------------------------

class BaseLLMClient(ABC):
    """LLM 클라이언트 추상 인터페이스.

    학습 포인트:
        ABC를 상속하고 @abstractmethod를 붙이면,
        이 클래스를 직접 인스턴스화할 수 없고
        자식 클래스가 반드시 해당 메서드를 구현해야 합니다.

        왜 이렇게 하나?
        → OllamaClient든 OpenRouterClient든 동일한 .generate()로 호출 가능.
        → 호출하는 쪽(review_analyzer.py)은 어떤 LLM인지 몰라도 됩니다.
    """

    @abstractmethod
    async def generate(self, prompt: str, system: str = "") -> str:
        """프롬프트를 받아 텍스트를 생성합니다.

        Args:
            prompt: 사용자 프롬프트 (분석 요청 등)
            system: 시스템 프롬프트 (역할 지정)

        Returns:
            LLM이 생성한 텍스트
        """
        ...

    @abstractmethod
    async def chat(self, messages: list[dict]) -> str:
        """채팅 형식으로 텍스트를 생성합니다.

        Args:
            messages: [{"role": "system"|"user"|"assistant", "content": "..."}]

        Returns:
            LLM이 생성한 응답 텍스트
        """
        ...

    @property
    def provider_name(self) -> str:
        """LLM 제공자 이름 (로깅/기록용)."""
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# Ollama 클라이언트 (로컬)
# ---------------------------------------------------------------------------

class OllamaClient(BaseLLMClient):
    """로컬 Ollama LLM 클라이언트.

    학습 포인트:
        Ollama는 로컬에서 LLM을 실행하는 도구입니다.
        http://localhost:11434 에서 REST API를 제공합니다.
        비용: 0원 (로컬 GPU 사용)

        API 문서: https://github.com/ollama/ollama/blob/main/docs/api.md
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.LLM_MODEL

    async def generate(self, prompt: str, system: str = "") -> str:
        """Ollama /api/generate 엔드포인트 호출.

        학습 포인트:
            Ollama의 generate API는 단일 프롬프트를 받아 텍스트를 생성합니다.
            stream=False로 설정하면 전체 응답을 한번에 받습니다.
            temperature=0은 결정적 출력으로 속도가 빠르고 JSON 파싱 안정성이 높습니다.
            num_predict로 최대 출력 토큰을 제한하여 불필요한 생성을 방지합니다.
        """
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "num_predict": 4096,
                    },
                }
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json().get("response", "")
        except httpx.ConnectError:
            logger.error(
                f"Ollama 서버에 연결할 수 없습니다 ({self.base_url}). "
                "Ollama가 실행 중인지 확인하세요: ollama serve"
            )
            raise
        except Exception as e:
            logger.error(f"Ollama generate 실패: {e}")
            raise

    async def chat(self, messages: list[dict]) -> str:
        """Ollama /api/chat 엔드포인트 호출."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                }
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Ollama chat 실패: {e}")
            raise


# ---------------------------------------------------------------------------
# OpenRouter 클라이언트 (클라우드)
# ---------------------------------------------------------------------------

class OpenRouterClient(BaseLLMClient):
    """OpenRouter 클라우드 LLM 클라이언트.

    학습 포인트:
        OpenRouter는 다양한 LLM 모델을 하나의 API로 접근할 수 있는 서비스입니다.
        OpenAI 호환 API 형식을 사용하므로, /chat/completions 엔드포인트를 씁니다.

        비용: API 호출당 과금 (모델마다 다름)
        설정: .env에 OPENROUTER_API_KEY 필요
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.model = model or settings.OPENROUTER_MODEL
        self.base_url = settings.OPENROUTER_URL

    async def generate(self, prompt: str, system: str = "") -> str:
        """OpenRouter chat/completions 엔드포인트 호출.

        학습 포인트:
            OpenRouter는 OpenAI 호환 API를 사용합니다.
            generate()도 내부적으로 chat/completions를 호출하되,
            messages 형식으로 변환합니다.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return await self.chat(messages)

    async def chat(self, messages: list[dict]) -> str:
        """OpenRouter chat/completions 엔드포인트 호출.

        학습 포인트:
            GPT-5 계열 등 리즈닝 모델은 기본적으로 내부 추론 토큰을 많이 소비합니다.
            단순 JSON 생성 용도에선 리즈닝이 불필요하므로
            settings.LLM_REASONING_EFFORT 로 "minimal" 로 낮춰 속도/비용을 확보합니다.

            - reasoning_effort: minimal | low | medium | high
            - None 으로 지정하면 파라미터를 아예 보내지 않아 기본값(medium) 사용
            - non-reasoning 모델(gemma, gpt-oss 등)은 이 파라미터를 무시
        """
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY가 설정되지 않았습니다. "
                ".env 파일에 OPENROUTER_API_KEY=sk-or-xxx를 추가하세요."
            )

        payload: dict = {
            "model": self.model,
            "messages": messages,
        }
        effort = settings.LLM_REASONING_EFFORT.strip().lower()
        if effort and effort != "none":
            payload["reasoning_effort"] = effort

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter API 오류 ({e.response.status_code}): {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"OpenRouter chat 실패: {e}")
            raise


# ---------------------------------------------------------------------------
# Remote Ollama 클라이언트 (RunPod 등)
# ---------------------------------------------------------------------------

class RemoteOllamaClient(OllamaClient):
    """원격 Ollama 클라이언트 (RunPod GPU 서버 등).

    학습 포인트:
        OllamaClient와 동일한 프로토콜을 사용하지만,
        URL만 원격 서버를 가리킵니다.
        상속을 활용해 코드 중복을 제거합니다.

        예: RunPod에서 Ollama를 실행하면
        https://xxx-11434.proxy.runpod.net 같은 URL이 생깁니다.
    """

    def __init__(self, base_url: str | None = None, model: str | None = None):
        remote_url = base_url or settings.OLLAMA_REMOTE_URL
        if not remote_url:
            raise ValueError(
                "OLLAMA_REMOTE_URL이 설정되지 않았습니다. "
                ".env 파일에 원격 Ollama 서버 URL을 추가하세요."
            )
        super().__init__(base_url=remote_url, model=model)


# ---------------------------------------------------------------------------
# 팩토리 함수
# ---------------------------------------------------------------------------

def get_llm_client() -> BaseLLMClient:
    """환경변수 기반으로 적절한 LLM 클라이언트를 생성합니다.

    학습 포인트:
        팩토리 패턴 — 객체 생성 로직을 한 곳에 모아둡니다.
        호출하는 쪽은 어떤 클라이언트가 반환되는지 몰라도 됩니다.
        .env의 LLM_PROVIDER 값만 바꾸면 전체 앱의 LLM이 전환됩니다.

    .env 설정 예시:
        LLM_PROVIDER=ollama          → 로컬 Ollama (개발용, 비용 0원)
        LLM_PROVIDER=openrouter      → OpenRouter 클라우드 (배포 A)
        LLM_PROVIDER=ollama_remote   → 원격 Ollama/RunPod (배포 B)

    Returns:
        BaseLLMClient 구현체
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openrouter":
        logger.info(f"LLM Provider: OpenRouter (model={settings.OPENROUTER_MODEL})")
        return OpenRouterClient()
    elif provider == "ollama_remote":
        logger.info(f"LLM Provider: Remote Ollama (url={settings.OLLAMA_REMOTE_URL})")
        return RemoteOllamaClient()
    else:
        logger.info(f"LLM Provider: Ollama Local (model={settings.LLM_MODEL})")
        return OllamaClient()
