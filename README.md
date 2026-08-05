# PatchPilot

PatchPilot is an autonomous code-review and bug-fixing agent. Point it at a
Python repository with a failing pytest suite, and it investigates the
codebase, forms a hypothesis, writes a patch, re-runs the tests, and
iterates - up to a fixed attempt cap - until the suite passes or it gives up
and reports its best remaining hypothesis.

It is a **single-agent, tool-use** system: one LLM reasoning loop, a small
fixed set of tools, explicit iteration. There is no multi-agent
orchestration or supervisor/specialist architecture here by design.

## Architecture

```
                     ┌─────────────────────────┐
                     │   Eval Harness           │
                     │   (eval/run_harness.py)  │
                     │   runs the agent against │
                     │   every bug in the bank   │
                     └────────────┬─────────────┘
                                  │
                                  ▼
┌───────────────┐        ┌───────────────────┐        ┌───────────────────┐
│ FastAPI + WS  │◄──────►│   Agent Core       │◄──────►│  Groq API          │
│ (backend/)    │  runs  │   (agent/core.py)  │  tools  │  (chat completions,│
│               │        │   ReAct loop       │  used   │   tool use)        │
└───────┬───────┘        └─────────┬─────────┘        └───────────────────┘
        │                          │
        │                          ▼
        │                ┌───────────────────┐
        │                │  Sandbox Executor  │
        │                │  (agent/sandbox.py)│
        │                │  path-jailed repo  │
        │                │  + pytest runner   │
        │                └───────────────────┘
        ▼
┌───────────────┐
│ React + Vite  │
│ Dashboard      │
│ (frontend/)    │
└───────────────┘
```

The agent core is the only thing that talks to the LLM. The eval harness and
the API/dashboard are two different ways of driving the same agent core -
the harness for batch scoring, the dashboard for watching one run live.

## Layers

1. **Agent core** (`agent/`) - the ReAct-style reasoning loop
   (`core.py`), the Groq tool-use client wrapper (`llm_client.py`), the
   five tool implementations (`tools.py`), and the sandbox executor
   (`sandbox.py`).
2. **Eval harness** (`eval/`) - a curated bank of 18 seeded bugs across
   three difficulty tiers, plus a runner that scores the agent against all
   of them and reports per-tier pass rates honestly.
3. **API + dashboard** (`backend/`, `frontend/`) - a FastAPI backend
   exposing runs and eval results (including a WebSocket for live trace
   streaming), and a React dashboard for watching the agent think, browsing
   the eval leaderboard, and inspecting any bug's full trace + diff.

## Setup

### Backend

```bash
python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env              # then fill in GROQ_API_KEY
uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Set `VITE_API_BASE_URL` (defaults to `http://localhost:8000`) if the
backend runs elsewhere.

### Docker

```bash
export GROQ_API_KEY=gsk_...
docker compose up --build
```

This runs the backend on `:8000` and the dashboard on `:5173`. Docker
Compose here only packages the API and frontend for deployment - it is
unrelated to the agent's own per-run sandbox isolation (see Known
Limitations below).

## Running the eval harness

```bash
python eval/run_harness.py
```

This runs the agent against every bug in `eval/bug_bank/`, writes
`eval/results/harness_report.json`, and prints a per-tier summary. Requires
`GROQ_API_KEY` to be set - the harness makes real chat-completions API
calls, there is no mocked or scripted mode for this run.

## Eval results

<!-- EVAL_RESULTS_TABLE -->

## Tech stack

| Layer | Technology |
|---|---|
| Agent reasoning | Groq Python SDK (`groq`), Chat Completions API tool use, `openai/gpt-oss-120b` |
| Sandbox execution | Python `subprocess`, directory-jailed filesystem checks |
| Backend | FastAPI, Uvicorn, WebSockets |
| Eval harness | Plain Python, pytest as the scoring oracle |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Router |
| Packaging | Docker, Docker Compose |

## Known limitations

- **Python/pytest only.** The agent, sandbox, and bug bank all assume a
  pytest-based Python repository. Multi-language support (JS/Jest, Go
  testing, etc.) is a documented roadmap item, not something half-built
  here.
- **Directory-jail isolation, not full containers.** `agent/sandbox.py`
  enforces a path-traversal check on every write and a wall-clock timeout
  per test run, but test code still executes as a subprocess on the host
  Python, not inside Docker-in-Docker. Full container-per-run isolation is
  a documented stretch goal for v2.
- **Whole-file patches, not unified diffs.** `write_patch` replaces a
  file's entire contents rather than applying a diff. This is simpler and
  more reliable for a single LLM turn, at the cost of noisier diffs for
  large files. Unified-diff patching is a stretch goal.
- **Hard-tier bugs are genuinely hard.** The eval results above are
  reported honestly per difficulty tier rather than as one aggregate
  number. If the agent were solving 100% of the hard tier, that would be a
  sign the hard bugs weren't actually hard - they involve stale state
  across modules, interface contracts violated in a different file than
  the one that breaks, and inheritance overrides that silently violate a
  base class invariant.
- **In-memory run state.** The backend keeps run status and trace queues
  in a process-local dict (`backend/main.py`), so it does not survive a
  backend restart and does not horizontally scale across multiple backend
  processes. Fine for a single-instance demo, not for production.

## Project structure

```
patchpilot/
├── agent/            # ReAct loop, sandbox, LLM client, tool implementations
├── eval/
│   ├── bug_bank/      # 18 seeded bugs (7 easy, 6 medium, 5 hard)
│   ├── run_harness.py
│   └── results/
├── backend/           # FastAPI app
├── frontend/           # React + Vite + Tailwind dashboard
├── tests/             # sandbox, agent loop, and API tests
└── docker-compose.yml
```

---

Project by Ayush Verma - ayushv3533e@gmail.com
