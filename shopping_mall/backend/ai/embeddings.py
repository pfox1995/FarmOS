"""임베딩 함수 팩토리.

EMBED_PROVIDER 설정에 따라 ChromaDB 임베딩 함수를 반환합니다.

지원 provider:
  openrouter          — OpenRouter Embeddings API (PRIMARY_LLM_API_KEY 재사용, 추가 설정 불필요)
  ollama              — 로컬 Ollama 서버 (OLLAMA_BASE_URL + OLLAMA_EMBED_MODEL 사용)
  sentence_transformers — HuggingFace 모델 로컬 실행 (API 키·서버 불필요, uv add sentence-transformers만 필요)
  openai              — OpenAI Embeddings API 또는 호환 엔드포인트 (EMBED_API_KEY 필요)

⚠️  시딩(seed_rag.py)과 쿼리(rag.py)는 반드시 동일한 provider + model을 사용해야 합니다.
    provider/model을 바꾸면 반드시 re-seed 하세요.
"""
from app.core.config import settings

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_embedding_function():
    """설정(EMBED_PROVIDER)에 따라 ChromaDB 임베딩 함수를 반환.

    Raises:
        ValueError: 지원하지 않는 provider일 때
        ImportError: 필요한 패키지가 설치되지 않았을 때
        Exception: provider 초기화 실패 시
    """
    provider = settings.embed_provider.lower()

    if provider == "openrouter":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        model = settings.embed_model or "openai/text-embedding-3-small"
        # PRIMARY_LLM_API_KEY를 기본으로 재사용 — 별도 키 불필요
        api_key = settings.embed_api_key or settings.primary_llm_api_key
        if not api_key:
            raise ValueError("openrouter requires a non-empty API key (EMBED_API_KEY 또는 PRIMARY_LLM_API_KEY)")
        return OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=model,
            api_base=_OPENROUTER_BASE_URL,
        )

    elif provider == "ollama":
        from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
        return OllamaEmbeddingFunction(
            url=f"{settings.ollama_base_url}/api/embeddings",
            model_name=settings.ollama_embed_model,
        )

    elif provider == "sentence_transformers":
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        model = settings.embed_model or "jhgan/ko-sroberta-multitask"
        return SentenceTransformerEmbeddingFunction(model_name=model)

    elif provider == "openai":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        if not settings.embed_api_key:
            raise ValueError("openai requires a non-empty API key (EMBED_API_KEY)")
        model = settings.embed_model or "text-embedding-3-small"
        kwargs: dict = {
            "api_key": settings.embed_api_key,
            "model_name": model,
        }
        if settings.embed_base_url:
            kwargs["api_base"] = settings.embed_base_url
        return OpenAIEmbeddingFunction(**kwargs)

    else:
        raise ValueError(
            f"지원하지 않는 EMBED_PROVIDER: '{provider}'. "
            "openrouter | ollama | sentence_transformers | openai 중 하나를 선택하세요."
        )
