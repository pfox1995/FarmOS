"""에이전트 서브패키지.

AgentExecutor (에이전트 1개) + clients/ (교체 가능한 LLM 클라이언트)
"""
from ai.agent.clients.base import AgentClient, AgentUnavailableError, AgentResponse, ToolCall
from ai.agent.clients.openai import OpenAIAgentClient
from ai.agent.clients.claude import ClaudeAgentClient
from ai.agent.executor import AgentExecutor, AgentResult, RequestContext
from ai.agent.tools import TOOL_DEFINITIONS, TOOL_TO_INTENT

__all__ = [
    # 클라이언트 인터페이스
    "AgentClient",
    "AgentUnavailableError",
    "AgentResponse",
    "ToolCall",
    # LLM 클라이언트 구현체
    "OpenAIAgentClient",
    "ClaudeAgentClient",
    # 에이전트
    "AgentExecutor",
    "AgentResult",
    "RequestContext",
    # 도구
    "TOOL_DEFINITIONS",
    "TOOL_TO_INTENT",
]
