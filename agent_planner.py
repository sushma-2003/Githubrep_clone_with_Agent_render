import json
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from query_rewriter import rewrite_search_queries


PLANNER_PROMPT = PromptTemplate(
    input_variables=["question", "repo_profile"],
    template="""
You are a retrieval planning agent for a GitHub repository assistant.

Create a focused retrieval plan for answering the user's question using
repository files only.

Repository profile:
{repo_profile}

Question:
{question}

Return strict JSON with these keys:
- question_type: one of overview, implementation, debugging, file_location,
  dependency, data_model, usage, unknown
- queries: 4 to 8 concise search queries
- preferred_chunk_types: relevant chunk types from readme, code, text,
  notebook_cell, repo_profile
- include_readme: boolean
- include_repo_profile: boolean
- needs_validation: boolean
- answer_focus: one short sentence describing what evidence is needed

Do not include markdown fences.
"""
)


OVERVIEW_TERMS = {
    "overview",
    "purpose",
    "about",
    "explain",
    "flow",
    "pipeline",
    "architecture",
    "project",
    "system",
}

IMPLEMENTATION_TERMS = {
    "implement",
    "function",
    "class",
    "method",
    "code",
    "where",
    "how",
    "bug",
    "error",
}


def _extract_json(text):
    text = str(text or "").strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if match:
        return match.group(0)

    return ""


def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}

    return default


def _normalize_list(values, fallback):
    if isinstance(values, str):
        values = [values]

    if not isinstance(values, list):
        values = fallback

    cleaned = []
    seen = set()

    for value in values:
        value = str(value).strip()

        if not value:
            continue

        key = value.lower()

        if key in seen:
            continue

        seen.add(key)
        cleaned.append(value)

    return cleaned or fallback


def fallback_plan(question, llm=None):
    lowered = question.lower()
    is_overview = any(term in lowered for term in OVERVIEW_TERMS)
    is_implementation = any(term in lowered for term in IMPLEMENTATION_TERMS)

    question_type = "overview" if is_overview else "implementation"

    if "install" in lowered or "dependency" in lowered:
        question_type = "dependency"
    elif "where" in lowered or "file" in lowered:
        question_type = "file_location"
    elif "bug" in lowered or "error" in lowered or "fix" in lowered:
        question_type = "debugging"
    elif not is_overview and not is_implementation:
        question_type = "unknown"

    try:
        queries = rewrite_search_queries(llm, question) if llm else [question]
    except Exception:
        queries = [question]

    preferred = ["repo_profile", "readme"] if is_overview else ["code", "notebook_cell"]

    return {
        "question_type": question_type,
        "queries": _normalize_list(queries, [question]),
        "preferred_chunk_types": preferred,
        "include_readme": is_overview,
        "include_repo_profile": True,
        "needs_validation": True,
        "answer_focus": "Find repository evidence that directly answers the question.",
    }


def create_retrieval_plan(llm, question, repo_profile=""):
    try:
        chain = PLANNER_PROMPT | llm | StrOutputParser()
        response = chain.invoke(
            {
                "question": question,
                "repo_profile": repo_profile[:6000],
            }
        )

        plan = json.loads(_extract_json(response))
    except Exception:
        return fallback_plan(question, llm)

    fallback = fallback_plan(question, llm=None)

    queries = _normalize_list(
        plan.get("queries"),
        fallback["queries"],
    )

    if question not in queries:
        queries.append(question)

    preferred_chunk_types = _normalize_list(
        plan.get("preferred_chunk_types"),
        fallback["preferred_chunk_types"],
    )

    return {
        "question_type": str(
            plan.get("question_type") or fallback["question_type"]
        ).strip(),
        "queries": queries[:8],
        "preferred_chunk_types": preferred_chunk_types,
        "include_readme": _as_bool(
            plan.get("include_readme"),
            fallback["include_readme"],
        ),
        "include_repo_profile": _as_bool(
            plan.get("include_repo_profile"),
            True,
        ),
        "needs_validation": _as_bool(
            plan.get("needs_validation"),
            True,
        ),
        "answer_focus": str(
            plan.get("answer_focus") or fallback["answer_focus"]
        ).strip(),
    }
