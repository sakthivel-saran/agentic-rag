from app.services.ingestion import load_file, chunk_documents
from app.rag.vectorstore import add_documents
docs = load_file(path="data/sample kb/company_it_handbook.md")
chunks = chunk_documents(docs)
add_documents(chunks)
print(len(chunks))
