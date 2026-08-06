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
   (`core.py`), the Groq tool-use client wrapper (`llm_client.py`), and the
   sandbox executor (`sandbox.py`). The agent has exactly five tools
   (`tools.py`): `read_file`, `list_files`, `search_codebase` (grep-style
   text search), `run_tests` (runs pytest, returns pass/fail counts and
   failing tracebacks), and `write_patch` (full-file replacement).
2. **Eval harness** (`eval/`) - a curated bank of 18 seeded bugs across
   three difficulty tiers, plus a runner that scores the agent against all
   of them and reports per-tier pass rates honestly. Each bug is its own
   directory - `eval/bug_bank/bug_NNN_name/` - containing a real, runnable
   `repo/` with a broken implementation and a genuine pytest suite that
   fails against it, a `metadata.json` (difficulty, bug type, description),
   and an `expected_diff.patch` reference fix (used for scoring reference
   only, never shown to the agent).
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

## Try it

With both the backend (`:8000`) and frontend (`:5173`) running:

1. Open `http://localhost:5173` - lands on the **Live Run** page.
2. Pick any entry from the bug bank dropdown (e.g. `bug_014_stale_state_snapshot`).
3. Click **Run PatchPilot** and watch the reasoning trace stream in live over
   the WebSocket - tool calls, test results, and the final patch, step by
   step.
4. Visit **Eval Leaderboard** for the full 18-bug scoreboard, or click any
   row to see that bug's complete trace + reference diff on the
   **Bug Detail** page.

You can also drive it without the dashboard, either against a bug-bank
entry or your own zipped repo:

```bash
# against a bug-bank entry
curl -X POST http://localhost:8000/api/runs -F "bug_id=bug_001_off_by_one"

# against your own repo (must contain a pytest suite)
curl -X POST http://localhost:8000/api/runs -F "repo_zip=@/path/to/your-repo.zip"

# both return {"run_id": "...", ...} - poll status or trace with it:
curl http://localhost:8000/api/runs/<run_id>
curl http://localhost:8000/api/runs/<run_id>/trace
```

## API reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/api/bugs` | List all bug-bank entries (id, difficulty, type, description) |
| POST | `/api/runs` | Start a run - form fields: `bug_id` OR `repo_zip`, optional `max_iterations` |
| GET | `/api/runs/{run_id}` | Run status and final result (once completed) |
| GET | `/api/runs/{run_id}/trace` | Full step-by-step JSON trace for a run |
| WS | `/ws/runs/{run_id}` | Live trace events as they happen, then a final `connection_closed` |
| GET | `/api/eval/report` | The latest `harness_report.json` |
| GET | `/api/eval/report/{bug_id}` | One bug's result + full trace + reference diff |

## Configuration

All read from `.env` (see `.env.example`) - every one has a working default
except `GROQ_API_KEY`.

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Groq API key the agent uses for every LLM call |
| `PATCHPILOT_MODEL` | `openai/gpt-oss-120b` | Model used for the reasoning loop |
| `MAX_ITERATIONS` | `6` | Agent turn cap before it gives up on a bug |
| `TEST_TIMEOUT_SECONDS` | `30` | Wall-clock timeout per `pytest` invocation inside the sandbox |
| `MAX_RUN_DURATION_SECONDS` | `300` | Total budget for sandbox file/test operations across one run |
| `RUNS_DIR` | `runs` | Where per-run sandboxes and trace files are written |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend URL the frontend calls |

## Testing

```bash
pytest
```

Runs the 23 tests in `tests/` (sandbox path-jail and timeout enforcement,
agent loop iteration/success/failure logic with a mocked LLM, API endpoint
status codes and response shapes). `pytest.ini` scopes collection to
`tests/` only - without it, bare `pytest` would also try to collect the
bug bank's intentionally-broken test files.

## Running the eval harness

```bash
python eval/run_harness.py
```

This runs the agent against every bug in `eval/bug_bank/`, writes
`eval/results/harness_report.json`, and prints a per-tier summary. Requires
`GROQ_API_KEY` to be set - the harness makes real chat-completions API
calls, there is no mocked or scripted mode for this run.

## Eval results

Run against `openai/gpt-oss-120b` via Groq, `MAX_ITERATIONS=6`. Full data in
[`eval/results/harness_report.json`](eval/results/harness_report.json).

**Overall: 15/18 (83%)**

| Tier | Passed | Pass rate |
|---|---|---|
| Easy | 6/7 | 86% |
| Medium | 4/6 | 67% |
| Hard | 5/5 | 100% |

- Avg iterations to success: **4.13**
- Avg iterations to give-up: **6** (all 3 gave-up runs hit the iteration cap)

