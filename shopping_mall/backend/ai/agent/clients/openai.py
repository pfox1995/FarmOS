"""OpenAI 호환 API 기반 에이전트 클라이언트.

OpenAI 호환 `/v1/chat/completions` 엔드포인트를 사용하는 모든 provider를 지원합니다.

사용 예:
    from app.core.config import settings

    # OpenRouter (기본 설정)
    client = OpenAIAgentClient(
        base_url=settings.primary_llm_base_url,
        api_key=settings.primary_llm_api_key,
        model=settings.primary_llm_model,
    )

    # Ollama (OpenAI 호환 엔드포인트)
    client = OpenAIAgentClient(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model="qwen2.5:7b",
    )

    # OpenAI
    client = OpenAIAgentClient(
        base_url="https://api.openai.com/v1",
        api_key=settings.primary_llm_api_key,
        model="gpt-4o",
    )
"""
import json
import logging

import httpx

from ai.agent.clients.base import AgentClient, AgentResponse, AgentUnavailableError, ToolCall

logger = logging.getLogger(__name__)


class OpenAIAgentClient(AgentClient):
    """OpenAI 호환 tool_use 클라이언트."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ):
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def _to_openai_tools(self, tools: list[dict]) -> list[dict]:
        """중립 형식 → OpenAI 호환 형식으로 변환."""
        return [{"type": "function", "function": t} for t in tools]

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str,
    ) -> AgentResponse:
        all_messages = [{"role": "system", "content": system}] + messages
        payload = {
            "model": self.model,
            "messages": all_messages,
            "tools": self._to_openai_tools(tools),
            "tool_choice": "auto",
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            if "choices" not in data:
                logger.error(f"응답에 'choices' 없음. base_url={self._base_url}, 응답: {data}")
                raise AgentUnavailableError(f"응답 형식 오류: {data.get('error', data)}")

            message = data["choices"][0]["message"]
            raw_tool_calls = message.get("tool_calls") or []

            tool_calls = []
            for tc in raw_tool_calls:
                args = tc["function"]["arguments"]
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        logger.warning(f"도구 호출 인수 JSON 디코딩 실패, 원본 문자열 사용: {args[:100]}")
                        args = {}
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", ""),
                        name=tc["function"]["name"],
                        arguments=args or {},
                    )
                )

            return AgentResponse(
                text=message.get("content") if not tool_calls else None,
                tool_calls=tool_calls,
                raw=message,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 오류: {e.response.status_code} {e.response.text} (base_url={self._base_url})")
            raise AgentUnavailableError(f"HTTP 오류: {e.response.status_code}") from e
        except AgentUnavailableError:
            raise
        except Exception as e:
            logger.error(f"연결 실패 (base_url={self._base_url}): {e}")
            raise AgentUnavailableError(f"연결 실패: {e}") from e

    def add_tool_results(
        self,
        messages: list[dict],
        response: AgentResponse,
        results: list[tuple[ToolCall, str]],
    ) -> None:
        """OpenAI 호환 형식으로 어시스턴트 메시지 + 도구 결과를 추가합니다."""
        raw_content = ""
        if response.raw is not None and isinstance(response.raw, dict):
            raw_content = response.raw.get("content") or ""
        assistant_msg: dict = {
            "role": "assistant",
            "content": raw_content,
        }
        if response.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in response.tool_calls
            ]
        messages.append(assistant_msg)

        for tc, result in results:
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    async def is_available(self) -> bool:
        return bool(self._api_key)
