"""RAG (Retrieval-Augmented Generation) service using ChromaDB."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RAGService:
    """RAG service with ChromaDB for document retrieval and LLM for generation."""

    def __init__(self, llm_client, persist_directory: str = "./chroma_data"):
        self.llm_client = llm_client
        self.chroma_client = None
        self._init_chroma(persist_directory)

    def _init_chroma(self, persist_directory: str):
        """Initialize ChromaDB client. Gracefully handles unavailability."""
        try:
            import chromadb
            self.chroma_client = chromadb.PersistentClient(path=persist_directory)
            logger.info("ChromaDB initialized successfully.")
        except Exception as e:
            logger.warning(f"ChromaDB initialization failed: {e}. RAG will use fallback.")
            self.chroma_client = None

    def _get_collection(self, collection_name: str):
        """Get or create a ChromaDB collection."""
        if self.chroma_client is None:
            return None
        try:
            return self.chroma_client.get_or_create_collection(name=collection_name)
        except Exception as e:
            logger.warning(f"Failed to get collection '{collection_name}': {e}")
            return None

    async def query(self, question: str, collection: str = "faq", top_k: int = 3) -> str:
        """Query documents and generate an answer using RAG."""
        col = self._get_collection(collection)
        if col is None:
            return await self._fallback_answer(question)

        try:
            results = col.query(query_texts=[question], n_results=top_k)
            documents = results.get("documents", [[]])[0]
            if not documents:
                return await self._fallback_answer(question)

            context = "\n".join(documents)
            prompt = (
                f"다음 참고 자료를 바탕으로 질문에 답변하세요.\n\n"
                f"참고 자료:\n{context}\n\n"
                f"질문: {question}\n\n"
                f"답변:"
            )
            return await self.llm_client.generate(
                prompt,
                system="당신은 농산물 쇼핑몰 고객 지원 전문가입니다. 참고 자료를 기반으로 정확하게 답변하세요.",
            )
        except Exception as e:
            logger.warning(f"RAG query failed: {e}")
            return await self._fallback_answer(question)

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

    async def _fallback_answer(self, question: str) -> str:
        """Provide a fallback answer when RAG is unavailable."""
        question_lower = question.lower()

        if any(kw in question_lower for kw in ["보관", "저장", "냉장", "냉동"]):
            return (
                "일반적으로 신선 농산물은 냉장(0-5도) 보관을 권장합니다. "
                "과일류는 신문지로 감싸 냉장 보관하면 신선도를 오래 유지할 수 있습니다. "
                "자세한 보관법은 상품 상세 페이지를 참고해 주세요."
            )

        if any(kw in question_lower for kw in ["제철", "시즌", "계절"]):
            return (
                "봄: 딸기, 냉이, 봄동 / 여름: 수박, 참외, 토마토 / "
                "가을: 사과, 배, 감 / 겨울: 감귤, 시금치, 무. "
                "제철 농산물이 가장 맛있고 영양가가 높습니다."
            )

        if any(kw in question_lower for kw in ["교환", "환불", "반품"]):
            return (
                "신선식품 특성상 단순 변심으로 인한 교환/환불은 어렵습니다. "
                "상품 하자 시 수령 후 24시간 이내에 사진과 함께 고객센터로 문의해 주세요."
            )

        return "죄송합니다. 해당 질문에 대한 정보를 찾을 수 없습니다. 고객센터(1588-0000)로 문의해 주세요."
