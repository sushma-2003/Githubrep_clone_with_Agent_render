import os
from collections import Counter, defaultdict

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate


PROFILE_PROMPT = PromptTemplate(
    input_variables=["profile"],
    template="""
You are a repository analysis agent.

Convert the raw repository inventory into a concise architecture brief that
will help a RAG assistant answer questions about the codebase.

Focus on purpose, entry points, important files, notebooks, major symbols,
and likely workflows. Use only the supplied inventory.

Raw repository inventory:
{profile}

Return a concise plain-text brief with file/path citations where available.
"""
)


IMPORTANT_NAMES = {
    "readme.md",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "setup.py",
    "app.py",
    "main.py",
    "cli.py",
    "manage.py",
    "dockerfile",
}


def _relative_path(path, root_path):
    try:
        return os.path.relpath(path, root_path)
    except ValueError:
        return path


def _top_values(counter, limit=12):
    return [value for value, _ in counter.most_common(limit)]


class RepositoryAnalysisAgent:

    def __init__(self, llm=None, max_docs=80):
        self.llm = llm
        self.max_docs = max_docs

    def _build_inventory(self, documents):
        if not documents:
            return {
                "repo_root": "",
                "file_count": 0,
                "chunk_count": 0,
                "extensions": [],
                "chunk_types": [],
                "important_files": [],
                "symbols": [],
                "notebooks": [],
                "readme_sections": [],
                "busiest_files": [],
            }

        paths = [
            doc.metadata.get("file_path", "")
            for doc in documents
            if doc.metadata.get("file_path")
        ]

        repo_root = os.path.commonpath(paths) if paths else ""
        files = sorted(set(paths))
        extension_counter = Counter(
            os.path.splitext(path)[1].lower() or "[no extension]"
            for path in files
        )
        chunk_type_counter = Counter(
            doc.metadata.get("chunk_type") or "unknown"
            for doc in documents
        )

        important_files = []
        notebooks = []
        symbols = Counter()
        readme_sections = []
        file_chunk_counts = defaultdict(int)

        for doc in documents:
            file_path = doc.metadata.get("file_path", "")
            file_name = str(doc.metadata.get("file_name") or "").lower()
            rel_path = _relative_path(file_path, repo_root) if file_path else ""
            file_chunk_counts[rel_path] += 1

            if file_name in IMPORTANT_NAMES and rel_path not in important_files:
                important_files.append(rel_path)

            if file_name.endswith(".ipynb") and rel_path not in notebooks:
                notebooks.append(rel_path)

            symbol = doc.metadata.get("symbol")

            if symbol:
                symbols[f"{symbol} ({rel_path})"] += 1

            if doc.metadata.get("chunk_type") == "readme":
                first_line = doc.page_content.splitlines()[0:1]

                if first_line:
                    readme_sections.append(f"{first_line[0]} ({rel_path})")

        busiest_files = sorted(
            file_chunk_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:12]

        return {
            "repo_root": repo_root,
            "file_count": len(files),
            "chunk_count": len(documents),
            "extensions": _top_values(extension_counter),
            "chunk_types": _top_values(chunk_type_counter),
            "important_files": important_files[:20],
            "symbols": _top_values(symbols, limit=30),
            "notebooks": notebooks[:20],
            "readme_sections": readme_sections[:20],
            "busiest_files": [
                f"{path} ({count} chunks)"
                for path, count in busiest_files
            ],
        }

    def _format_inventory(self, inventory):
        lines = [
            "Repository Profile",
            f"Root: {inventory['repo_root']}",
            f"Files indexed: {inventory['file_count']}",
            f"Chunks indexed: {inventory['chunk_count']}",
            "Extensions: " + ", ".join(inventory["extensions"]),
            "Chunk types: " + ", ".join(inventory["chunk_types"]),
        ]

        sections = [
            ("Important files", inventory["important_files"]),
            ("Notebook files", inventory["notebooks"]),
            ("README sections", inventory["readme_sections"]),
            ("Major symbols", inventory["symbols"]),
            ("High-chunk files", inventory["busiest_files"]),
        ]

        for title, values in sections:
            if not values:
                continue

            lines.append("")
            lines.append(f"{title}:")

            for value in values:
                lines.append(f"- {value}")

        return "\n".join(lines)

    def analyze(self, documents):
        inventory = self._build_inventory(documents)
        raw_profile = self._format_inventory(inventory)

        if self.llm is None:
            return raw_profile

        try:
            sampled_docs = "\n\n".join(
                doc.page_content
                for doc in documents[: self.max_docs]
                if doc.metadata.get("chunk_type") in {"readme", "code", "notebook_cell"}
            )
            profile_input = raw_profile + "\n\nSampled repository context:\n" + sampled_docs[:12000]
            chain = PROFILE_PROMPT | self.llm | StrOutputParser()
            summary = chain.invoke({"profile": profile_input})
        except Exception:
            return raw_profile

        return raw_profile + "\n\nRepository Analysis Agent Brief:\n" + str(summary).strip()

    def build_profile_document(self, documents):
        profile = self.analyze(documents)

        return Document(
            page_content=profile,
            metadata={
                "file_name": "REPOSITORY_PROFILE",
                "file_path": "REPOSITORY_PROFILE",
                "chunk_type": "repo_profile",
                "symbol": "repository_analysis",
            },
        )
