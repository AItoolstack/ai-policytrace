"""
api.py — FastAPI server for the UK Motor Insurance Visual Audit Review UI.

Endpoints
─────────
  GET  /api/health
  POST /api/process                   — upload PDFs, run pipeline, return session_id
  GET  /api/session/{id}              — full GoldenRecordWithProvenance JSON
  GET  /api/pdf/{session_id}/{file}   — serve source PDF (path-traversal safe)
  PATCH /api/session/{id}/review      — log a verify / override action
  GET  /api/session/{id}/review-state — current review state for the session

Run (from project root)
───────────────────────
  uvicorn api:app --app-dir src --reload --port 8000

Or directly:
  python src/api.py
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Ensure src/ is on sys.path so sibling modules resolve regardless of CWD ─
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents import InsuranceExtractionAgents
from pipeline import run_extraction_pipeline
from privacy import PIIMasker
from provenance import build_provenance
from schema import GoldenRecordWithProvenance, UKMotorGoldenRecord
from settings import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

# ---------------------------------------------------------------------------
# Session storage directory  (project_root/output/sessions/<timestamp>_<uuid>/)
# Debug artifacts directory  (project_root/output/debug/run_<timestamp>/)
# ---------------------------------------------------------------------------

_SESSION_DIR = Path(__file__).parent.parent / "output" / "sessions"
_SESSION_DIR.mkdir(parents=True, exist_ok=True)

_DEBUG_DIR = Path(__file__).parent.parent / "output" / "debug"
_DEBUG_DIR.mkdir(parents=True, exist_ok=True)

_STATIC_DIR = Path(__file__).parent.parent / "ui" / "dist"

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="UK Motor Insurance IDP — Visual Audit API",
    version="1.0.0",
    description=(
        "Backend for the Human-in-the-Loop review dashboard. "
        "Runs the extraction pipeline and exposes session-based review endpoints."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _cleanup_old_sessions() -> None:
    """Remove session directories older than settings.pipeline.session_ttl_days on startup."""
    import shutil
    ttl_days = settings.pipeline.session_ttl_days
    if ttl_days <= 0:
        return
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=ttl_days)
    removed = 0
    for session_dir in _SESSION_DIR.iterdir():
        if session_dir.is_dir():
            mtime = datetime.fromtimestamp(session_dir.stat().st_mtime)
            if mtime < cutoff:
                shutil.rmtree(session_dir, ignore_errors=True)
                removed += 1
    if removed:
        logger.info(
            "Startup cleanup: removed %d session(s) older than %d day(s)",
            removed, ttl_days,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session_dir(session_id: str) -> Path:
    """Return session directory or raise 404.

    Supports both old-style (uuid-only) and new-style (timestamp_uuid) folder names.
    """
    # New-style: glob for any folder ending with the session UUID
    matches = list(_SESSION_DIR.glob(f"*{session_id}"))
    if matches:
        return matches[0]
    raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")


def _count_leaves(obj: object) -> int:
    if isinstance(obj, dict):
        return sum(_count_leaves(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_count_leaves(v) for v in obj)
    return 1


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ── POST /api/process ────────────────────────────────────────────────────────

class ProcessResponse(BaseModel):
    session_id: str
    fields_extracted: int
    provenance_coverage: int   # number of fields successfully located


@app.post("/api/process", response_model=ProcessResponse)
async def process_documents(files: list[UploadFile] = File(...)):
    """
    Accept one or more PDF uploads, run the full extraction pipeline, and
    persist a session containing the Golden Record + provenance index.

    Returns a ``session_id`` which the UI uses for all subsequent requests.

    Note: This endpoint is synchronous and may take 30–90 seconds depending
    on Groq API response times.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    pdf_files = [f for f in files if f.filename and f.filename.lower().endswith(".pdf")]
    if not pdf_files:
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # ── Create session directory (timestamp_uuid for easy sorting) ─────────
    run_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_id = str(uuid.uuid4())
    session_folder = f"{run_ts}_{session_id}"
    session_dir = _SESSION_DIR / session_folder
    docs_dir = session_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # ── Create timestamped debug directory ────────────────────────────────
    debug_dir: Path | None = None
    if settings.debug.enabled:
        debug_dir = _DEBUG_DIR / f"run_{run_ts}"
        debug_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Debug artifacts → %s", debug_dir)

    # ── Save uploaded PDFs (sanitise filenames) ───────────────────────────
    pdf_paths: list[Path] = []
    for upload in pdf_files:
        safe_name = Path(upload.filename).name  # strips directory components
        dest = docs_dir / safe_name
        dest.write_bytes(await upload.read())
        pdf_paths.append(dest)

    # ── Run pipeline with provenance ──────────────────────────────────────
    masker = PIIMasker(mask_dates=settings.pii.mask_dates)
    agent = InsuranceExtractionAgents(masker=masker, debug_dir=debug_dir)

    golden, conflicts, corpora = run_extraction_pipeline(
        pdf_paths=pdf_paths,
        agent=agent,
        with_provenance=True,
    )

    # ── Build provenance index ────────────────────────────────────────────
    provenance_list = build_provenance(golden, corpora)

    result = GoldenRecordWithProvenance(
        record=golden,
        provenance=provenance_list,
        conflicts=conflicts,
        session_id=session_id,
    )

    # ── Persist session ────────────────────────────────────────────────
    (session_dir / "result.json").write_text(
        result.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    (session_dir / "review_state.json").write_text("{}", encoding="utf-8")

    # Save field_citations sidecar so provenance can be re-built without re-running the LLM.
    # (field_citations is excluded from result.json via Field(exclude=True) on the schema.)
    fc = dict(getattr(golden, "field_citations", None) or {})
    if fc:
        (session_dir / "field_citations.json").write_text(
            json.dumps(fc, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    flat_fields = _count_leaves(golden.model_dump(exclude_none=True))
    return ProcessResponse(
        session_id=session_id,
        fields_extracted=flat_fields,
        provenance_coverage=len(provenance_list),
    )


# ── GET /api/session/{session_id} ────────────────────────────────────────────

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Return the full GoldenRecordWithProvenance for this session."""
    session_dir = _get_session_dir(session_id)
    result_file = session_dir / "result.json"
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="Session result not yet available.")
    return JSONResponse(content=json.loads(result_file.read_text(encoding="utf-8")))


# ── GET /api/pdf/{session_id}/{filename} ─────────────────────────────────────

@app.get("/api/pdf/{session_id}/{filename}")
async def serve_pdf(session_id: str, filename: str):
    """
    Serve a PDF from the session's docs directory.

    Path traversal is prevented by using only ``Path(filename).name``,
    which strips any directory components from the supplied filename.
    """
    session_dir = _get_session_dir(session_id)
    safe_name = Path(filename).name
    if not safe_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files can be served.")
    pdf_path = session_dir / "docs" / safe_name
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF '{safe_name}' not found in session.")
    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


# ── PATCH /api/session/{session_id}/review ───────────────────────────────────

class ReviewUpdate(BaseModel):
    field_path: str
    action: str                         # "verify" | "reject" | "override"
    overridden_value: Optional[str] = None
    reviewer: Optional[str] = "anonymous"


@app.patch("/api/session/{session_id}/review")
async def update_review(session_id: str, update: ReviewUpdate):
    """Record a verify, reject, or override action for a specific field."""
    if update.action not in {"verify", "reject", "override"}:
        raise HTTPException(
            status_code=422,
            detail="action must be one of: verify, reject, override",
        )

    session_dir = _get_session_dir(session_id)
    state_file = session_dir / "review_state.json"
    state: dict = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}

    state[update.field_path] = {
        "action": update.action,
        "overridden_value": update.overridden_value,
        "reviewer": update.reviewer,
    }
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return {"ok": True, "field_path": update.field_path, "action": update.action}


# ── GET /api/session/{session_id}/review-state ───────────────────────────────

@app.get("/api/session/{session_id}/review-state")
async def get_review_state(session_id: str):
    """Return the current review state (verify/override log) for the session."""
    session_dir = _get_session_dir(session_id)
    state_file = session_dir / "review_state.json"
    if not state_file.exists():
        return JSONResponse(content={})
    return JSONResponse(content=json.loads(state_file.read_text(encoding="utf-8")))

# ── DELETE /api/session/{session_id} ──────────────────────────────────────────

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """
    Permanently delete a session directory and all its contents.

    This removes the uploaded PDFs, the Golden Record JSON, the review state,
    and all debug artifacts for this session.
    """
    import shutil
    session_dir = _get_session_dir(session_id)
    shutil.rmtree(session_dir, ignore_errors=True)
    return {"ok": True, "session_id": session_id}


# ---------------------------------------------------------------------------
# Production UI hosting
# ---------------------------------------------------------------------------

if _STATIC_DIR.exists():
    assets_dir = _STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """
        Serve the built React app when running as a single production service.

        Vite handles the frontend during local development. In Docker/Hugging
        Face deployments, the Dockerfile builds ui/dist and FastAPI serves it.
        Unknown non-API paths fall back to index.html so /session/{id} works
        after a hard refresh.
        """
        requested = (_STATIC_DIR / full_path).resolve()
        static_root = _STATIC_DIR.resolve()
        if (
            full_path
            and requested.is_file()
            and static_root in requested.parents
        ):
            return FileResponse(str(requested))
        return FileResponse(str(_STATIC_DIR / "index.html"))

# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
