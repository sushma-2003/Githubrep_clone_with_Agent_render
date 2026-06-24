import ast
import json
import os

from nltk.tokenize import sent_tokenize


def chunk_python_file(code):

    chunks = []

    try:

        tree = ast.parse(code)

        lines = code.splitlines()

        for node in tree.body:

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef
                )
            ):

                start = node.lineno

                end = getattr(
                    node,
                    "end_lineno",
                    start
                )

                chunk = "\n".join(
                    lines[start - 1:end]
                )

                chunks.append(
                    {
                        "content": chunk,
                        "chunk_type": "code",
                        "symbol": node.name
                    }
                )

    except Exception:
        pass

    if not chunks:

        chunks.append(
            {
                "content": code,
                "chunk_type": "file",
                "symbol": None
            }
        )

    return chunks


def chunk_readme(text):

    sections = []

    current = []

    for line in text.split("\n"):

        if line.startswith("#"):

            if current:

                sections.append(
                    "\n".join(current)
                )

            current = [line]

        else:

            current.append(line)

    if current:

        sections.append(
            "\n".join(current)
        )

    return [
        {
            "content": section,
            "chunk_type": "readme",
            "symbol": None
        }
        for section in sections
    ]


def chunk_text_file(
    text,
    chunk_size=800
):

    try:

        sentences = sent_tokenize(text)

    except Exception:

        sentences = [text]

    chunks = []

    current = ""

    for sentence in sentences:

        if (
            len(current)
            + len(sentence)
            < chunk_size
        ):

            current += " " + sentence

        else:

            chunks.append(
                {
                    "content": current.strip(),
                    "chunk_type": "text",
                    "symbol": None
                }
            )

            current = sentence

    if current:

        chunks.append(
            {
                "content": current.strip(),
                "chunk_type": "text",
                "symbol": None
            }
        )

    return chunks


def normalize_notebook_source(source):

    if isinstance(source, list):

        return "".join(source)

    return str(source or "")


def summarize_output_value(
    value,
    max_chars=500
):

    if isinstance(value, list):

        text = "".join(
            str(item)
            for item in value
        )

    else:

        text = str(value or "")

    text = " ".join(
        text.split()
    )

    if len(text) > max_chars:

        return (
            text[:max_chars]
            + "..."
        )

    return text


def summarize_notebook_outputs(outputs):

    summaries = []

    for output in outputs or []:

        output_type = output.get(
            "output_type",
            ""
        )

        if output_type == "stream":

            text = summarize_output_value(
                output.get("text")
            )

            if text:

                summaries.append(
                    f"Stream output: {text}"
                )

        elif output_type in (
            "execute_result",
            "display_data"
        ):

            data = output.get(
                "data",
                {}
            )

            if "text/plain" in data:

                text = summarize_output_value(
                    data["text/plain"]
                )

                if text:

                    summaries.append(
                        f"{output_type}: {text}"
                    )

            else:

                media_types = ", ".join(
                    sorted(data.keys())
                )

                if media_types:

                    summaries.append(
                        f"{output_type}: media output ({media_types})"
                    )

        elif output_type == "error":

            error_name = output.get(
                "ename",
                "Error"
            )

            error_value = output.get(
                "evalue",
                ""
            )

            summaries.append(
                f"Error output: {error_name}: {error_value}"
            )

    if not summaries:

        return "No output."

    return "\n".join(summaries)


def chunk_notebook(content):

    try:

        notebook = json.loads(
            content
        )

    except json.JSONDecodeError:

        return [
            {
                "content": content,
                "chunk_type": "notebook",
                "symbol": None,
                "cell_order": None,
                "cell_type": "unknown",
                "output_summary":
                "Could not parse notebook JSON."
            }
        ]

    chunks = []

    for index, cell in enumerate(
        notebook.get("cells", []),
        start=1
    ):

        cell_type = cell.get(
            "cell_type",
            "unknown"
        )

        if cell_type not in (
            "code",
            "markdown"
        ):

            continue

        source = normalize_notebook_source(
            cell.get("source")
        ).strip()

        output_summary = "No output."

        if cell_type == "code":

            output_summary = (
                summarize_notebook_outputs(
                    cell.get(
                        "outputs",
                        []
                    )
                )
            )

        parts = [
            f"Notebook cell {index}",
            f"Cell type: {cell_type}",
            "Source:",
            source or "[Empty cell]"
        ]

        if cell_type == "code":

            parts.extend(
                [
                    "Output summary:",
                    output_summary
                ]
            )

        chunks.append(
            {
                "content": "\n".join(parts),
                "chunk_type": "notebook_cell",
                "symbol": f"cell_{index}",
                "cell_order": index,
                "cell_type": cell_type,
                "output_summary": output_summary
            }
        )

    return chunks


def chunk_document(
    file_path,
    content
):

    ext = os.path.splitext(
        file_path
    )[1]

    filename = os.path.basename(
        file_path
    ).lower()

    if filename == "readme.md":

        return chunk_readme(
            content
        )

    if ext == ".py":

        return chunk_python_file(
            content
        )

    if ext == ".ipynb":

        return chunk_notebook(
            content
        )

    return chunk_text_file(
        content
    )