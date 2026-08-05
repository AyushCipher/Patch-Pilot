"""FastAPI backend exposing PatchPilot agent runs and eval results.

Runs execute the (blocking) agent loop on a background thread. Each run's
trace events are also pushed onto an in-memory asyncio.Queue so the
WebSocket endpoint can stream them live to the dashboard as they happen.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.core import run_agent  # noqa: E402

load_dotenv()

BUG_BANK_DIR = Path(__file__).resolve().parent.parent / "eval" / "bug_bank"
RESULTS_PATH = Path(__file__).resolve().parent.parent / "eval" / "results" / "harness_report.json"
RUNS_DIR = Path(os.environ.get("RUNS_DIR", "runs"))
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "6"))

app = FastAPI(title="PatchPilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_executor = ThreadPoolExecutor(max_workers=4)


class RunState:
    def __init__(self, run_id: str, bug_id: Optional[str]) -> None:
        self.run_id = run_id
        self.bug_id = bug_id
        self.status = "pending"  # pending -> running -> completed | failed
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.queues: list[asyncio.Queue] = []
        self.events: list[dict] = []


RUNS: dict[str, RunState] = {}


class RunSummary(BaseModel):
    run_id: str
    bug_id: Optional[str]
    status: str


def _broadcast(run_id: str, loop: asyncio.AbstractEventLoop, event: dict) -> None:
    state = RUNS.get(run_id)
    if state is None:
        return
    state.events.append(event)

    def _push() -> None:
        for q in state.queues:
            q.put_nowait(event)

    loop.call_soon_threadsafe(_push)


def _execute_run(run_id: str, source_repo_path: Path, max_iterations: int) -> None:
    state = RUNS[run_id]
    state.status = "running"
    loop = asyncio.get_event_loop()

    try:
        result = run_agent(
            source_repo_path=source_repo_path,
            run_id=run_id,
            runs_dir=RUNS_DIR,
            max_iterations=max_iterations,
            on_event=lambda event: _broadcast(run_id, loop, event),
        )
        state.result = result
        state.status = "completed"
    except Exception as exc:  # noqa: BLE001
        state.error = f"{type(exc).__name__}: {exc}"
        state.status = "failed"
    finally:
        _broadcast(run_id, loop, {"type": "connection_closed"})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/bugs")
async def list_bugs() -> list[dict]:
    bugs = []
    for bug_dir in sorted(BUG_BANK_DIR.iterdir()):
        metadata_path = bug_dir / "metadata.json"
        if not metadata_path.exists():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        bugs.append({"bug_id": bug_dir.name, **metadata})
    return bugs


@app.post("/api/runs", response_model=RunSummary)
async def create_run(
    bug_id: Optional[str] = Form(None),
    repo_zip: Optional[UploadFile] = File(None),
    max_iterations: int = Form(MAX_ITERATIONS),
) -> RunSummary:
    if not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured on the server")

    run_id = uuid.uuid4().hex[:12]

    if bug_id:
        source_repo_path = BUG_BANK_DIR / bug_id / "repo"
        if not source_repo_path.is_dir():
            raise HTTPException(status_code=404, detail=f"unknown bug_id: {bug_id}")
    elif repo_zip is not None:
        upload_dir = RUNS_DIR / run_id / "upload"
        upload_dir.mkdir(parents=True, exist_ok=True)
        zip_path = upload_dir / "repo.zip"
        with open(zip_path, "wb") as f:
            shutil.copyfileobj(repo_zip.file, f)
        extract_dir = RUNS_DIR / run_id / "upload_source"
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        source_repo_path = extract_dir
    else:
        raise HTTPException(status_code=400, detail="must provide either bug_id or repo_zip")

    state = RunState(run_id=run_id, bug_id=bug_id)
    RUNS[run_id] = state

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _execute_run, run_id, source_repo_path, max_iterations)

    return RunSummary(run_id=run_id, bug_id=bug_id, status=state.status)


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    state = RUNS.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    return {
        "run_id": state.run_id,
        "bug_id": state.bug_id,
        "status": state.status,
        "result": state.result,
        "error": state.error,
    }


@app.get("/api/runs/{run_id}/trace")
async def get_run_trace(run_id: str) -> list:
    trace_path = RUNS_DIR / run_id / "trace.json"
    if not trace_path.exists():
        raise HTTPException(status_code=404, detail="no trace found for this run_id")
    return json.loads(trace_path.read_text(encoding="utf-8"))


@app.websocket("/ws/runs/{run_id}")
async def ws_run_trace(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    state = RUNS.get(run_id)
    if state is None:
        await websocket.send_json({"type": "error", "message": "unknown run_id"})
        await websocket.close()
        return

    queue: asyncio.Queue = asyncio.Queue()
    for event in state.events:
        queue.put_nowait(event)
    state.queues.append(queue)

    try:
        while True:
            event = await queue.get()
            if event.get("type") == "connection_closed":
                await websocket.send_json(event)
                break
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        if queue in state.queues:
            state.queues.remove(queue)


@app.get("/api/eval/report")
async def get_eval_report() -> dict:
    if not RESULTS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="no harness report yet - run `python eval/run_harness.py` first",
        )
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


@app.get("/api/eval/report/{bug_id}")
async def get_bug_report(bug_id: str) -> dict:
    report = await get_eval_report()
    bug_result = next((r for r in report["results"] if r["bug_id"] == bug_id), None)
    if bug_result is None:
        raise HTTPException(status_code=404, detail=f"no eval result for bug_id: {bug_id}")

    trace_path = Path(bug_result["trace_path"])
    trace = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.exists() else []

    diff_path = BUG_BANK_DIR / bug_id / "expected_diff.patch"
    expected_diff = diff_path.read_text(encoding="utf-8") if diff_path.exists() else None

    return {"result": bug_result, "trace": trace, "expected_diff": expected_diff}
