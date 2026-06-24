from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
from typing import Optional

from dotenv import load_dotenv

from clone_repo import clone_repository

load_dotenv()

app = FastAPI(title="GitHub Repo RAG", version="1.0.0")

# CORS: allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global state for tracking repo loading and QA chains
_sessions = {}
_status = {}


class LoadRepoRequest(BaseModel):
    repo_url: str


class AskRequest(BaseModel):
    question: str
    session_id: str


class StatusResponse(BaseModel):
    status: str
    message: str
    session_id: str
    repo_name: Optional[str] = None
    progress: Optional[int] = None


@app.get("/")
async def read_root(request: Request):
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/load")
async def load_repo(data: LoadRepoRequest, background_tasks: BackgroundTasks):
    """
    Start loading a repository (clone + index) in the background.
    Returns a session ID that the client can poll for status.
    """
    session_id = str(uuid.uuid4())
    _status[session_id] = {
        "status": "starting",
        "message": "Initializing...",
        "repo_name": None,
        "progress": 0
    }
    background_tasks.add_task(_load_repo_task, data.repo_url, session_id)
    return {"session_id": session_id, "status": "started"}


import traceback as _tb

async def _load_repo_task(repo_url: str, session_id: str):
    """Background task to clone and index a repository."""
    # Lazy imports: defer heavy ML libraries until first use.
    # This keeps the FastAPI app startup fast enough for Render's port detection.
    import sys
    print(f"[BG TASK {session_id}] Starting background task", flush=True)
    from ingest import create_vector_store
    from qa_chain import build_qa_chain

    try:
        _status[session_id]["status"] = "cloning"
        _status[session_id]["message"] = "Cloning repository..."
        _status[session_id]["progress"] = 10

        repo_path = clone_repository(repo_url)
        repo_name = os.path.basename(repo_path)

        _status[session_id]["repo_name"] = repo_name
        _status[session_id]["status"] = "indexing"
        _status[session_id]["message"] = "Indexing repository..."
        _status[session_id]["progress"] = 40

        print(f"[BG TASK {session_id}] About to call create_vector_store...", flush=True)
        vectordb, documents = create_vector_store(repo_path)
        print(f"[BG TASK {session_id}] create_vector_store done, documents={len(documents)}", flush=True)

        _status[session_id]["status"] = "building"
        _status[session_id]["message"] = "Preparing QA chain..."
        _status[session_id]["progress"] = 80

        print(f"[BG TASK {session_id}] About to call build_qa_chain...", flush=True)
        qa_chain = build_qa_chain(vectordb, documents)
        print(f"[BG TASK {session_id}] build_qa_chain done", flush=True)

        _sessions[session_id] = {
            "qa_chain": qa_chain,
            "repo_name": repo_name,
            "repo_path": repo_path
        }

        _status[session_id]["status"] = "ready"
        _status[session_id]["message"] = "Repository loaded and ready!"
        _status[session_id]["progress"] = 100

    except Exception as e:
        _status[session_id]["status"] = "error"
        _status[session_id]["message"] = f"Error: {str(e)}"
        _status[session_id]["progress"] = 0


@app.get("/api/status/{session_id}")
async def get_status(session_id: str):
    """Poll the current status of a repo loading job."""
    if session_id not in _status:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": "Session not found"}
        )
    return _status[session_id]


@app.post("/api/ask")
async def ask_question(data: AskRequest):
    """
    Ask a question about the loaded repository.
    Returns the answer directly or as a stream (if stream param is set).
    """
    session_id = data.session_id

    if session_id not in _sessions:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "No repository loaded for this session. Load a repository first."}
        )

    qa_chain = _sessions[session_id]["qa_chain"]

    try:
        answer = qa_chain.invoke(data.question)
        return {"status": "success", "answer": answer}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
