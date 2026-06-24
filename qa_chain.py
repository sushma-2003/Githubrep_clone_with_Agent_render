import os
import json

from dotenv import (
    load_dotenv
)

from langchain_groq import (
    ChatGroq
)

from langchain_core.prompts import (
    ChatPromptTemplate
)

from langchain_core.output_parsers import (
    StrOutputParser
)

from prompts import (
    SYSTEM_PROMPT
)

from reranker import (
    rerank_documents
)

from retrievers import (
    build_hybrid_retriever
)

from agent_planner import (
    create_retrieval_plan
)

from context_validator import (
    validate_context
)

from repo_analyzer import (
    RepositoryAnalysisAgent
)


load_dotenv()


DEBUG_MODE = (
    os.getenv(
        "DEBUG_RETRIEVAL",
        "0"
    )
    == "1"
)


def merge_context_docs(
    primary_docs,
    secondary_docs,
    max_docs=12
):

    merged = []

    seen = set()

    for doc in (
        list(primary_docs)
        + list(secondary_docs)
    ):

        key = (
            doc.page_content
            .strip()
        )

        if (
            not key
            or key in seen
        ):
            continue

        seen.add(key)

        merged.append(doc)

        if (
            len(merged)
            >= max_docs
        ):
            break

    return merged


def build_context(
    docs
):

    return "\n\n".join(
        doc.page_content
        for doc in docs
    )


class RepositoryQA:

    def __init__(
        self,
        vectordb,
        documents
    ):

        self.llm = ChatGroq(
            model=
            "openai/gpt-oss-120b",

            temperature=0,

            api_key=os.getenv(
                "GROQ_API_KEY"
            )
        )

        profile_agent = (
            RepositoryAnalysisAgent(
                self.llm
            )
        )

        self.repo_profile_doc = (
            profile_agent
            .build_profile_document(
                documents
            )
        )

        self.repo_profile = (
            self.repo_profile_doc
            .page_content
        )

        self.documents = (
            list(documents)
            + [
                self.repo_profile_doc
            ]
        )

        self.retriever = (
            build_hybrid_retriever(
                vectordb,
                self.documents
            )
        )

        self.prompt = (
            ChatPromptTemplate
            .from_template(
                """
{system_prompt}

Context:

{context}

Question:

{question}

Answer:
"""
            )
        )

        self.chain = (
            self.prompt
            | self.llm
            | StrOutputParser()
        )

    def invoke(
        self,
        question
    ):

        retrieval_plan = (
            create_retrieval_plan(
                self.llm,
                question,
                self.repo_profile
            )
        )

        search_queries = (
            retrieval_plan[
                "queries"
            ]
        )

        retrieved_docs = (
            self.retriever.retrieve(
                search_queries,
                top_k=30,
                preferred_chunk_types=
                retrieval_plan.get(
                    "preferred_chunk_types"
                ),
                include_readme=
                retrieval_plan.get(
                    "include_readme"
                ),
                include_repo_profile=
                retrieval_plan.get(
                    "include_repo_profile"
                )
            )
        )

        deduplicated = []

        seen = set()

        for doc in retrieved_docs:

            key = (
                str(
                    doc.metadata.get(
                        "file_path",
                        ""
                    )
                )
                + "::"
                + doc.page_content
            )

            if key not in seen:

                seen.add(key)

                deduplicated.append(
                    doc
                )

        reranked_docs = (
            rerank_documents(
                "\n".join(
                    search_queries
                ),
                deduplicated,
                top_k=12
            )
        )

        context_docs = (
            merge_context_docs(
                deduplicated[:8],
                reranked_docs,
                max_docs=12
            )
        )

        validation = {
            "sufficient": True,
            "confidence": "high",
            "missing_aspects": [],
            "follow_up_queries": []
        }

        if retrieval_plan.get(
            "needs_validation",
            True
        ):

            validation = (
                validate_context(
                    self.llm,
                    question,
                    retrieval_plan,
                    context_docs
                )
            )

        if (
            not validation.get(
                "sufficient"
            )
            and validation.get(
                "follow_up_queries"
            )
        ):

            follow_up_docs = (
                self.retriever.retrieve(
                    validation[
                        "follow_up_queries"
                    ],
                    top_k=20,
                    preferred_chunk_types=
                    retrieval_plan.get(
                        "preferred_chunk_types"
                    ),
                    include_readme=
                    retrieval_plan.get(
                        "include_readme"
                    ),
                    include_repo_profile=True
                )
            )

            follow_up_ranked = (
                rerank_documents(
                    "\n".join(
                        validation[
                            "follow_up_queries"
                        ]
                    ),
                    follow_up_docs,
                    top_k=8
                )
            )

            context_docs = (
                merge_context_docs(
                    context_docs,
                    follow_up_ranked,
                    max_docs=14
                )
            )

        if DEBUG_MODE:

            print(
                "\nSearch Queries:"
            )

            for q in search_queries:

                print(
                    f"- {q}"
                )

            print(
                "\nRetrieval Plan:"
            )

            print(
                json.dumps(
                    retrieval_plan,
                    indent=2
                )
            )

            print(
                "\nContext Validation:"
            )

            print(
                json.dumps(
                    validation,
                    indent=2
                )
            )

            print(
                "\nContext Sources:"
            )

            for doc in context_docs:

                meta = (
                    doc.metadata
                )

                print(
                    "- "
                    + meta.get(
                        "file_name",
                        "Unknown"
                    )
                )

        context = (
            build_context(
                context_docs
            )
        )

        return (
            self.chain.invoke(
                {
                    "system_prompt":
                    SYSTEM_PROMPT,

                    "context":
                    context,

                    "question":
                    question
                }
            )
        )


def build_qa_chain(
    vectordb,
    documents
):

    return RepositoryQA(
        vectordb,
        documents
    )
