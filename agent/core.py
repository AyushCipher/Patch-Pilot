"""The ReAct-style single-agent reasoning loop.

Flow:
  1. Sandbox the target repo (copy into runs/{run_id}/sandbox)
  2. Run tests once to capture the initial failure state
  3. Send the LLM: task framing + failing test output + available tools
  4. LLM responds with a tool call
  5. Execute the tool, return the real result to the LLM
  6. Repeat 4-5 until the LLM calls write_patch, then auto re-run tests
  7. If tests pass: stop, record success + a natural-language summary
  8. If tests still fail: feed the new failure output back as the next turn
  9. Cap at MAX_ITERATIONS. If exceeded: stop, record failure + last hypothesis

Each LLM call is individually wall-clock bounded (LLMClient's own
request_timeout_seconds) and retried up to MAX_LLM_RETRIES_PER_ITERATION
times with a short backoff before the whole run gives up - this bounds a
single flaky/rate-limited call to a few minutes instead of letting the
provider's own retry-after backoff stall the run indefinitely.

Every step is appended to a structured JSON trace file so the dashboard can
render a live, step-by-step view of the agent's reasoning.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from agent.llm_client import LLMClient
from agent.sandbox import Sandbox, SandboxRunDurationExceeded, SandboxTimeoutError
from agent.tools import execute_tool

DEFAULT_MAX_ITERATIONS = 6
MAX_LLM_RETRIES_PER_ITERATION = 2
LLM_RETRY_BACKOFF_SECONDS = 5

SYSTEM_PROMPT = """You are PatchPilot, an autonomous code-review and bug-fixing agent.

You are given a Python repository with a failing pytest suite. Your job is to:
1. Investigate using read_file, list_files, and search_codebase to understand
   the code and form a hypothesis about why the tests are failing.
2. Call run_tests whenever you want to verify current behavior.
3. Once you understand the bug, you can apply fixes in one of two ways:
   - Call write_patch with the COMPLETE new contents of the file you are fixing.
   - Call apply_diff with search_block + replace_block (or a unified diff) for targeted edits in larger files.
   Python syntax is automatically validated before saving. You may patch more than one file across multiple turns.
4. After a patch is applied, tests will automatically be re-run and you will
   see the result in the next turn.
5. Keep iterating until the tests pass. You have a limited number of turns,
   so investigate efficiently and prefer the smallest fix that makes the
   failing behavior correct - do not do unrelated refactors.

