"""RAG (Retrieval-Augmented Generation) service using ChromaDB."""
import logging
from typing import Optional

from app.core.config import settings
from app.paths import CHROMA_DB_PATH
from ai.embeddings import get_embedding_function

logger = logging.getLogger(__name__)


class RAGService:
    """RAG service with ChromaDB for document retrieval and LLM for generation."""

    def __init__(self, persist_directory: str | None = None):
        self.chroma_client = None
        self._ef = None
        if persist_directory is None:
            persist_directory = CHROMA_DB_PATH
        self._init_chroma(persist_directory)

    def _init_chroma(self, persist_directory: str):
        """Initialize ChromaDB client. Gracefully handles unavailability."""
        try:
            import chromadb
            self.chroma_client = chromadb.PersistentClient(path=persist_directory)
            self._ef = get_embedding_function()
            logger.info("ChromaDB initialized (provider=%s).", settings.embed_provider)
        except Exception as e:
            logger.warning(f"ChromaDB initialization failed: {e}. RAG will use fallback.")
            self.chroma_client = None

    def _get_collection(self, collection_name: str):
        """Get a ChromaDB collection with embedding function."""
        if self.chroma_client is None:
            return None
        try:
            return self.chroma_client.get_collection(
                name=collection_name,
                embedding_function=self._ef,
            )
        except Exception as e:
            logger.error(
                f"Failed to get collection '{collection_name}': {e}. "
                "seed_rag.py를 먼저 실행하세요: uv run python ai/seed_rag.py"
            )
            return None

    def retrieve(
        self,
        question: str,
        collection: str,
        top_k: int = 3,
        distance_threshold: float = 0.5,
        where: dict | None = None,
    ) -> list[str]:
        """ChromaDB에서 관련 문서를 검색하고 거리 필터링 후 반환.

        Args:
            question: 검색 질문
            collection: 컬렉션 이름
            top_k: 최대 반환 수
            distance_threshold: 이 값 미만의 거리(유사도)인 문서만 반환
            where: 메타데이터 필터 (선택)

        Returns:
            필터링된 문서 텍스트 리스트. 관련 문서 없으면 빈 리스트.
        """
        col = self._get_collection(collection)
        if col is None:
            return []

        try:
            kwargs: dict = {
                "query_texts": [question],
                "n_results": top_k,
                "include": ["documents", "distances"],
            }
            if where:
                kwargs["where"] = where

            results = col.query(**kwargs)
            documents = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]

            filtered = [
                doc for doc, dist in zip(documents, distances)
                if dist < distance_threshold
            ]
            return filtered

        except Exception as e:
            logger.warning(f"RAG retrieve failed (collection={collection}): {e}")
            return []

    def retrieve_multiple(
        self,
        question: str,
        collections: list[str],
        top_k_per: int = 2,
        distance_threshold: float = 0.5,
    ) -> list[str]:
        """여러 컬렉션에서 검색하여 결과를 합산.

        Args:
            question: 검색 질문
            collections: 검색할 컬렉션 이름 목록
            top_k_per: 컬렉션당 최대 반환 수
            distance_threshold: 거리 필터

        Returns:
            모든 컬렉션에서 수집된 관련 문서 리스트 (중복 제거)
        """
        seen = set()
        all_docs = []
        for col_name in collections:
            docs = self.retrieve(question, col_name, top_k_per, distance_threshold)
            for doc in docs:
                if doc not in seen:
                    seen.add(doc)
                    all_docs.append(doc)
        return all_docs

    def add_documents(self, collection: str, docs: list[dict]) -> int:
        """Add documents to a ChromaDB collection.
        Each doc should have 'id', 'text', and optional 'metadata'.
        Returns count of added documents.
        """
        col = self._get_collection(collection)
        if col is None:
            logger.warning("Cannot add documents: ChromaDB not available.")
            return 0

        try:
            ids = [d["id"] for d in docs]
            texts = [d["text"] for d in docs]
            metadatas = [d.get("metadata", {}) for d in docs]
            col.add(documents=texts, ids=ids, metadatas=metadatas)
            return len(docs)
        except Exception as e:
            logger.warning(f"Failed to add documents: {e}")
            return 0
