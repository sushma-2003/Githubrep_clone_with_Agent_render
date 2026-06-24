import json
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate


VALIDATOR_PROMPT = PromptTemplate(
    input_variables=["question", "plan", "context"],
    template="""
You are a context validation agent for a repository RAG system.

Decide whether the supplied repository context is sufficient to answer the
question accurately. Use only the context. If it is weak, propose targeted
follow-up search queries.

Question:
{question}

Retrieval plan:
{plan}

Context:
{context}

Return strict JSON with these keys:
- sufficient: boolean
- confidence: one of high, medium, low
- missing_aspects: list of short strings
- follow_up_queries: list of 0 to 5 concise repository search queries
- rationale: one short sentence

Do not include markdown fences.
"""
)


def _extract_json(text):
    text = str(text or "").strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if match:
        return match.group(0)

    return ""


def _normalize_list(values):
    if isinstance(values, str):
        values = [values]

    if not isinstance(values, list):
        return []

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

    return cleaned


def _fallback_validation(question, docs):
    question_terms = {
        term
        for term in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", question.lower())
        if term not in {"what", "where", "when", "which", "does", "this"}
    }

    context = " ".join(doc.page_content.lower() for doc in docs)
    matched_terms = {term for term in question_terms if term in context}
    coverage = len(matched_terms) / max(len(question_terms), 1)
    sufficient = bool(docs) and coverage >= 0.25

    return {
        "sufficient": sufficient,
        "confidence": "medium" if sufficient else "low",
        "missing_aspects": [] if sufficient else ["direct repository evidence"],
        "follow_up_queries": [] if sufficient else [question],
        "rationale": "Fallback lexical validation was used.",
    }


def validate_context(llm, question, plan, docs):
    if not docs:
        return {
            "sufficient": False,
            "confidence": "low",
            "missing_aspects": ["retrieved context"],
            "follow_up_queries": [question],
            "rationale": "No context documents were retrieved.",
        }

    context = "\n\n".join(doc.page_content for doc in docs)[:14000]

    try:
        chain = VALIDATOR_PROMPT | llm | StrOutputParser()
        response = chain.invoke(
            {
                "question": question,
                "plan": json.dumps(plan, ensure_ascii=True),
                "context": context,
            }
        )

        validation = json.loads(_extract_json(response))
    except Exception:
        return _fallback_validation(question, docs)

    sufficient = validation.get("sufficient")

    if isinstance(sufficient, str):
        sufficient = sufficient.strip().lower() in {"1", "true", "yes"}
    else:
        sufficient = bool(sufficient)

    confidence = str(validation.get("confidence") or "low").strip().lower()

    if confidence not in {"high", "medium", "low"}:
        confidence = "low"

    return {
        "sufficient": sufficient,
        "confidence": confidence,
        "missing_aspects": _normalize_list(validation.get("missing_aspects")),
        "follow_up_queries": _normalize_list(validation.get("follow_up_queries"))[:5],
        "rationale": str(validation.get("rationale") or "").strip(),
    }