Be concise. When you believe the suite passes, say so briefly. If you are
stuck, state your current best hypothesis clearly before your turns run out."""

EventCallback = Callable[[dict], None]


class Trace:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.events: list[dict] = []

    def log(self, event_type: str, on_event: EventCallback | None = None, **fields: Any) -> dict:
        event = {
            "type": event_type,
            "timestamp": time.time(),
            **fields,
        }
        self.events.append(event)
        self.path.write_text(json.dumps(self.events, indent=2), encoding="utf-8")
        if on_event is not None:
            on_event(event)
        return event


def run_agent(
    source_repo_path: str | Path,
    run_id: str | None = None,
    runs_dir: str | Path = "runs",
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    test_timeout_seconds: int = 30,
    max_run_duration_seconds: int = 300,
    on_event: EventCallback | None = None,
    llm_client: LLMClient | None = None,
) -> dict:
    run_id = run_id or uuid.uuid4().hex[:12]
    trace = Trace(Path(runs_dir) / run_id / "trace.json")
    llm = llm_client or LLMClient()

    trace.log("run_started", on_event, run_id=run_id, source_repo_path=str(source_repo_path))

    sandbox = Sandbox(
        run_id=run_id,
        runs_dir=runs_dir,
        test_timeout_seconds=test_timeout_seconds,
        max_run_duration_seconds=max_run_duration_seconds,
    )
    sandbox.setup_from_dir(source_repo_path)
    trace.log("sandbox_ready", on_event, sandbox_root=str(sandbox.root))

    try:
        initial_result = sandbox.run_tests()
    except SandboxTimeoutError as exc:
        trace.log("run_failed", on_event, reason=f"initial test run timed out: {exc}")
        return _final_report(run_id, trace, success=False, iterations=0, hypothesis=None)

    trace.log(
        "initial_test_result",
        on_event,
        passed=initial_result.passed,
        failed=initial_result.failed,
        errors=initial_result.errors,
        failing_tests=initial_result.failing_tests,
    )

    if initial_result.all_passed:
        trace.log("run_completed", on_event, success=True, note="suite already passing")
        return _final_report(run_id, trace, success=True, iterations=0, hypothesis=None)

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                "The test suite is failing. Here is the initial pytest output:\n\n"
                f"passed={initial_result.passed} failed={initial_result.failed} "
                f"errors={initial_result.errors}\n\n"
                f"Failing tests:\n{json.dumps(initial_result.failing_tests, indent=2)}\n\n"
                f"stdout:\n{initial_result.stdout[-4000:]}\n\n"
                "Investigate and fix the repo. Use your tools."
            ),
        }
    ]

    last_hypothesis = None
    total_input_tokens = 0
    total_output_tokens = 0

    for iteration in range(1, max_iterations + 1):
        trace.log("iteration_started", on_event, iteration=iteration)

        response = None
        for attempt in range(1, MAX_LLM_RETRIES_PER_ITERATION + 2):
            try:
                response = llm.send(SYSTEM_PROMPT, messages)
                break
            except Exception as exc:  # noqa: BLE001
                trace.log(
                    "llm_error", on_event, iteration=iteration, attempt=attempt, error=str(exc)
                )
                if attempt <= MAX_LLM_RETRIES_PER_ITERATION:
                    time.sleep(LLM_RETRY_BACKOFF_SECONDS)

        if response is None:
            trace.log(
                "run_completed",
                on_event,
                success=False,
                iterations=iteration,
                hypothesis=last_hypothesis,
                note=f"LLM call failed after {MAX_LLM_RETRIES_PER_ITERATION + 1} attempts",
            )
            return _final_report(
                run_id,
                trace,
                success=False,
                iterations=iteration,
                hypothesis=last_hypothesis,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

        total_input_tokens += response.input_tokens
        total_output_tokens += response.output_tokens

        if response.raw_text:
            last_hypothesis = response.raw_text
            trace.log("llm_message", on_event, iteration=iteration, text=response.raw_text)

        messages.append({"role": "assistant", "content": response.content_blocks})

        tool_use_blocks = [b for b in response.content_blocks if b["type"] == "tool_use"]

        if not tool_use_blocks:
            if response.stop_reason == "end_turn":
                trace.log(
                    "agent_stopped_without_patch",
                    on_event,
                    iteration=iteration,
                    hypothesis=last_hypothesis,
                )
                messages.append(
                    {
                        "role": "user",
                        "content": "Tests are still failing. Continue investigating or write a patch.",
                    }
                )
            continue

        tool_results = []
        patch_written_this_turn = False
        for block in tool_use_blocks:
            trace.log(
                "tool_call",
                on_event,
                iteration=iteration,
                tool=block["name"],
                input=block["input"],
            )
            try:
                result = execute_tool(sandbox, block["name"], block["input"])
            except SandboxRunDurationExceeded as exc:
                trace.log("run_failed", on_event, reason=str(exc))
                return _final_report(
                    run_id, trace, success=False, iterations=iteration, hypothesis=last_hypothesis,
                    input_tokens=total_input_tokens, output_tokens=total_output_tokens,
                )

            trace.log("tool_result", on_event, iteration=iteration, tool=block["name"], result=result)

            if block["name"] in ("write_patch", "apply_diff") and "error" not in result:
                patch_written_this_turn = True

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": json.dumps(result)[:8000],
                }
            )

        if patch_written_this_turn:
            try:
                test_result = sandbox.run_tests()
            except SandboxTimeoutError as exc:
                trace.log("run_failed", on_event, reason=f"post-patch test run timed out: {exc}")
                return _final_report(
                    run_id, trace, success=False, iterations=iteration, hypothesis=last_hypothesis,
                    input_tokens=total_input_tokens, output_tokens=total_output_tokens,
                )

            trace.log(
                "post_patch_test_result",
                on_event,
                iteration=iteration,
                passed=test_result.passed,
                failed=test_result.failed,
                errors=test_result.errors,
                failing_tests=test_result.failing_tests,
            )

            if test_result.all_passed:
                messages.append({"role": "user", "content": tool_results})
                summary = _ask_for_summary(llm, messages, trace, on_event)
                trace.log("run_completed", on_event, success=True, iteration=iteration, summary=summary)
                return _final_report(
                    run_id,
                    trace,
                    success=True,
                    iterations=iteration,
                    hypothesis=last_hypothesis,
                    summary=summary,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                )

            tool_results.append(
                {
                    "type": "text",
                    "text": (
                        f"Patch applied but tests still fail: passed={test_result.passed} "
                        f"failed={test_result.failed} errors={test_result.errors}. "
                        f"Failing tests:\n{json.dumps(test_result.failing_tests, indent=2)}\n"
                        "Revise your hypothesis and continue."
                    ),
                }
            )

        messages.append({"role": "user", "content": tool_results})

    trace.log(
        "run_completed",
        on_event,
        success=False,
        iterations=max_iterations,
        hypothesis=last_hypothesis,
        note="max iterations exceeded",
    )
    return _final_report(
        run_id,
        trace,
        success=False,
        iterations=max_iterations,
        hypothesis=last_hypothesis,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
    )


def _ask_for_summary(
    llm: LLMClient, messages: list[dict], trace: Trace, on_event: EventCallback | None
) -> str:
    messages = messages + [
        {
            "role": "user",
            "content": (
                "Tests now pass. In 2-4 sentences, explain what was wrong and what you "
                "changed to fix it."
            ),
        }
    ]
    try:
        response = llm.send(SYSTEM_PROMPT, messages)
        return response.raw_text.strip()
    except Exception as exc:  # noqa: BLE001
        trace.log("llm_error", on_event, error=f"summary request failed: {exc}")
        return "(summary unavailable)"


def _final_report(
    run_id: str,
    trace: Trace,
    success: bool,
    iterations: int,
    hypothesis: str | None,
    summary: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> dict:
    return {
        "run_id": run_id,
        "success": success,
        "iterations": iterations,
        "last_hypothesis": hypothesis,
        "summary": summary,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "trace_path": str(trace.path),
    }
