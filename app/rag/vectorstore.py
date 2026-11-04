import time
from pinecone import Pinecone, ServerlessSpec
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.embeddings import Embeddings
from openai import OpenAI
from google import genai
from google.genai import types
from app.core.config import get_settings

settings = get_settings()

_embeddings = None
_vectorstore = None

EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "all-minilm-l6-v2": 384,
    "nvidia/nemotron-3-embed-1b": 2048,
    "gemini-embedding-001": 3072,
  
}


def get_embedding_dimension(model_name: str| None = None) -> int:
    name = (model_name or settings.embedding_model or "").strip()
    if not name:
        raise RuntimeError("Embedding model is not configures")

    normalized = name.lower()
    if normalized in EMBEDDING_DIMENSIONS:
        return EMBEDDING_DIMENSIONS[normalized]
    if "text-embedding-3-small" in normalized:
        return 1536
    if "text-embedding-3-large" in normalized:
        return 3072
    if "text-embedding-ada-002" in normalized:
        return 1536
    if "all-minilm" in normalized:
        return 384
    if normalized == "nvidia/nemotron-3-embed-1b":
        return 2048
    if normalized == "gemini-embedding-001":
        return 3072


    raise ValueError(
        f"unsupported embedding model: '{model_name or settings.embedding_model}' for Pinecone. "
        "add the matching dimension to the EMBEDDING_DIMENSIONS ."
    )

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        model_name = settings.embedding_model.strip()
        if model_name.lower() == "gemini-embedding-001":
            if not settings.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is required for the configured Gemini embedding model")
            _embeddings = GeminiEmbeddings(settings.gemini_api_key, model_name)
        elif model_name.lower().startswith("nvidia/"):
            if not settings.nvidia_api_key:
                raise RuntimeError("NVIDIA_API_KEY is required for the configured NVIDIA embedding model")
            _embeddings = NvidiaEmbeddings(settings.nvidia_api_key, model_name)
        elif model_name.lower().startswith("text-embedding-"):
            if not settings.openai_api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is required for the configured embedding model "
                    f"'{model_name}'. Set a funded key, or set EMBEDDING_MODEL="
                    "sentence-transformers/all-MiniLM-L6-v2 to use local embeddings."
                )
            _embeddings = OpenAIEmbeddings(
                model=model_name,
                openai_api_key=settings.openai_api_key,
            )
        else:
            _embeddings = HuggingFaceEmbeddings(model_name=model_name)
    return _embeddings


class NvidiaEmbeddings(Embeddings):
    """NVIDIA NIM embeddings with distinct passage and query modes."""

    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        self.model = model

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            extra_body={"input_type": input_type},
        )
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "passage")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]


class GeminiEmbeddings(Embeddings):
    """Gemini embeddings with retrieval-specific document and query task types."""

    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        response = self.client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=3072,
            ),
        )
        return [item.values for item in response.embeddings]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]


def ensure_index():
    if not settings.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is missing")

    desired_dimension = get_embedding_dimension()
    pc = Pinecone(api_key=settings.pinecone_api_key)
    names = [x["name"] for x in pc.list_indexes()]

    if settings.pinecone_index_name in names:
        index_info = pc.describe_index(settings.pinecone_index_name)
        current_dimension = getattr(index_info, "dimension", None)
        if current_dimension is None and isinstance(index_info, dict):
            current_dimension = index_info.get("dimension")

        if current_dimension is not None and current_dimension != desired_dimension:
            raise RuntimeError(
                f"Pinecone index '{settings.pinecone_index_name}' has dimension "
                f"{current_dimension}, but embedding model '{settings.embedding_model}' "
                f"requires {desired_dimension}. Choose a new index name or migrate/rebuild "
                "the index; the existing index was left untouched."
            )

    if settings.pinecone_index_name not in [x["name"] for x in pc.list_indexes()]:
        pc.create_index(
            name=settings.pinecone_index_name,
            dimension=desired_dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        while not pc.describe_index(settings.pinecone_index_name).status["ready"]:
            time.sleep(1)

    return pc.Index(settings.pinecone_index_name)




def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        index = ensure_index()
        _vectorstore = PineconeVectorStore(
            index=index,
            embedding=get_embeddings(),
            namespace=settings.pinecone_namespace,
        )
    return _vectorstore



def get_retriever():
    return get_vectorstore().as_retriever(search_kwargs={"k": settings.top_k})



def add_documents(chunks):
    store = get_vectorstore()
    return store.add_documents(chunks)
