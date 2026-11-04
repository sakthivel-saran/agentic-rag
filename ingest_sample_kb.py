from pathlib import Path
from app.core.config import get_settings
from app.services.ingestion import load_file, chunk_documents
from app.rag.vectorstore import add_documents

settings = get_settings()

folder = Path(settings.sample_kb_dir)
if not folder.is_dir():
    raise FileNotFoundError(f"Sample knowledge folder does not exist: {folder}")

files = [p for p in folder.iterdir() if p.is_file()]
if not files:
    raise FileNotFoundError(f"No sample knowledge files found in: {folder}")

all_docs = []

for path in files:
    all_docs.extend(load_file(path))
chunks = chunk_documents(all_docs)
ids = add_documents(chunks)
print(f"indexed {len(files)} files ->  {len(chunks)} chunks -> {len(ids)} pinecone vectors")
