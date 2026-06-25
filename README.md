<!-- prettier-ignore -->
<div align="center">

# GitHub Repo RAG — Render Edition

Ask questions about any GitHub repository and get accurate, source-backed answers powered by AI. Optimized for free-tier cloud hosting on Render.

[Features](#features) · [Demo](#demo) · [Getting Started](#getting-started) · [Usage](#usage) · [Architecture](#architecture) · [Configuration](#configuration)

</div>

## Overview

**GitHub Repo RAG — Render Edition** is a lightweight, cloud-hosted version of the GitHub Repo RAG assistant. It clones, indexes, and lets you chat with any public GitHub repository using a streamlined retrieval pipeline that fits within the constraints of free-tier hosting platforms like Render.

Unlike the full local version, this edition skips heavy vector embedding models and database storage to stay under **512 MB of RAM**, while still delivering intelligent, context-aware answers with citations to specific files.

## Features

- **Free-Tier Optimised** — Runs comfortably within Render's free-tier limits by omitting ChromaDB and Sentence Transformers, relying on lightweight BM25 search instead.
- **One-Click Cloning** — Paste a GitHub URL and the repository is automatically cloned, pulled, and indexed in the background.
- **BM25 Sparse Retrieval** — Uses the `rank-bm25` library for fast, memory-efficient keyword-based document matching without requiring a GPU or large model downloads.
- **Intelligent Retrieval Planning** — An LLM-based planner analyses each question to determine the search strategy, query rewrites, and preferred document types.
- **Context Validation** — Validates whether retrieved context is sufficient. If not, it performs targeted follow-up searches automatically.
- **Repository Analysis** — Automatically builds a repository profile identifying key files, entry points, symbols, and architecture.
- **AST-Based Code Chunking** — Parses Python files into semantic chunks using the abstract syntax tree, preserving function and class boundaries.
- **Modern Web UI** — Clean, responsive interface for loading repos and chatting, built with vanilla JavaScript and FastAPI.
- **Multiple File Types** — Supports `.py`, `.js`, `.ts`, `.java`, `.md`, `.txt`, `.json`, `.ipynb`, `.yaml`, `.yml`, `.cpp`, and `.c` files.

> [!IMPORTANT]
> This is the **Render/cloud edition** of GitHub Repo RAG, designed for platforms with tight memory limits. For the full-featured local version with dense vector search (ChromaDB + Sentence Transformers), see the [main/local branch](https://github.com/sushma-2003/Githubrep_clone_with_Agent_localhost).

## Demo

1. Enter any public GitHub repository URL into the web interface.
2. The app clones the repo, indexes all documents, and builds a QA chain in the background.
3. Ask questions like:
   - "What does this project do?"
   - "Where is the main entry point?"
   - "How is the data model structured?"
   - "Show me the implementation of `build_qa_chain`"

## Getting Started

### Prerequisites

- Python 3.10+
- [Git](https://git-scm.com/downloads)
- A [Groq](https://groq.com/) API key (free tier available)

### Installation

1. **Clone this repository:**

   ```bash
   git clone https://github.com/sushma-2003/Githubrep_clone_with_Agent_render.git
   cd Githubrep_clone_with_Agent_render
   ```

2. **Create a virtual environment and install dependencies:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure your environment:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set your Groq API key:

   ```
   GROQ_API_KEY=your_groq_api_key_here
   ```

   > [!TIP]
   > You can get a free Groq API key at [console.groq.com](https://console.groq.com/keys).

### Running the Application

Start the FastAPI server:

```bash
python app.py
```

The application will be available at `http://127.0.0.1:8000`.

Open your browser, paste a GitHub repository URL, and start exploring!

### Deploying to Render

This edition is ready to deploy to [Render](https://render.com/) with minimal configuration:

1. Create a free Render account at [render.com](https://render.com/).
2. In the Render Dashboard, create a new **Web Service** and connect your GitHub repository.
3. Set the following:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Add your `GROQ_API_KEY` as an environment variable in the Render dashboard.
5. Deploy.

> [!NOTE]
> The app uses **lazy imports** for heavy ML libraries, so FastAPI starts quickly and doesn't trigger Render's port-detection timeout. The actual model loading and document indexing happen inside a background task only after a repository URL is submitted.

## Usage

### Web Interface

1. Navigate to the deployed URL (or `http://127.0.0.1:8000` locally).
2. Enter a public GitHub repository URL (e.g., `https://github.com/microsoft/DeepSpeed`).
3. Wait for the cloning, indexing, and QA chain to build (status is shown with a progress indicator).
4. Once ready, ask questions about the codebase in natural language.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | `GET` | Serves the web interface |
| `/api/load` | `POST` | Start loading a repository (clone + index) |
| `/api/status/{session_id}` | `GET` | Poll the current status of a loading job |
| `/api/ask` | `POST` | Ask a question about the loaded repository |
| `/api/health` | `GET` | Health check |

### Example API Request

```bash
curl -X POST http://127.0.0.1:8000/api/load \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/microsoft/DeepSpeed"}'
```

```bash
curl -X POST http://127.0.0.1:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<your-session-id>", "question": "What is the main purpose of this project?"}'
```

## Architecture

```
User Query
    |
    v
Retrieval Planner (LLM)  <-- Determines question type & search strategy
    |
    v
BM25 Sparse Retriever  <-- Lightweight keyword-based search (no vector DB)
    |
    v
Document Re-ranking  <-- Reranks documents for relevance
    |
    v
Context Validator  <-- Checks if context is sufficient; performs follow-up if needed
    |
    v
QA Chain (Groq LLM)  <-- Generates answer with source citations
```

### Differences from the Full (Local) Version

| | Render Edition | Local Edition |
|---|---|---|
| **Vector Store** | None (BM25 only) | ChromaDB + Sentence Transformers |
| **Memory Footprint** | < 512 MB | ~1–2 GB |
| **Search Type** | Sparse (BM25) only | Hybrid (dense + sparse) |
| **LLM Provider** | Groq API | Groq API |
| **Model Downloads** | None (API-only) | Sentence Transformers (local) |
| **Best For** | Free cloud hosting | Local development, large repos |

### Component Overview

| Component | Purpose |
|-----------|---------|
| `app.py` | FastAPI web application, lazy-imports heavy libraries, background tasks for repo loading |
| `clone_repo.py` | Clones or pulls GitHub repositories using GitPython or subprocess |
| `document_loader.py` | Loads and processes files from cloned repos |
| `chunking.py` | AST-based and semantic chunking for code files, notebooks, and READMEs |
| `ingest.py` | Loads documents and skips ChromaDB to stay lightweight |
| `retrievers.py` | BM25 sparse retriever with fallback when vectordb is absent |
| `reranker.py` | Re-ranks retrieved documents by relevance |
| `agent_planner.py` | LLM-based retrieval planning and query generation |
| `context_validator.py` | Validates context sufficiency, triggers follow-up |
| `repo_analyzer.py` | Analyses repository structure and builds a profile |
| `qa_chain.py` | Orchestrates the full QA pipeline |
| `query_rewriter.py` | Rewrites and expands search queries |
| `prompts.py` | System prompt templates for the LLM |

## Configuration

The application is configured via the `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Your Groq API key | *(required)* |
| `DEBUG_RETRIEVAL` | Set to `1` to print retrieval debug info | `0` |

## Supported File Types

The following file extensions are indexed by default:

`.py` `.js` `.ts` `.java` `.cpp` `.c` `.md` `.txt` `.json` `.ipynb` `.yaml` `.yml`

## Troubleshooting

**Render port-detection timeout**
> The app uses lazy imports: `FastAPI` and Pydantic models load immediately, but LangChain and other heavy libraries are only imported inside the background task. This keeps the initial startup snappy and avoids triggering Render's port-detection timeout.

**Repository not found / cloning fails**
> Verify the repository is public and the URL is correct. The app does not support private repositories without authentication.

**Slow indexing on large repositories**
> Even without vector embeddings, parsing very large repositories can take time. Memory usage should still remain below 512 MB for most mid-sized repos.
