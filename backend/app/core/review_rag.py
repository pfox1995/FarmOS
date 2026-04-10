"""리뷰 RAG (Retrieval-Augmented Generation) 서비스.

# Design Ref: §3.2 — RAG 서비스 (임베딩 + 검색)
# Plan SC: SC-01 (리뷰 임베딩 → ChromaDB 저장 → 의미 검색이 동작한다)

학습 포인트:
    이 파일은 RAG의 "R" (Retrieval, 검색) 부분을 담당합니다.

    임베딩(Embedding)이란?
        텍스트를 숫자 배열(벡터)로 변환하는 것입니다.
        예: "딸기가 달아요" → [0.12, -0.34, 0.56, ...]  (768차원 벡터)
        의미가 비슷한 텍스트는 벡터 공간에서 가까이 위치합니다.

    임베딩 모델 선택이 중요한 이유:
        기본 모델(all-MiniLM-L6-v2)은 영어 중심이라 한국어 유사도가 부정확합니다.
        Ollama의 nomic-embed-text 모델은 다국어(한국어 포함)를 지원하여
        "포장이 엉망" 검색 시 실제 포장 관련 리뷰가 상위에 나옵니다.

    코사인 유사도(Cosine Similarity)란?
        두 벡터 간의 각도를 이용한 유사도 측정입니다.
        1.0 = 완전히 같은 의미
        0.0 = 전혀 관련 없음

    RAG 파이프라인에서의 위치:
        [리뷰 저장] → ChromaDB (이 파일)
        [질의 검색] → ChromaDB (이 파일) → 유사 리뷰 N개
        [LLM 분석] → review_analyzer.py (다음 파일)

사용 예시:
    from app.core.review_rag import ReviewRAG

    rag = ReviewRAG()

    # 리뷰 임베딩 저장
    rag.embed_reviews([
        {"id": "rev-01", "text": "딸기가 달아요", "rating": 5, "platform": "네이버", "date": "2026-03-01"}
    ])

    # 의미 검색
    results = rag.search("포장이 별로야", top_k=5)
    # → 포장 관련 리뷰가 유사도 순으로 반환됨
"""

import logging
from typing import Any

import httpx
from chromadb import EmbeddingFunction, Documents, Embeddings

from app.core.vectordb import get_client
from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "reviews_llama"
EMBED_MODEL = "llama3.1:8b"


class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """Ollama LLM을 사용하는 ChromaDB 임베딩 함수.

    학습 포인트:
        ChromaDB는 커스텀 임베딩 함수를 주입할 수 있습니다.
        EmbeddingFunction을 상속하고 __call__을 구현하면,
        add()나 query() 시 이 함수가 자동으로 호출됩니다.

        nomic-embed-text는 한국어를 지원하지 않아 모든 입력에 동일한 벡터를 반환합니다.
        llama3.1:8b는 다국어를 지원하여 한국어 의미를 정확히 구분합니다.

        예시 (검색어: "포장이 엉망이에요"):
          nomic-embed-text: 모든 결과 동일 (한국어 미지원)
          llama3.1:8b:      "멍투성이" 0.95, "당도 높아요" 0.89 ← 관련 리뷰가 상위
    """

    def __init__(self, base_url: str | None = None, model: str = EMBED_MODEL):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model

    def __call__(self, input: Documents) -> Embeddings:
        """텍스트 리스트를 임베딩 벡터 리스트로 변환."""
        embeddings = []
        for text in input:
            try:
                resp = httpx.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": text},
                    timeout=60.0,
                )
                resp.raise_for_status()
                embedding = resp.json()["embeddings"][0]
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Ollama 임베딩 실패: {e}")
                embeddings.append([0.0] * 4096)
        return embeddings


