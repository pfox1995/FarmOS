"""ChromaDB 시딩 후 적재 검증까지 한 번에 수행하는 스크립트.

실행: uv run python scripts/seed_and_verify.py
"""
import gc
import sys
import os

# Windows Git Bash / cmd 환경에서 한글 출력을 위해 stdout을 UTF-8로 강제
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# shopping_mall/backend를 sys.path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.paths import CHROMA_DB_PATH

# 컬렉션별 검증용 샘플 쿼리
VERIFY_QUERIES: dict[str, str] = {
    "payment_policy":    "결제 방법이 뭐예요?",
    "delivery_policy":   "배송 얼마나 걸려요?",
    "return_policy":     "반품 어떻게 해요?",
    "quality_policy":    "상품 신선도 보장돼요?",
    "service_policy":    "고객센터 운영시간이 어떻게 돼요?",
    "membership_policy": "회원 탈퇴하려면 어떻게 해요?",
    "faq":               "자주 묻는 질문이 뭐가 있어요?",
    "storage_guide":     "딸기 보관 어떻게 해요?",
    "season_info":       "제철 농산물이 뭐예요?",
}

SEP = "=" * 60


def main():
    # ── 1단계: 시딩 ────────────────────────────────────────────────
    print(SEP)
    print("  [1단계] ChromaDB 시딩")
    print(SEP)
    try:
        from ai.seed_rag import main as seed_main
        seed_result = seed_main()
    except SystemExit:
        print("시딩 실패.")
        sys.exit(1)
    except Exception as e:
        print(f"시딩 오류: {e}")
        sys.exit(1)

    if seed_result is None:
        print("시딩 실패: client를 반환하지 않았습니다.")
        sys.exit(1)

    # ChromaDB 1.5.x 버그: 시딩에 쓴 클라이언트로 바로 query()하면
    # 일부 컬렉션 HNSW 인덱스를 찾지 못함 → 명시적으로 닫고 새 클라이언트로 재오픈
    seed_client, _ = seed_result
    del seed_client
    gc.collect()

    import chromadb
    from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
    from app.core.config import settings

    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    embed_fn = OllamaEmbeddingFunction(
        url=f"{settings.ollama_base_url}/api/embeddings",
        model_name=settings.ollama_embed_model,
    )

    # ── 2단계: 청크 수 확인 ─────────────────────────────────────────
    print()
    print(SEP)
    print("  [2단계] 컬렉션 청크 수 확인")
    print(SEP)
    collections = {c.name: c.count() for c in client.list_collections()}

    for name in sorted(VERIFY_QUERIES.keys()):
        count = collections.get(name, 0)
        print(f"  {'OK' if count > 0 else 'EMPTY':6}  {name:<25} {count:>3}개 청크")

    total = sum(collections.values())
    print()
    print(f"  총 {len(collections)}개 컬렉션 / {total}개 청크")

    # ── 3단계: 샘플 쿼리 검색 테스트 ────────────────────────────────
    print()
    print(SEP)
    print("  [3단계] 샘플 쿼리 검색 테스트")
    print("  (Ollama embeddinggemma:latest 사용 - Ollama 실행 중이어야 합니다)")
    print(SEP)
    all_pass = True

    for collection_name, query in VERIFY_QUERIES.items():
        if collections.get(collection_name, 0) == 0:
            print(f"  SKIP  {collection_name:<25}  (청크 없음)")
            continue

        try:
            col = client.get_collection(collection_name, embedding_function=embed_fn)
            res = col.query(query_texts=[query], n_results=1)
            docs = res["documents"][0] if res["documents"] else []

            if docs:
                preview = docs[0][:80].replace("\n", " ")
                print(f"  PASS  {collection_name:<25}  \"{preview}...\"")
            else:
                print(f"  FAIL  {collection_name:<25}  (검색 결과 없음)")
                all_pass = False
        except Exception as e:
            print(f"  ERROR {collection_name:<25}  {e}")
            all_pass = False

    print()
    if all_pass:
        print("  모든 컬렉션 검색 통과.")
    else:
        print("  일부 컬렉션 검색 실패. Ollama 실행 여부 및 시딩 상태를 확인하세요.")

    print()
    print(SEP)
    print("  완료")
    print(SEP)


if __name__ == "__main__":
    main()
