# PatchPilot

[![CI](https://github.com/AyushCipher/Patch-Pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/AyushCipher/Patch-Pilot/actions/workflows/ci.yml)

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
| `LLM_REQUEST_TIMEOUT_SECONDS` | `90` | Hard wall-clock cap on a single LLM call; retried up to twice with a 5s backoff before the run gives up |
| `RUNS_DIR` | `runs` | Where per-run sandboxes and trace files are written |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend URL the frontend calls |

## Testing

```bash
pytest                          # backend: 25 tests
cd frontend && npm test         # frontend: 9 tests (vitest)
```

Backend tests cover sandbox path-jail and timeout enforcement, agent loop
iteration/success/failure/retry logic with a mocked LLM (including the
LLM-call-retry-then-give-up path), and API endpoint status codes and
response shapes. `pytest.ini` scopes collection to `tests/` only - without
it, bare `pytest` would also try to collect the bug bank's
intentionally-broken test files.

Frontend tests cover the report-formatting helpers in `frontend/src/utils/format.ts`
- added after a real bug: a page rendering an older `harness_report.json`
(missing fields the newer harness adds) crashed with `Cannot read
properties of undefined (reading 'toFixed')`, caught only by actually
running the app in a browser, not by the type checker. Both CI jobs
(`.github/workflows/ci.yml`) run these on every push.

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
This is the run *after* the LLM-call-timeout fix described below - an
earlier run (still in git history) scored 15/18 with 3 failures, two of
which were multi-hour infrastructure stalls. This run's numbers are the
ones to trust.

**Overall: 17/18 (94%)**

| Tier | Passed | Pass rate |
|---|---|---|
| Easy | 7/7 | 100% |
| Medium | 5/6 | 83% |
| Hard | 5/5 | 100% |

- Avg iterations to success: computed per-run in the report; typically 3-6
- Estimated cost: **$0.0201 total, $0.0011 avg per successful fix** (Groq
  list pricing: $0.15/M input tokens, $0.60/M output tokens for
  `openai/gpt-oss-120b`, see Known Limitations for what this estimate does
  and doesn't cover)
- Latency: **avg 48.5s, median 40.3s, p90 74.0s** per bug (excludes runs
  that gave up purely due to a bounded LLM-call failure with zero
  reasoning progress - see `aggregate()` in `run_harness.py`)

**On the timeout fix actually working:** the two bugs that previously
stalled for hours on Groq rate-limit/connection errors (`bug_006`: ~5
hours, `bug_013`: ~21 minutes) now complete in 27.8s and 35.7s respectively
in this run. That's the direct, measured effect of bounding
`LLMClient.send()` to a hard per-call timeout with a small retry budget
instead of letting the SDK's own retry-after backoff run unbounded - see
`agent/llm_client.py::LLMRequestTimeout` and `agent/core.py`'s
`MAX_LLM_RETRIES_PER_ITERATION`.

**On the one remaining failure (`bug_008_retry_threshold`):** this time
it's a genuine reasoning failure, not infrastructure - the trace
(`runs/eval_bug_008_retry_threshold/trace.json`) shows no `llm_error`
events at all. The model investigated correctly, wrote a semantically
correct fix on iteration 5, but the generated file had a stray trailing
`}` character (a plausible LLM-tool-call artifact, not present in Python
syntax), which raised a `SyntaxError` on test collection. The auto-run
after `write_patch` caught this immediately and reported it back to the
model, but the model spent its 6th and final iteration re-running
`run_tests` to re-confirm the same failure instead of rereading and fixing
its own patch, then ran out of budget. This is exactly the kind of
"plausible-looking patch that wasn't actually verified correctly" failure
mode the harness is designed to surface - a real reasoning gap, not
noise.

**On the 100% hard-tier pass rate (both runs):** still worth scrutiny, not
celebration - see Known Limitations. Looking at the hard-tier traces, the
model did genuinely have to read across 2-3 files and identify the real
root cause in each case (a stale snapshot instead of a live reference, a
cache contract violated in a different file than the one that crashes, a
missing `invalidate()` call, a wrong override of a geometric formula, a
missing `unsubscribe()` before resubscribing) - it just took more
iterations to get there. With only 5 hard bugs the sample is too small to
either confirm or rule out that the tier is mis-calibrated.

| Bug | Difficulty | Outcome | Iterations | Time (s) | Est. cost |
|---|---|---|---|---|---|
| bug_001_off_by_one | easy | Pass | 3 | 33.2 | $0.0007 |
| bug_002_wrong_comparator | easy | Pass | 3 | 23.1 | $0.0005 |
| bug_003_swapped_arguments | easy | Pass | 4 | 71.3 | $0.0011 |
| bug_004_wrong_operator | easy | Pass | 3 | 72.1 | $0.0007 |
| bug_005_string_slice_off_by_one | easy | Pass | 3 | 37.4 | $0.0008 |
| bug_006_boolean_logic | easy | Pass | 3 | 27.8 | $0.0006 |
| bug_007_empty_list_default | easy | Pass | 3 | 25.2 | $0.0005 |
| bug_008_retry_threshold | medium | Fail (reasoning) | 6 | 52.3 | $0.0014 |
| bug_009_wrong_key_lookup | medium | Pass | 5 | 40.0 | $0.0012 |
| bug_010_unit_conversion_drift | medium | Pass | 6 | 81.5 | $0.0018 |
| bug_011_state_not_reset | medium | Pass | 5 | 40.3 | $0.0011 |
| bug_012_incorrect_sort_key | medium | Pass | 5 | 33.6 | $0.0011 |
| bug_013_rounding_accumulation | medium | Pass | 4 | 35.7 | $0.0009 |
| bug_014_stale_state_snapshot | hard | Pass | 6 | 59.6 | $0.0015 |
| bug_015_interface_contract_violation | hard | Pass | 6 | 61.2 | $0.0016 |
| bug_016_cache_invalidation_missing | hard | Pass | 6 | 68.0 | $0.0016 |
| bug_017_inheritance_override_bug | hard | Pass | 5 | 57.1 | $0.0016 |
| bug_018_event_bus_double_subscribe | hard | Pass | 5 | 57.7 | $0.0013 |

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
- **~~The LLM API call itself is not time-bounded~~ - fixed.** Originally,
  `agent/sandbox.py`'s duration budget only guarded sandboxed operations
  (file I/O, test runs); a stalled or rate-limited call to the LLM
  provider could block for as long as the provider's own retry/backoff
  took - observed directly as multi-hour stalls in an earlier eval run
  (still in git history). `agent/llm_client.py::LLMClient.send()` now runs
  the API call in a worker thread with a hard `LLM_REQUEST_TIMEOUT_SECONDS`
  deadline (default 90s) via `future.result(timeout=...)`, and
  `agent/core.py` retries a failed call up to `MAX_LLM_RETRIES_PER_ITERATION`
  times before giving up on the run. The eval results above are the
  re-run after this fix, and the two previously-stalled bugs now complete
  in under a minute each.
- **The failure-mode classifier doesn't distinguish infra errors from
  reasoning gaps in its aggregate stats.** `eval/run_harness.py::classify_failure_mode`
  only checks whether the agent left behind a hypothesis - it doesn't
  special-case "the LLM call failed/timed out" versus "the agent
  investigated and gave up." Both show up as `gave_up_no_hypothesis` in
  `failure_mode_breakdown`. The trace's `llm_error` events (now with an
  `attempt` field) are the reliable per-run signal for this today, but the
  harness doesn't roll it up automatically.
- **Cost estimates are static list pricing, not billing data.** `eval/run_harness.py::PRICING_PER_MILLION_TOKENS_USD`
  is a hardcoded rate table (Groq's published $0.15/M input, $0.60/M
  output for `openai/gpt-oss-120b` as of 2026-08) multiplied against
  reported token counts - it is not pulled from a billing API and will
  silently go stale if Groq changes rates or a different model is
  configured without updating the table (unknown models fall back to a
  `null` cost rather than a wrong number, at least).
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