**On the 100% hard-tier pass rate:** read at face value this looks like the
hard bugs weren't actually hard, which is exactly the failure mode this
section is supposed to call out. Looking at the traces
(`runs/eval_bug_01{4..8}_*/trace.json`), the model did genuinely have to
read across 2-3 files and identify the real root cause in each case (a
stale snapshot instead of a live reference, a cache contract violated in a
different file than the one that crashes, a missing `invalidate()` call,
a wrong override of a geometric formula, a missing `unsubscribe()` before
resubscribing) - it just took more iterations to get there (avg 5.4 vs 3.3
for easy). With only 5 hard bugs the sample is small enough that 100%
isn't strong evidence the tier is mis-calibrated, but it's also not enough
runs to rule that out either; a larger hard-tier bank would tell more.

**On the 3 failures:** all three were **infrastructure failures, not
reasoning failures** - every one of the three gave-up runs recorded either
a Groq 429 rate-limit error or a raw connection error mid-run
(`llm_error` events in the trace), not the model exhausting its ideas and
stopping. `run_harness.py`'s failure-mode classifier does not yet
distinguish "API call failed" from "agent ran out of hypotheses" - that's
a known gap (see Known Limitations). Two of these three runs also show
anomalously long wall-clock times (`bug_006`: ~5 hours, `bug_013`: ~21
minutes) because the Groq client's retry/backoff blocked on those errors
before finally giving up - `agent/sandbox.py`'s duration budget only
guards sandbox operations (file I/O, test runs), not the LLM API call
itself, so a stalled network request isn't currently bounded.

| Bug | Difficulty | Outcome | Iterations |
|---|---|---|---|
| bug_001_off_by_one | easy | Pass | 3 |
| bug_002_wrong_comparator | easy | Pass | 3 |
| bug_003_swapped_arguments | easy | Pass | 3 |
| bug_004_wrong_operator | easy | Pass | 3 |
| bug_005_string_slice_off_by_one | easy | Pass | 3 |
| bug_006_boolean_logic | easy | Fail (infra) | 6 |
| bug_007_empty_list_default | easy | Pass | 3 |
| bug_008_retry_threshold | medium | Fail (infra) | 6 |
| bug_009_wrong_key_lookup | medium | Pass | 4 |
| bug_010_unit_conversion_drift | medium | Pass | 4 |
| bug_011_state_not_reset | medium | Pass | 4 |
| bug_012_incorrect_sort_key | medium | Pass | 5 |
| bug_013_rounding_accumulation | medium | Fail (infra) | 6 |
| bug_014_stale_state_snapshot | hard | Pass | 6 |
| bug_015_interface_contract_violation | hard | Pass | 6 |
| bug_016_cache_invalidation_missing | hard | Pass | 6 |
| bug_017_inheritance_override_bug | hard | Pass | 5 |
| bug_018_event_bus_double_subscribe | hard | Pass | 4 |

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
- **Hard-tier bugs are genuinely hard, and the 100% pass rate deserves
  scrutiny, not celebration.** See the "On the 100% hard-tier pass rate"
  discussion above - the sample is only 5 bugs, which is too small to
  confirm the tier is well-calibrated even though the traces show real
  multi-file investigation happening.
- **The LLM API call itself is not time-bounded.** `agent/sandbox.py`'s
  duration budget only guards sandboxed operations (file I/O, test runs);
  a stalled or rate-limited call to the LLM provider inside
  `agent/llm_client.py` can block for as long as the provider's own
  retry/backoff takes. This was observed directly in the eval run above -
  two runs stalled for extended periods on Groq rate-limit/connection
  errors before finally giving up. A request-level timeout around
  `LLMClient.send()` is the natural fix and isn't implemented yet.
- **The failure-mode classifier doesn't distinguish infra errors from
  reasoning gaps.** `eval/run_harness.py::classify_failure_mode` currently
  only checks whether the agent left behind a hypothesis. It does not
  special-case "the LLM API call itself failed" (rate limit, connection
  error) versus "the agent ran out of ideas" - both currently show up as
  `gave_up_no_hypothesis`. All 3 failures in the eval run above were
  actually the former; the trace's `llm_error` events are the reliable
  signal for this today, but the harness doesn't surface it in the
  aggregate stats yet.
- **In-memory run state.** The backend keeps run status and trace queues
  in a process-local dict (`backend/main.py`), so it does not survive a
  backend restart and does not horizontally scale across multiple backend
  processes. Fine for a single-instance demo, not for production.

## Project structure

```
patchpilot/
├── agent/             # ReAct loop, sandbox, LLM client, tool implementations
├── eval/
│   ├── bug_bank/      # 18 seeded bugs (7 easy, 6 medium, 5 hard)
│   ├── run_harness.py
│   └── results/       # harness_report.json lands here
├── backend/           # FastAPI app
├── frontend/          # React + Vite + Tailwind dashboard
├── tests/             # sandbox, agent loop, and API tests
└── docker-compose.yml
```

---

Project by Ayush Verma - ayushv3533e@gmail.com
