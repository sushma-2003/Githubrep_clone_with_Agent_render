from langchain_core.prompts import (
    PromptTemplate
)

from langchain_core.output_parsers import (
    StrOutputParser
)


REWRITE_PROMPT = PromptTemplate(
    input_variables=["question"],
    template="""
You are a search query generator.

Generate 5 different search queries
for retrieving relevant code and
documentation from a GitHub repository.

Question:
{question}

Return one query per line.
"""
)
def normalize_queries(
    queries
):

    seen = set()

    normalized = []

    for query in queries:

        query = str(query).strip()

        if not query:

            continue

        key = query.lower()

        if key not in seen:

            seen.add(key)

            normalized.append(
                query
            )

    return normalized

def rewrite_search_queries(
    llm,
    question
):

    chain = (
        REWRITE_PROMPT
        | llm
        | StrOutputParser()
    )

    response = chain.invoke(
        {
            "question": question
        }
    )

    queries = []

    for line in response.split("\n"):

        line = line.strip()

        if line:

            queries.append(line)

    queries.append(question)

    queries = list(
        dict.fromkeys(queries)
    )

    return normalize_queries(
    queries
)