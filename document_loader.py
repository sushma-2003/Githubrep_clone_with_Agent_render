import os

from langchain_core.documents import (
    Document
)

from chunking import (
    chunk_document
)


VALID_EXTENSIONS = (
    ".py",
    ".js",
    ".ts",
    ".java",
    ".cpp",
    ".c",
    ".md",
    ".txt",
    ".json",
    ".ipynb",
    ".yaml",
    ".yml"
)


def build_searchable_content(
    file_name,
    file_path,
    chunk
):

    parts = [

        f"Source file: {file_name}",

        f"Source path: {file_path}",

        f"Chunk type: "
        f"{chunk.get('chunk_type','')}"
    ]

    if chunk.get("symbol"):

        parts.append(
            f"Symbol: "
            f"{chunk.get('symbol')}"
        )

    if chunk.get("cell_order"):

        parts.append(
            f"Notebook cell order: "
            f"{chunk.get('cell_order')}"
        )

    if chunk.get("cell_type"):

        parts.append(
            f"Notebook cell type: "
            f"{chunk.get('cell_type')}"
        )

    if chunk.get("output_summary"):

        parts.append(
            f"Output summary: "
            f"{chunk.get('output_summary')}"
        )

    parts.extend(
        [
            "Content:",
            chunk["content"]
        ]
    )

    return "\n".join(
        parts
    )


def load_repository_documents(
    repo_path
):

    documents = []

    for root, _, files in os.walk(
        repo_path
    ):

        for file in files:

            if not file.lower().endswith(
                VALID_EXTENSIONS
            ):
                continue

            file_path = os.path.join(
                root,
                file
            )

            try:

                with open(
                    file_path,
                    "r",
                    encoding="utf-8"
                ) as f:

                    content = f.read()

                chunks = chunk_document(
                    file_path,
                    content
                )

                for chunk in chunks:

                    searchable_content = (
                        build_searchable_content(
                            file,
                            file_path,
                            chunk
                        )
                    )

                    documents.append(
                        Document(
                            page_content=
                            searchable_content,

                            metadata={
                                "file_name":
                                file,

                                "file_path":
                                file_path,

                                "chunk_type":
                                chunk.get(
                                    "chunk_type"
                                ),

                                "symbol":
                                chunk.get(
                                    "symbol"
                                ),

                                "cell_order":
                                chunk.get(
                                    "cell_order"
                                ),

                                "cell_type":
                                chunk.get(
                                    "cell_type"
                                ),

                                "output_summary":
                                chunk.get(
                                    "output_summary"
                                )
                            }
                        )
                    )

            except Exception as e:

                print(
                    f"Skipped "
                    f"{file_path}: {e}"
                )

    return documents