"""ChromaDB RAG 데이터 적재 스크립트.

실행: uv run python ai/seed_rag.py

정책 문서(PDF/DOCX)는 DOCS_DIR 경로에 위치해야 합니다.
새 문서 추가 시 DOC_TO_COLLECTION에 파일명과 컬렉션명 매핑을 추가하세요.
"""
import json
import os
import re
import sys

# shopping_mall/backend를 sys.path에 추가 (python ai/seed_rag.py 직접 실행 시 필요)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.paths import CHROMA_DB_PATH, AI_DATA_DIR
from ai.embeddings import get_embedding_function

DATA_DIR = str(AI_DATA_DIR)
CHROMA_DIR = CHROMA_DB_PATH
DOCS_DIR = settings.policy_docs_dir

# 파일명(부분 일치) → ChromaDB 컬렉션명 매핑
DOC_TO_COLLECTION: dict[str, str] = {
    "01_주문및결제정책": "payment_policy",
    "02_배송정책": "delivery_policy",
    "03_반품교환환불정책": "return_policy",
    "04_상품품질신선도보증정책": "quality_policy",
    "05_고객서비스운영정책": "service_policy",
    "06_개인정보처리및회원정책": "membership_policy",
}


# ── 문서 파싱 ──────────────────────────────────────────────────────────────

def parse_pdf(path: str) -> str:
    """PDF 파일에서 전체 텍스트 추출."""
    from pypdf import PdfReader
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


