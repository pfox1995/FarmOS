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

COLLECTION_NAME = "reviews_voyage_v35"


class LiteLLMEmbeddingFunction(EmbeddingFunction[Documents]):
    """LiteLLM 프록시 경유 임베딩 함수 (OpenAI 호환 /embeddings 엔드포인트).

    학습 포인트:
        LiteLLM은 인퍼런스를 하지 않고 HTTP 포워딩만 하는 프록시입니다.
        실제 임베딩 연산은 LiteLLM config에 등록된 외부 제공자에서 수행됩니다.
        예: VoyageAI, OpenAI, Cohere 등.

        N100 위에 LiteLLM이 올라가 있어도 N100은 요청을 외부로 중계만 하므로
        CPU 부하가 거의 0이며, 저사양 PC여도 병목이 발생하지 않습니다.

        모델 전환은 .env 의 EMBED_MODEL / EMBED_DIM 만 바꾸면 되며,
        차원이 바뀌면 COLLECTION_NAME 도 같이 바꿔서 전체 재임베딩합니다.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = base_url or settings.LITELLM_URL
        self.api_key = api_key or settings.LITELLM_API_KEY
        self.model = model or settings.EMBED_MODEL

    def __call__(self, input: Documents) -> Embeddings:
        """텍스트 리스트를 임베딩 벡터 리스트로 변환 (배치)."""
        batch_size = 64
        embeddings: list[list[float]] = []
        for i in range(0, len(input), batch_size):
            batch = list(input[i:i + batch_size])
            try:
                resp = httpx.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.model, "input": batch},
                    timeout=120.0,
                )
                resp.raise_for_status()
                data = resp.json()["data"]
                embeddings.extend([d["embedding"] for d in data])
            except Exception as e:
                logger.error(f"LiteLLM 임베딩 실패: {e}")
                embeddings.extend([[0.0] * settings.EMBED_DIM for _ in batch])
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
        self._embed_fn = LiteLLMEmbeddingFunction()
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

        # 이미 임베딩된 리뷰는 건너뛰기
        existing = self.collection.get()
        existing_ids = set(existing["ids"]) if existing["ids"] else set()
        new_reviews = [r for r in reviews if str(r["id"]) not in existing_ids]

        if not new_reviews:
            logger.info(f"리뷰 {len(reviews)}건 모두 이미 임베딩됨, 건너뜀")
            return 0

        ids = [str(r["id"]) for r in new_reviews]
        documents = [r["text"] for r in new_reviews]
        metadatas = [
            {
                "product_id": r.get("product_id", 0),
                "rating": r["rating"],
                "platform": r["platform"],
                "date": r["date"],
            }
            for r in new_reviews
        ]

        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
            logger.info(f"리뷰 {len(new_reviews)}건 임베딩 저장 완료 (기존 {len(existing_ids)}건 건너뜀)")
            return len(new_reviews)
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

        # 이미 임베딩된 리뷰는 건너뛰기
        existing = self.collection.get()
        existing_ids = set(existing["ids"]) if existing["ids"] else set()
        new_reviews = [r for r in reviews if str(r["id"]) not in existing_ids]
        skipped = len(reviews) - len(new_reviews)

        if not new_reviews:
            yield {"progress": 100, "embedded": 0, "total": 0,
                   "message": f"리뷰 {len(reviews)}건 모두 이미 임베딩됨, 건너뜀"}
            return

        if skipped > 0:
            logger.info(f"이미 임베딩된 리뷰 {skipped}건 건너뜀")

        total = len(new_reviews)
        embedded = 0

        for i in range(0, total, chunk_size):
            chunk = new_reviews[i:i + chunk_size]
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

    # 하이브리드 검색에서 키워드 일치 시 부여할 가산점
    KEYWORD_BOOST = 0.3

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict]:
        """하이브리드 검색: 벡터 유사도 + 키워드 매칭.

        학습 포인트:
            순수 벡터 검색만으로는 한계가 있습니다:
            - "당도" 검색 시 → "별로..." 같은 짧은 리뷰가 상위에 올 수 있음
            - LLM 임베딩은 문맥 유사도를 계산하지, 단어 일치를 보장하지 않음

            하이브리드 검색은 두 가지를 결합합니다:
            1. 벡터 유사도 (의미적으로 비슷한 리뷰)
            2. 키워드 부스팅 (검색어가 실제로 포함된 리뷰에 가산점)

            최종 점수 = 벡터 유사도 + (키워드 포함 시 KEYWORD_BOOST)

            이렇게 하면:
            - "당도" 검색 → "당도 14Brix 이상!" 이 1위로 올라옴
            - 의미적으로 유사하지만 키워드가 없는 리뷰도 여전히 포함됨

        Args:
            query: 검색 질의 (예: "포장 관련 불만")
            top_k: 반환할 최대 결과 수 (기본 10)
            filters: 메타데이터 필터

        Returns:
            유사 리뷰 리스트 (하이브리드 점수 내림차순)
            [{ id, text, similarity, metadata }]
        """
        where_filter = self._build_where_filter(filters)

        try:
            # 벡터 검색 (top_k보다 크게 가져와서 dedup 후에도 충분한 결과가 남도록)
            # 더미/시드 데이터에 동일 문장이 상품별로 반복 저장된 경우를 대비해
            # 넉넉히 fetch → 키워드 부스팅 → 텍스트 중복 제거 → top_k 반환
            fetch_count = min(max(top_k * 10, 50), 300)
            results = self.collection.query(
                query_texts=[query],
                n_results=fetch_count,
                where=where_filter if where_filter else None,
            )
            vector_results = self._format_query_results(results)

            # 키워드 부스팅: 검색어의 각 단어가 리뷰에 포함되면 가산점
            query_words = query.split()
            for r in vector_results:
                boost = 0.0
                for word in query_words:
                    if word in r["text"]:
                        boost = self.KEYWORD_BOOST
                        break
                r["similarity"] = round(r["similarity"] + boost, 4)

            # 하이브리드 점수로 재정렬
            vector_results.sort(key=lambda x: x["similarity"], reverse=True)

            # 텍스트 기반 중복 제거 — 동일 content 는 가장 높은 점수 1건만 유지
            # (상품은 달라도 리뷰 본문이 같은 시드 데이터의 시각적 중복을 제거)
            seen_texts: set[str] = set()
            deduped: list[dict] = []
            for r in vector_results:
                text_key = r.get("text", "").strip()
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)
                deduped.append(r)
                if len(deduped) >= top_k:
                    break
            return deduped

        except Exception as e:
            logger.error(f"리뷰 검색 실패: {e}")
            return []

    # ------------------------------------------------------------------
    # 전체 리뷰 조회
    # ------------------------------------------------------------------

    def get_all_reviews(self) -> list[dict]:
        """저장된 전체 리뷰를 조회합니다 (분석용).

        학습 포인트:
            ChromaDB.get()은 유사도 검색 없이 저장된 문서를 직접 가져옵니다.
            전체 리뷰를 LLM에 보내서 배치 분석할 때 사용합니다.
        """
        try:
            results = self.collection.get()
            return self._format_get_results(results)
        except Exception as e:
            logger.error(f"전체 리뷰 조회 실패: {e}")
            return []

    def get_count(self) -> int:
        """저장된 리뷰 수를 반환합니다."""
        return self.collection.count()

    # ------------------------------------------------------------------
    # DB 동기화 (shop_reviews → ChromaDB)
    # ------------------------------------------------------------------

    async def sync_from_db(self, db) -> int:
        """shop_reviews 테이블에서 리뷰를 조회하여 ChromaDB에 동기화합니다.

        Plan Ref: FR-01 (DB 연동)
        Design Ref: §4.2 (sync_from_db)

        Args:
            db: AsyncSession (asyncpg)

        Returns:
            새로 임베딩된 리뷰 수
        """
        from sqlalchemy import text as sa_text

        result = await db.execute(
            sa_text("""
                SELECT id, product_id, user_id, rating, content, created_at
                FROM shop_reviews
                WHERE content IS NOT NULL AND content != ''
            """)
        )
        rows = result.fetchall()

        if not rows:
            logger.info("shop_reviews에 리뷰가 없습니다")
            return 0

        reviews = [
            {
                "id": f"review-{row.id}",
                "text": row.content,
                "rating": row.rating,
                "platform": "",
                "date": row.created_at.strftime("%Y-%m-%d") if row.created_at else "",
                "product_id": row.product_id or 0,
            }
            for row in rows
        ]

        added = self.embed_reviews(reviews)
        logger.info(f"DB 리뷰 {added}건 새로 동기화 (전체 {len(rows)}건 중)")
        return added

    async def sync_from_db_chunked(self, db, chunk_size: int = 100):
        """DB 리뷰를 청크 단위로 임베딩하며 진행률을 yield합니다 (SSE용)."""
        from sqlalchemy import text as sa_text

        result = await db.execute(
            sa_text("""
                SELECT id, product_id, user_id, rating, content, created_at
                FROM shop_reviews
                WHERE content IS NOT NULL AND content != ''
            """)
        )
        rows = result.fetchall()

        if not rows:
            yield {"progress": 100, "embedded": 0, "total": 0, "message": "DB에 리뷰가 없습니다."}
            return

        reviews = [
            {
                "id": f"review-{row.id}",
                "text": row.content,
                "rating": row.rating,
                "platform": "",
                "date": row.created_at.strftime("%Y-%m-%d") if row.created_at else "",
                "product_id": row.product_id or 0,
            }
            for row in rows
        ]

        for update in self.embed_reviews_chunked(reviews, chunk_size=chunk_size):
            yield update

    # ------------------------------------------------------------------
    # 멀티테넌트 조회 (Design §4.2)
    # ------------------------------------------------------------------

    def get_reviews_by_products(self, product_ids: list[int], top_k: int = 100) -> list[dict]:
        """특정 상품 ID의 리뷰만 조회합니다 (멀티테넌트).

        Args:
            product_ids: 필터링할 상품 ID 리스트
            top_k: 최대 반환 수

        Returns:
            해당 상품들의 리뷰 리스트
        """
        try:
            results = self.collection.get(
                where={"product_id": {"$in": product_ids}},
                limit=top_k,
            )
            return self._format_get_results(results)
        except Exception as e:
            logger.error(f"상품별 리뷰 조회 실패: {e}")
            return []

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
