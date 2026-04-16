# tests/

pytest 기반 테스트. 현재 에이전트 관련 테스트만 있습니다.

## 구조

```text
tests/
├── conftest.py          # 공용 픽스처 (FakeAgentClient, FakeRAGService, make_mock_db 등)
└── agent/
    ├── test_executor.py       # AgentExecutor 단위 테스트
    └── test_chatbot_service.py  # AgentChatbotService 통합 테스트
```

## 실행

```bash
uv run pytest
uv run pytest tests/agent/          # 에이전트 테스트만
uv run pytest -v                    # 상세 출력
```

## 픽스처 (conftest.py)

| 픽스처 | 설명 |
|--------|------|
| `FakeAgentClient` | 실제 LLM 호출 없이 미리 정의한 응답을 반환하는 mock 클라이언트 |
| `FakeRAGService` | ChromaDB 없이 컬렉션별 문서를 dict로 주입 |
| `make_mock_db` | SQLAlchemy Session mock |
| `make_text_response` | 텍스트 응답 AgentResponse 생성 헬퍼 |
