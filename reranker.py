def rerank_documents(
    query,
    documents,
    top_k=12
):
    """Return documents as-is (no CrossEncoder reranking) to avoid OOM on low-memory hosts like Render."""
    if not documents:
        return []

    return documents[:top_k]