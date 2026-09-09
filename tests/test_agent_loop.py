import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.core import run_agent
from agent.llm_client import LLMResponse


class FakeLLMClient:
    """Stands in for LLMClient in tests - returns a pre-scripted sequence of
    responses instead of calling the real Groq API."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def send(self, system_prompt: str, messages: list[dict]) -> LLMResponse:
        self.calls += 1
        if not self._responses:
            raise AssertionError("FakeLLMClient ran out of scripted responses")
        return self._responses.pop(0)


def text_response(text: str) -> LLMResponse:
    return LLMResponse(
        content_blocks=[{"type": "text", "text": text}],
        stop_reason="end_turn",
        input_tokens=10,
        output_tokens=10,
        raw_text=text,
    )


def tool_use_response(tool_name: str, tool_input: dict, tool_id: str = "tool_1") -> LLMResponse:
    return LLMResponse(
        content_blocks=[{"type": "tool_use", "id": tool_id, "name": tool_name, "input": tool_input}],
        stop_reason="tool_use",
        input_tokens=20,
        output_tokens=15,
        raw_text="",
    )


class FlakyLLMClient:
    """Raises for the first `fail_times` calls, then returns scripted responses."""

    def __init__(self, fail_times: int, responses: list[LLMResponse]) -> None:
        self.fail_times = fail_times
        self._responses = list(responses)
        self.calls = 0

    def send(self, system_prompt: str, messages: list[dict]) -> LLMResponse:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("simulated transient LLM failure")
        return self._responses.pop(0)


class AlwaysFailingLLMClient:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, system_prompt: str, messages: list[dict]) -> LLMResponse:
        self.calls += 1
        raise RuntimeError("simulated persistent LLM failure")


@pytest.fixture
def broken_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "mathutils.py").write_text(
        "def sum_first_n(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total\n",
        encoding="utf-8",
    )
    (repo / "test_mathutils.py").write_text(
        "from mathutils import sum_first_n\n\n\ndef test_sum():\n    assert sum_first_n(5) == 15\n",
        encoding="utf-8",
    )
    return repo


def test_agent_succeeds_after_correct_patch(tmp_path: Path, broken_repo: Path) -> None:
    fixed_content = (
        "def sum_first_n(n):\n    total = 0\n    for i in range(1, n + 1):\n        total += i\n    return total\n"
    )
    fake_llm = FakeLLMClient(
        [
            tool_use_response("write_patch", {"file_path": "mathutils.py", "new_content": fixed_content}),
            text_response("Fixed an off-by-one error in the range() call."),
        ]
    )

    report = run_agent(
        source_repo_path=broken_repo,
        run_id="unit-success",
        runs_dir=tmp_path / "runs",
        max_iterations=6,
        llm_client=fake_llm,
    )

    assert report["success"] is True
    assert report["iterations"] == 1
    assert report["summary"] == "Fixed an off-by-one error in the range() call."


def test_agent_gives_up_after_max_iterations(tmp_path: Path, broken_repo: Path) -> None:
    fake_llm = FakeLLMClient([text_response(f"Still investigating, hypothesis #{i}") for i in range(10)])

    report = run_agent(
        source_repo_path=broken_repo,
        run_id="unit-giveup",
        runs_dir=tmp_path / "runs",
        max_iterations=3,
        llm_client=fake_llm,
    )

    assert report["success"] is False
    assert report["iterations"] == 3
    assert report["last_hypothesis"] == "Still investigating, hypothesis #2"


def test_agent_iterates_when_patch_does_not_fix_tests(tmp_path: Path, broken_repo: Path) -> None:
    wrong_patch = "def sum_first_n(n):\n    return 0\n"
    correct_patch = (
        "def sum_first_n(n):\n    total = 0\n    for i in range(1, n + 1):\n        total += i\n    return total\n"
    )
    fake_llm = FakeLLMClient(
        [
            tool_use_response("write_patch", {"file_path": "mathutils.py", "new_content": wrong_patch}, "t1"),
            tool_use_response("write_patch", {"file_path": "mathutils.py", "new_content": correct_patch}, "t2"),
            text_response("Second attempt fixed the summation logic."),
        ]
    )

    report = run_agent(
        source_repo_path=broken_repo,
        run_id="unit-retry",
        runs_dir=tmp_path / "runs",
        max_iterations=6,
        llm_client=fake_llm,
    )

    assert report["success"] is True
    assert report["iterations"] == 2


def test_agent_reads_files_before_patching(tmp_path: Path, broken_repo: Path) -> None:
    fixed_content = (
        "def sum_first_n(n):\n    total = 0\n    for i in range(1, n + 1):\n        total += i\n    return total\n"
    )
    fake_llm = FakeLLMClient(
        [
            tool_use_response("read_file", {"path": "mathutils.py"}, "t1"),
            tool_use_response("write_patch", {"file_path": "mathutils.py", "new_content": fixed_content}, "t2"),
            text_response("Investigated then fixed the off-by-one."),
        ]
    )

    report = run_agent(
        source_repo_path=broken_repo,
        run_id="unit-read-first",
        runs_dir=tmp_path / "runs",
        max_iterations=6,
        llm_client=fake_llm,
    )

    assert report["success"] is True
    assert report["iterations"] == 2


def test_agent_skips_run_when_suite_already_passes(tmp_path: Path) -> None:
    repo = tmp_path / "already_passing"
    repo.mkdir()
    (repo / "app.py").write_text("def ok():\n    return True\n", encoding="utf-8")
    (repo / "test_app.py").write_text("from app import ok\n\n\ndef test_ok():\n    assert ok()\n", encoding="utf-8")

    fake_llm = FakeLLMClient([])  # should never be called

    report = run_agent(
        source_repo_path=repo,
        run_id="unit-already-passing",
        runs_dir=tmp_path / "runs",
        max_iterations=6,
        llm_client=fake_llm,
    )

    assert report["success"] is True
    assert report["iterations"] == 0
    assert fake_llm.calls == 0


def test_agent_retries_transient_llm_errors_within_an_iteration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, broken_repo: Path
) -> None:
    monkeypatch.setattr("agent.core.LLM_RETRY_BACKOFF_SECONDS", 0)
    fixed_content = (
        "def sum_first_n(n):\n    total = 0\n    for i in range(1, n + 1):\n        total += i\n    return total\n"
    )
    flaky_llm = FlakyLLMClient(
        fail_times=2,  # fails twice, succeeds on the 3rd attempt (initial + 2 retries)
        responses=[
            tool_use_response("write_patch", {"file_path": "mathutils.py", "new_content": fixed_content}),
            text_response("Fixed after a couple of transient errors."),
        ],
    )

    report = run_agent(
        source_repo_path=broken_repo,
        run_id="unit-flaky-recovery",
        runs_dir=tmp_path / "runs",
        max_iterations=6,
        llm_client=flaky_llm,
    )

    assert report["success"] is True
    assert report["iterations"] == 1  # retries within an iteration don't advance the counter
    assert flaky_llm.calls == 4  # 2 failures + 1 successful write_patch + 1 summary request


def test_agent_gives_up_after_exhausting_llm_retries_reports_actual_iteration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, broken_repo: Path
) -> None:
    monkeypatch.setattr("agent.core.LLM_RETRY_BACKOFF_SECONDS", 0)
    failing_llm = AlwaysFailingLLMClient()

    report = run_agent(
        source_repo_path=broken_repo,
        run_id="unit-persistent-failure",
        runs_dir=tmp_path / "runs",
        max_iterations=6,
        llm_client=failing_llm,
    )

    assert report["success"] is False
    # gives up on the first iteration rather than mislabeling this as
    # "exhausted all 6 iterations" - it never got past iteration 1
    assert report["iterations"] == 1
    assert failing_llm.calls == 3  # 1 initial attempt + 2 retries


def test_agent_succeeds_using_apply_diff(tmp_path: Path, broken_repo: Path) -> None:
    fake_llm = FakeLLMClient(
        [
            tool_use_response(
                "apply_diff",
                {
                    "file_path": "mathutils.py",
                    "search_block": "range(1, n)",
                    "replace_block": "range(1, n + 1)",
                },
            ),
            text_response("Applied targeted diff fix to range end-point."),
        ]
    )

    report = run_agent(
        source_repo_path=broken_repo,
        run_id="unit-apply-diff-success",
        runs_dir=tmp_path / "runs",
        max_iterations=6,
        llm_client=fake_llm,
    )

    assert report["success"] is True
    assert report["iterations"] == 1
    assert report["summary"] == "Applied targeted diff fix to range end-point."

