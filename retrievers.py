from langchain_community.retrievers import (
    BM25Retriever
)


OVERVIEW_KEYWORDS = [
    "purpose",
    "overview",
    "project",
    "about",
    "problem",
    "goal",
    "objective",
    "repository",
    "system"
]


def normalize_queries(
    queries
):

    if isinstance(
        queries,
        str
    ):

        queries = [queries]

    seen = set()

    normalized = []

    for query in queries:

        query = str(query).strip()

        if not query:

            continue

        key = query.lower()

        if key not in seen:

            seen.add(key)

            normalized.append(query)

    return normalized


def is_overview_query(
    query
):

    query = query.lower()

    return any(
        keyword in query
        for keyword in OVERVIEW_KEYWORDS
    )


class HybridRetriever:

    def __init__(
        self,
        vectordb,
        documents
    ):

        self.documents = documents

        if vectordb is not None:
            self.dense_retriever = (
                vectordb.as_retriever(
                    search_kwargs={"k": 30}
                )
            )

        self.bm25_retriever = (
            BM25Retriever.from_documents(
                documents
            )
        )

        self.bm25_retriever.k = 30

    def add_ranked_docs(
        self,
        scores,
        docs_by_id,
        docs,
        k=60
    ):

        for rank, doc in enumerate(
            docs
        ):

            doc_id = (
                str(
                    doc.metadata.get(
                        "file_path",
                        ""
                    )
                )
                + "::"
                + doc.page_content
            )

            docs_by_id[
                doc_id
            ] = doc

            scores[
                doc_id
            ] = (
                scores.get(
                    doc_id,
                    0
                )
                + 1 / (
                    k
                    + rank
                    + 1
                )
            )

    def get_readme_docs(
        self
    ):

        return self.get_docs_by_chunk_type(
            "readme"
        )

    def get_docs_by_chunk_type(
        self,
        chunk_type
    ):

        docs = []

        for doc in self.documents:

            if (
                doc.metadata.get(
                    "chunk_type"
                )
                == chunk_type
            ):

                docs.append(
                    doc
                )

        return docs

    def retrieve(
        self,
        queries,
        top_k=30,
        preferred_chunk_types=None,
        include_readme=None,
        include_repo_profile=False
    ):

        queries = (
            normalize_queries(
                queries
            )
        )

        scores = {}

        docs_by_id = {}

        for query in queries:

            dense_docs = []
            if hasattr(self, "dense_retriever") and self.dense_retriever is not None:
                dense_docs = (
                    self.dense_retriever
                    .invoke(query)
                )

            sparse_docs = (
                self.bm25_retriever
                .invoke(query)
            )

            self.add_ranked_docs(
                scores,
                docs_by_id,
                dense_docs
            )

            self.add_ranked_docs(
                scores,
                docs_by_id,
                sparse_docs
            )

        if any(
            is_overview_query(
                query
            )
            for query
            in queries
        ) or include_readme:

            self.add_ranked_docs(
                scores,
                docs_by_id,
                self.get_readme_docs()
            )

        if include_repo_profile:

            self.add_ranked_docs(
                scores,
                docs_by_id,
                self.get_docs_by_chunk_type(
                    "repo_profile"
                ),
                k=10
            )

        for chunk_type in (
            preferred_chunk_types
            or []
        ):

            self.add_ranked_docs(
                scores,
                docs_by_id,
                self.get_docs_by_chunk_type(
                    chunk_type
                ),
                k=90
            )

        ranked = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            docs_by_id[doc_id]
            for doc_id, _
            in ranked[:top_k]
        ]


def build_hybrid_retriever(
    vectordb,
    documents
):

    return HybridRetriever(
        vectordb,
        documents
    )
