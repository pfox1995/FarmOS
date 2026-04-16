# ai/agent/clients/

교체 가능한 LLM 클라이언트 구현체. `AgentClient` 인터페이스를 구현하면 어떤 LLM도 에이전트에 연결할 수 있습니다.

## 파일

| 파일 | 역할 |
|------|------|
| `base.py` | 추상 인터페이스 — `AgentClient`, `AgentResponse`, `AgentUnavailableError`, `ToolCall` 정의 |
| `openai.py` | OpenAI 호환 클라이언트 — OpenRouter / Ollama / OpenAI 등 `/v1/chat/completions` 엔드포인트를 쓰는 모든 provider 지원 |
| `claude.py` | Anthropic Claude 클라이언트 — Fallback LLM. Primary 장애 시 자동 전환 |

## LLM 체인

```
OpenAIAgentClient (PRIMARY_LLM_*)  →  실패 시  →  ClaudeAgentClient (ANTHROPIC_API_KEY)
                                                          ↓ 둘 다 실패
                                                    escalated=True
```

## Provider 전환 (.env만 수정)

```env
# OpenRouter
PRIMARY_LLM_BASE_URL=https://openrouter.ai/api/v1
PRIMARY_LLM_API_KEY=sk-or-...
PRIMARY_LLM_MODEL=google/gemma-3-27b-it

# Ollama (로컬)
PRIMARY_LLM_BASE_URL=http://localhost:11434/v1
PRIMARY_LLM_API_KEY=ollama
PRIMARY_LLM_MODEL=qwen2.5:7b

# OpenAI
PRIMARY_LLM_BASE_URL=https://api.openai.com/v1
PRIMARY_LLM_API_KEY=sk-...
PRIMARY_LLM_MODEL=gpt-4o
```
