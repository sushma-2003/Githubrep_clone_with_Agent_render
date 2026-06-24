from document_loader import load_repository_documents


def create_vector_store(repo_path):
    documents = load_repository_documents(repo_path)
    print(f"Documents loaded: {len(documents)}")
    if not documents:
        raise ValueError("No documents were loaded from repository.")

    # Skip ChromaDB + embedding model to stay under Render's 512MB.
    # Return None for vectordb and only use BM25 in the retriever.
    return None, documents