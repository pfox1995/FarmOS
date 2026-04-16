"""에이전트 클라이언트 추상 인터페이스.

OpenAIAgentClient(primary)와 ClaudeAgentClient(fallback)가 이 인터페이스를 구현합니다.
AgentExecutor는 이 인터페이스만 의존하므로 두 클라이언트를 동일하게 다룹니다.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """클라이언트 종류에 무관한 통일된 도구 호출 표현."""
    id: str          # Ollama는 "" (없음), Claude는 "toolu_xxxx"
    name: str
    arguments: dict


@dataclass
class AgentResponse:
    """LLM 응답을 통일된 형식으로 표현."""
    text: str | None                          # 최종 텍스트 (tool_calls 없을 때)
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: object = None                        # 원본 응답 (디버깅 및 메시지 재구성용)


class AgentUnavailableError(Exception):
    """LLM 클라이언트에 연결할 수 없을 때 발생. AgentExecutor가 폴백을 트리거합니다."""


class AgentClient(ABC):
    """에이전트 LLM 클라이언트 추상 기반 클래스."""

    @abstractmethod
    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str,
    ) -> AgentResponse:
        """tools를 포함하여 LLM에 메시지를 전송하고 응답을 반환합니다.

        Args:
            messages: 대화 히스토리 (role/content 형식)
            tools: 중립 형식의 도구 정의 (name/description/parameters)
            system: 시스템 프롬프트

        Returns:
            AgentResponse — tool_calls가 있으면 도구 호출, 없으면 최종 텍스트

        Raises:
            AgentUnavailableError: 연결 실패 또는 API 오류 시
        """
        ...

    @abstractmethod
    def add_tool_results(
        self,
        messages: list[dict],
        response: AgentResponse,
        results: list[tuple[ToolCall, str]],
    ) -> None:
        """어시스턴트 응답과 도구 실행 결과를 messages에 추가합니다 (in-place).

        각 클라이언트마다 메시지 포맷이 다르므로 클라이언트가 직접 처리합니다.
        - OpenAI 호환: assistant message + 개별 tool 메시지 (tool_call_id 필수)
        - Claude: assistant content blocks + 통합 user tool_result 메시지

        Args:
            messages: 수정할 대화 히스토리 리스트
            response: 도구 호출이 담긴 AgentResponse
            results: [(ToolCall, 결과 문자열), ...] 쌍의 리스트
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """필수 자격증명(API 키)이 설정되어 있는지 확인합니다.

        실제 네트워크 연결은 검증하지 않습니다. 연결 실패는 chat_with_tools()에서
        AgentUnavailableError로 처리됩니다.
        """
        ...