class ReviewRAG:
    """리뷰 벡터 저장 및 의미 검색 서비스.

    학습 포인트:
        이 클래스는 ChromaDB의 "reviews_nomic" 컬렉션을 관리합니다.
        컬렉션 = RDB의 테이블과 유사한 개념입니다.

        Ollama nomic-embed-text 모델을 임베딩 함수로 사용합니다.
        기본 영어 모델 대비 한국어 유사도 정확도가 크게 향상됩니다.
    """

    def __init__(self):
        client = get_client()
        self._embed_fn = OllamaEmbeddingFunction()
        self.collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # 임베딩 저장
    # ------------------------------------------------------------------

    def embed_reviews(self, reviews: list[dict]) -> int:
        """리뷰를 ChromaDB에 임베딩하여 저장합니다.

        학습 포인트:
            ChromaDB.add()에 텍스트(documents)를 넣으면,
            내장 임베딩 모델이 자동으로 벡터로 변환하여 저장합니다.

            메타데이터(metadatas)는 벡터와 함께 저장되어
            나중에 필터링에 사용할 수 있습니다.
            예: {"platform": "네이버"} → platform="네이버"인 리뷰만 검색

        Args:
            reviews: 리뷰 딕셔너리 리스트
                [{ id, text, rating, platform, date, product_id? }]

        Returns:
            저장된 리뷰 수
        """
        if not reviews:
            return 0

        ids = [str(r["id"]) for r in reviews]
        documents = [r["text"] for r in reviews]
        metadatas = [
            {
                "product_id": r.get("product_id", 0),
                "rating": r["rating"],
                "platform": r["platform"],
                "date": r["date"],
            }
            for r in reviews
        ]

        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
            logger.info(f"리뷰 {len(reviews)}건 임베딩 저장 완료")
            return len(reviews)
        except Exception as e:
            logger.error(f"리뷰 임베딩 저장 실패: {e}")
            raise

    def embed_reviews_chunked(self, reviews: list[dict], chunk_size: int = 10):
        """리뷰를 청크 단위로 임베딩하며 진행률을 yield합니다.

        학습 포인트:
            Generator(yield)를 사용하면 호출자가 진행 상황을
            한 단계씩 받아볼 수 있습니다.
            이걸 SSE(Server-Sent Events)와 결합하면
            프론트엔드에서 실시간 진행률 표시가 가능합니다.

        Yields:
            { "progress": 0~100, "embedded": int, "total": int, "message": str }
        """
        if not reviews:
            yield {"progress": 100, "embedded": 0, "total": 0, "message": "임베딩할 리뷰가 없습니다."}
            return

        total = len(reviews)
        embedded = 0

        for i in range(0, total, chunk_size):
            chunk = reviews[i:i + chunk_size]
            ids = [str(r["id"]) for r in chunk]
            documents = [r["text"] for r in chunk]
            metadatas = [
                {
                    "product_id": r.get("product_id", 0),
                    "rating": r["rating"],
                    "platform": r["platform"],
                    "date": r["date"],
                }
                for r in chunk
            ]

            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
            embedded += len(chunk)
            progress = int(embedded / total * 100)

            yield {
                "progress": progress,
                "embedded": embedded,
                "total": total,
                "message": f"{embedded}/{total}건 임베딩 완료",
            }

    # ------------------------------------------------------------------
    # 의미 검색
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict]:
        """자연어 질의로 유사 리뷰를 검색합니다.

        학습 포인트:
            ChromaDB.query()는 다음 과정을 거칩니다:
            1. query_texts를 벡터로 변환 (내장 임베딩 모델)
            2. 저장된 모든 벡터와 코사인 유사도 계산
            3. 유사도가 높은 순서로 상위 n_results개 반환

            where 파라미터로 메타데이터 필터를 추가할 수 있습니다.
            벡터 유사도 + 메타데이터 필터 = 정밀한 검색

        Args:
            query: 검색 질의 (예: "포장 관련 불만")
            top_k: 반환할 최대 결과 수 (기본 10)
            filters: 메타데이터 필터
                - platform: 플랫폼명 (예: "네이버스마트스토어")
                - rating_min: 최소 평점 (1~5)
                - rating_max: 최대 평점 (1~5)

        Returns:
            유사 리뷰 리스트 (유사도 내림차순)
            [{ id, text, similarity, metadata }]
        """
        where_filter = self._build_where_filter(filters)

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_filter if where_filter else None,
            )
            return self._format_query_results(results)
        except Exception as e:
            logger.error(f"리뷰 검색 실패: {e}")
            return []

    # ------------------------------------------------------------------
    # 전체 리뷰 조회
    # ------------------------------------------------------------------

    def get_all_reviews(self, limit: int = 100) -> list[dict]:
        """저장된 전체 리뷰를 조회합니다 (분석용).

        학습 포인트:
            ChromaDB.get()은 유사도 검색 없이 저장된 문서를 직접 가져옵니다.
            전체 리뷰를 LLM에 보내서 배치 분석할 때 사용합니다.
        """
        try:
            results = self.collection.get(limit=limit)
            return self._format_get_results(results)
        except Exception as e:
            logger.error(f"전체 리뷰 조회 실패: {e}")
            return []

    def get_count(self) -> int:
        """저장된 리뷰 수를 반환합니다."""
        return self.collection.count()

    # ------------------------------------------------------------------
    # Mock 데이터 동기화 (개발용)
    # ------------------------------------------------------------------

    def sync_from_mock(self, mock_reviews: list[dict]) -> int:
        """Mock 데이터를 ChromaDB에 동기화합니다 (개발용).

        학습 포인트:
            개발 초기에는 실제 DB 대신 Mock 데이터를 사용합니다.
            이미 저장된 리뷰는 스킵하고 새로운 것만 추가합니다.
            이렇게 하면 서버를 재시작해도 중복 저장되지 않습니다.

        Args:
            mock_reviews: Mock 리뷰 리스트
                [{ id, text, rating, platform, date }]

        Returns:
            새로 추가된 리뷰 수
        """
        existing = self.collection.get()
        existing_ids = set(existing["ids"]) if existing["ids"] else set()

        new_reviews = [
            r for r in mock_reviews
            if str(r["id"]) not in existing_ids
        ]

        if not new_reviews:
            logger.info("모든 Mock 리뷰가 이미 저장되어 있습니다")
            return 0

        added = self.embed_reviews(new_reviews)
        logger.info(f"Mock 리뷰 {added}건 새로 동기화 (기존 {len(existing_ids)}건)")
        return added

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _build_where_filter(self, filters: dict[str, Any] | None) -> dict | None:
        """ChromaDB where 필터를 구성합니다.

        학습 포인트:
            ChromaDB의 where 필터는 메타데이터 기반 필터링입니다.
            $eq(같음), $gte(이상), $lte(이하) 등의 연산자를 사용합니다.
            $and로 여러 조건을 결합할 수 있습니다.

            예시:
                {"platform": {"$eq": "네이버스마트스토어"}}
                {"$and": [{"rating": {"$gte": 1}}, {"rating": {"$lte": 3}}]}
        """
        if not filters:
            return None

        conditions = []

        if "platform" in filters and filters["platform"]:
            conditions.append({"platform": {"$eq": filters["platform"]}})

        if "rating_min" in filters and filters["rating_min"] is not None:
            conditions.append({"rating": {"$gte": filters["rating_min"]}})

        if "rating_max" in filters and filters["rating_max"] is not None:
            conditions.append({"rating": {"$lte": filters["rating_max"]}})

        if len(conditions) == 0:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}

    def _format_query_results(self, results: dict) -> list[dict]:
        """ChromaDB query() 결과를 API 응답 형식으로 변환합니다.

        학습 포인트:
            ChromaDB query()는 distances(거리)를 반환합니다.
            코사인 유사도 = 1 - distance
            distance=0 → 유사도=1.0 (완전 일치)
            distance=1 → 유사도=0.0 (전혀 다름)
        """
        formatted = []

        if not results["ids"] or not results["ids"][0]:
            return formatted

        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i] if results["distances"] else 0
            similarity = round(1 - distance, 4)

            formatted.append({
                "id": doc_id,
                "text": results["documents"][0][i],
                "similarity": similarity,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            })

        return formatted

    def _format_get_results(self, results: dict) -> list[dict]:
        """ChromaDB get() 결과를 변환합니다."""
        formatted = []

        if not results["ids"]:
            return formatted

        for i, doc_id in enumerate(results["ids"]):
            formatted.append({
                "id": doc_id,
                "text": results["documents"][i],
                "metadata": results["metadatas"][i] if results["metadatas"] else {},
            })

        return formatted
