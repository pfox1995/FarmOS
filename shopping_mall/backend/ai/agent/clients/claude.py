"""Claude API 기반 에이전트 클라이언트 (Fallback LLM).

Primary LLM 장애 시 Claude Haiku로 동일한 tool_use 에이전트를 실행합니다.
"""
import logging

import anthropic

from ai.agent.clients.base import AgentClient, AgentResponse, AgentUnavailableError, ToolCall

logger = logging.getLogger(__name__)


class ClaudeAgentClient(AgentClient):
    """Anthropic Claude API tool_use 클라이언트."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5",
    ):
        self.model = model
        self._api_key = api_key
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    def _to_claude_tools(self, tools: list[dict]) -> list[dict]:
        """중립 형식 → Claude 형식으로 변환. parameters → input_schema."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in tools
        ]

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str,
    ) -> AgentResponse:
        try:
            response = await self.client.messages.create(
                model=self.model,
                system=system,
                messages=messages,
                tools=self._to_claude_tools(tools),
                max_tokens=1024,
            )

            tool_calls = []
            text = None
            for block in response.content:
                if block.type == "tool_use":
                    tool_calls.append(
                        ToolCall(id=block.id, name=block.name, arguments=block.input)
                    )
                elif block.type == "text" and block.text:
                    text = block.text

            return AgentResponse(
                text=text if not tool_calls else None,
                tool_calls=tool_calls,
                raw=response,
            )

        except anthropic.AuthenticationError as e:
            logger.exception(f"Claude API 인증 실패: {e}")
            raise AgentUnavailableError(f"Claude API 인증 실패: {e}") from e
        except anthropic.APIError as e:
            logger.exception(f"Claude API 오류: {e}")
            raise AgentUnavailableError(f"Claude API 오류: {e}") from e
        except Exception as e:
            logger.exception(f"Claude 클라이언트 오류: {e}")
            raise AgentUnavailableError(f"Claude 클라이언트 오류: {e}") from e

    def add_tool_results(
        self,
        messages: list[dict],
        response: AgentResponse,
        results: list[tuple[ToolCall, str]],
    ) -> None:
        """Claude 형식으로 어시스턴트 메시지 + 도구 결과를 추가합니다."""
        # 어시스턴트 메시지 (content 블록 그대로)
        if response.raw is not None and hasattr(response.raw, "content"):
            content = response.raw.content
        else:
            # raw 없으면 AgentResponse에서 재구성
            content = []
            if response.text:
                content.append({"type": "text", "text": response.text})
            for tc in response.tool_calls:
                content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
        messages.append({"role": "assistant", "content": content})

        # 모든 도구 결과를 하나의 user 메시지로 묶음 (Claude 요구사항)
        tool_results = [
            {
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result,
            }
            for tc, result in results
        ]
        messages.append({"role": "user", "content": tool_results})

    async def is_available(self) -> bool:
        return bool(self._api_key)
