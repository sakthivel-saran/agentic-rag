from pathlib import Path
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.rag.workflow import ask
from app.rag.vectorstore import add_documents
from app.services.ingestion import load_file, chunk_documents
from app.services.audit import write_audit

router = APIRouter(prefix="/api")
settings = get_settings()
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=3000)

@router.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}

@router.post("/chat")
def chat(payload: ChatRequest):
    try:
        result = ask(payload.question)
        write_audit(payload.question, result["source_used"], result.get("trace", []))

        return {
            "answer": result["answer"],
            "source_used": result["source_used"],
            "trace": result.get("trace",[]),
            "citations": result.get("citations", []),
            "rewritten_query": result.get("current_query", payload.question),
        
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ingest")
async def ingest(file: UploadFile = File(...), x_admin_key: str = Header(default="")):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Supported: {', '.join(sorted(SUPPORTED))}")
    dest = Path(settings.upload_dir) / Path(file.filename).name
    stage = "saving the uploaded file"
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="The uploaded file is empty")
        dest.write_bytes(contents)

        stage = "reading the document"
        docs = load_file(dest)
        if not docs or not any(doc.page_content.strip() for doc in docs):
            raise HTTPException(status_code=400, detail="No readable text was found in the document")

        stage = "splitting the document into chunks"
        chunks = chunk_documents(docs)
        if not chunks:
            raise HTTPException(status_code=400, detail="No text chunks could be created from the document")

        stage = "embedding and indexing chunks in Pinecone"
        ids = add_documents(chunks)
        return {"message": "Document indexed", "file": dest.name, "chunks": len(chunks), "ids_created": len(ids)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Document ingestion failed while %s (%s)", stage, dest.name)
        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed while {stage}: {type(exc).__name__}: {exc}",
        ) from exc
