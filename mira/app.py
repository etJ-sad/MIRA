"""Web API and UI."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import __version__
from .config import Settings, get_settings
from .ovms import OvmsClient
from .parsers import SUPPORTED
from .rag import Mira, ModelClient, answer_to_dict, append_log, document_id
from .store import VectorStore

STATIC = Path(__file__).parent / "static"


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


class Feedback(BaseModel):
    answer_id: str
    helpful: bool
    comment: str = Field(default="", max_length=2000)


def _safe_name(name: str) -> str:
    name = Path(name).name
    return re.sub(r"[^\w.\- ]", "_", name) or "dokument"


def create_app(settings: Settings | None = None, models: ModelClient | None = None, store: VectorStore | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    ovms = OvmsClient(settings) if models is None else None
    store = store or VectorStore.open(str(settings.index_dir), settings.collection)
    mira = Mira(settings, models or ovms, store)

    app = FastAPI(title="MIRA", version=__version__)

    @app.exception_handler(httpx.HTTPError)
    def model_server_down(request: Request, error: httpx.HTTPError) -> JSONResponse:
        detail = f"NPU-Modellserver (OVMS) nicht erreichbar unter {settings.ovms_url}: {error}"
        return JSONResponse(status_code=503, content={"detail": detail})

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/api/health")
    def health() -> dict:
        status = {"mira": __version__, "llm_model": settings.llm_model, "embed_model": settings.embed_model}
        if ovms is not None:
            try:
                status["ovms"] = ovms.health()
            except Exception as error:  # report, don't fail: the UI shows it
                status["ovms_error"] = str(error)
        return status

    @app.get("/api/documents")
    def documents() -> list[dict]:
        return store.documents()

    @app.post("/api/documents")
    def upload(file: UploadFile) -> dict:
        name = _safe_name(file.filename or "")
        if Path(name).suffix.lower() not in SUPPORTED:
            raise HTTPException(400, f"Dateityp nicht unterstützt. Erlaubt: {', '.join(sorted(SUPPORTED))}")
        target = settings.docs_dir / name
        target.write_bytes(file.file.read())
        try:
            chunks = mira.ingest_file(target)
        except httpx.HTTPError:
            raise
        except Exception as error:
            raise HTTPException(422, f"Datei konnte nicht gelesen werden: {error}") from error
        return {"doc_id": document_id(target), "name": name, "chunks": chunks}

    @app.delete("/api/documents/{doc_id}")
    def delete(doc_id: str) -> dict:
        for path in settings.docs_dir.iterdir():
            if document_id(path) == doc_id:
                path.unlink()
        store.delete_document(doc_id)
        return {"deleted": doc_id}

    @app.post("/api/ask")
    def ask(body: Question) -> dict:
        answer = mira.ask(body.question)
        result = {"answer_id": uuid.uuid4().hex, **answer_to_dict(answer)}
        append_log(settings.log_dir, "questions", {"question": body.question, **result})
        return result

    @app.post("/api/feedback")
    def feedback(body: Feedback) -> dict:
        append_log(settings.log_dir, "feedback", body.model_dump())
        return {"ok": True}

    return app


def app() -> FastAPI:
    """Factory for `uvicorn --factory mira.app:app`."""
    return create_app()
