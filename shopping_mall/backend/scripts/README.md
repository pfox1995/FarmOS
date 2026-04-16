# scripts/

개발·운영용 유틸리티 스크립트. 서버 실행과 무관하게 직접 실행합니다.

## 파일

| 파일 | 역할 |
|------|------|
| `seed_and_verify.py` | ChromaDB 시딩(`ai/seed_rag.py`) 실행 후 전체 컬렉션 검색 검증까지 한번에 수행 |

## 실행

```bash
# RAG 시딩 + 검증 (.env의 EMBED_PROVIDER 설정 사용)
uv run python scripts/seed_and_verify.py
```

## seed_and_verify.py 단계

1. `ai/seed_rag.py` 호출로 9개 컬렉션 시딩
2. 컬렉션별 청크 수 확인
3. 샘플 쿼리로 실제 검색 테스트 (PASS / FAIL 출력)