def parse_docx(path: str) -> str:
    """DOCX 파일에서 전체 텍스트 추출 (단락 단위)."""
    from docx import Document
    doc = Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def parse_document(path: str) -> str:
    """확장자에 따라 PDF 또는 DOCX 파싱."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return parse_pdf(path)
    elif ext == ".docx":
        return parse_docx(path)
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {ext}")


# ── 청킹 ──────────────────────────────────────────────────────────────────

# 섹션 헤딩 패턴: "1.", "1.1", "2.3.4" 로 시작하는 줄
_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$", re.MULTILINE)

def chunk_by_sections(text: str, source: str) -> list[dict]:
    """섹션 헤딩 기준으로 텍스트를 청크로 분할.

    Returns:
        [{"id": str, "text": str, "metadata": dict}, ...]
    """
    # 헤딩 위치 목록
    matches = list(_HEADING_RE.finditer(text))

    if not matches:
        # 헤딩이 없으면 전체를 하나의 청크로
        return [{
            "id": f"{source}_chunk_0",
            "text": text.strip(),
            "metadata": {"source": source, "section": "전체"},
        }]

    chunks = []
    for i, match in enumerate(matches):
        section_num = match.group(1)
        section_title = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        content = text[start:end].strip()
        if not content:
            continue

        chunk_id = f"{source}_s{section_num.replace('.', '_')}"
        chunks.append({
            "id": chunk_id,
            "text": content,
            "metadata": {
                "source": source,
                "section": f"{section_num} {section_title}",
                "section_num": section_num,
            },
        })

    return chunks


# ── ChromaDB 적재 ──────────────────────────────────────────────────────────

def seed_policy_collection(client, ef, filepath: str, collection_name: str) -> int:
    """문서 파일 파싱 → 청킹 → ChromaDB 컬렉션에 적재.

    Returns:
        적재된 청크 수
    """
    filename = os.path.basename(filepath)
    print(f"  파싱 중: {filename}")

    try:
        text = parse_document(filepath)
    except Exception as e:
        print(f"  [오류] 파싱 실패: {e}")
        return 0

    # 파일명에서 소스 식별자 추출 (공백/괄호 제거)
    source = re.sub(r"[\s\(\)]+", "_", os.path.splitext(filename)[0]).strip("_")
    chunks = chunk_by_sections(text, source)

    if not chunks:
        print(f"  [경고] 청크 없음: {filename}")
        return 0

    col = client.get_or_create_collection(name=collection_name, embedding_function=ef)
    col.upsert(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )
    count = col.count()
    print(f"  → {collection_name}: {count}개 청크 적재 완료")
    return count


# ── 기존 컬렉션 (JSON 기반) ────────────────────────────────────────────────

def load_json(filename: str) -> list:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"[경고] 파일 없음: {path} — 해당 컬렉션을 건너뜁니다.")
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def seed_faq(client, ef) -> int:
    data = load_json("faq.json")
    if not data:
        return 0

    col = client.get_or_create_collection(name="faq", embedding_function=ef)

    ids, documents, metadatas = [], [], []
    for item in data:
        chunk_text = f"Q: {item['question']}\nA: {item['answer']}"
        ids.append(item["id"])
        documents.append(chunk_text)
        metadatas.append({
            "type": "faq",
            "intent": item["intent"],
            "faq_id": item["id"],
        })

    col.upsert(documents=documents, metadatas=metadatas, ids=ids)
    return col.count()


def seed_storage_guide(client, ef) -> int:
    data = load_json("storage_guide.json")
    if not data:
        return 0

    col = client.get_or_create_collection(name="storage_guide", embedding_function=ef)

    ids, documents, metadatas = [], [], []
    for item in data:
        ids.append(item["id"])
        documents.append(item["guide"])
        metadatas.append({
            "type": "storage",
            "product_name": item["product"],
            "category": item["category"],
        })

    col.upsert(documents=documents, metadatas=metadatas, ids=ids)
    return col.count()


def seed_season_info(client, ef) -> int:
    data = load_json("season_info.json")
    if not data:
        return 0

    col = client.get_or_create_collection(name="season_info", embedding_function=ef)

    ids, documents, metadatas = [], [], []
    for item in data:
        products_text = ", ".join(item["products"]) if item["products"] else "없음"
        doc_text = f"{item['season']} 제철 상품: {products_text}\n{item['description']}"
        ids.append(item["id"])
        documents.append(doc_text)
        metadatas.append({
            "type": "season",
            "season": item["season"],
        })

    col.upsert(documents=documents, metadatas=metadatas, ids=ids)
    return col.count()


# ── 진입점 ─────────────────────────────────────────────────────────────────

def find_policy_files() -> list[tuple[str, str]]:
    """DOCS_DIR에서 DOC_TO_COLLECTION 매핑에 해당하는 파일을 찾아 반환.

    Returns:
        [(filepath, collection_name), ...]
    """
    if not os.path.isdir(DOCS_DIR):
        print(f"[경고] 정책 문서 폴더 없음: {DOCS_DIR}")
        return []

    found = []
    for fname in sorted(os.listdir(DOCS_DIR)):
        fpath = os.path.join(DOCS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in (".pdf", ".docx"):
            continue
        # 파일명 키와 부분 일치 확인
        for key, collection in DOC_TO_COLLECTION.items():
            if key in fname:
                found.append((fpath, collection))
                break
        else:
            print(f"  [건너뜀] 매핑 없음: {fname}")

    return found


def main():
    try:
        import chromadb
    except ImportError:
        print("[오류] chromadb 설치 필요: uv add chromadb")
        sys.exit(1)

    # 기존 chroma_data 전체 삭제 — 개별 컬렉션 삭제 시 HNSW 인덱스 파일이
    # 디스크에 남아 "Nothing found on disk" 오류를 일으키므로 전체 초기화
    import shutil
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
        print(f"기존 ChromaDB 삭제: {CHROMA_DIR}")

    print(f"ChromaDB 초기화 중... ({CHROMA_DIR})")
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        ef = get_embedding_function()
        print(f"임베딩 provider: {settings.embed_provider}")
    except Exception as e:
        print(f"[오류] 임베딩 함수 초기화 실패: {e}")
        print(f"  → EMBED_PROVIDER={settings.embed_provider} 설정을 확인하세요.")
        sys.exit(1)

    # ── JSON 기반 컬렉션 ──
    print("\n[JSON 컬렉션 적재]")
    faq_count = seed_faq(client, ef)
    print(f"  faq: {faq_count}개")
    storage_count = seed_storage_guide(client, ef)
    print(f"  storage_guide: {storage_count}개")
    season_count = seed_season_info(client, ef)
    print(f"  season_info: {season_count}개")

    # ── 정책 문서 적재 ──
    print(f"\n[정책 문서 적재] 경로: {DOCS_DIR}")
    policy_files = find_policy_files()

    if not policy_files:
        print("  적재할 정책 문서 없음.")
    else:
        policy_totals = {}
        for fpath, collection in policy_files:
            count = seed_policy_collection(client, ef, fpath, collection)
            policy_totals[collection] = count

        print("\n정책 컬렉션 요약:")
        for col, cnt in policy_totals.items():
            print(f"  {col}: {cnt}개 청크")

    print(f"\n완료. ChromaDB 저장 경로: {os.path.abspath(CHROMA_DIR)}")
    return client, ef


if __name__ == "__main__":
    main()
