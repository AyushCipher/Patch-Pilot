import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import main as backend_main  # noqa: E402

client = TestClient(backend_main.app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_bugs_returns_full_bug_bank() -> None:
    response = client.get("/api/bugs")
    assert response.status_code == 200
    bugs = response.json()
    assert len(bugs) == 18
    bug_ids = {b["bug_id"] for b in bugs}
    assert "bug_001_off_by_one" in bug_ids
    assert all("difficulty" in b and "bug_type" in b for b in bugs)


def test_create_run_requires_bug_id_or_zip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "sk-test-key")
    response = client.post("/api/runs")
    assert response.status_code == 400


def test_create_run_without_api_key_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    response = client.post("/api/runs", data={"bug_id": "bug_001_off_by_one"})
    assert response.status_code == 503


def test_create_run_unknown_bug_id_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "sk-test-key")
    response = client.post("/api/runs", data={"bug_id": "bug_does_not_exist"})
    assert response.status_code == 404


def test_get_unknown_run_returns_404() -> None:
    response = client.get("/api/runs/does-not-exist")
    assert response.status_code == 404


def test_get_unknown_run_trace_returns_404() -> None:
    response = client.get("/api/runs/does-not-exist/trace")
    assert response.status_code == 404


def test_eval_report_404_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(backend_main, "RESULTS_PATH", tmp_path / "no_report_here.json")
    response = client.get("/api/eval/report")
    assert response.status_code == 404


def test_eval_report_and_bug_detail_shape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(json.dumps([{"type": "run_started", "timestamp": 1.0}]), encoding="utf-8")

    fake_report = {
        "generated_at": 1.0,
        "results": [
            {
                "bug_id": "bug_001_off_by_one",
                "difficulty": "easy",
                "bug_type": "off-by-one",
                "success": True,
                "iterations": 1,
                "wall_clock_seconds": 2.5,
                "input_tokens": 100,
                "output_tokens": 50,
                "estimated_cost_usd": 0.00004,
                "last_hypothesis": None,
                "summary": "Fixed it",
                "trace_path": str(trace_path),
                "error": None,
                "failure_mode": None,
            }
        ],
        "aggregate": {
            "total_bugs": 1,
            "total_passed": 1,
            "overall_pass_rate": 1.0,
            "by_difficulty": {
                "easy": {"total": 1, "passed": 1, "pass_rate": 1.0},
                "medium": {"total": 0, "passed": 0, "pass_rate": None},
                "hard": {"total": 0, "passed": 0, "pass_rate": None},
            },
            "avg_iterations_to_success": 1.0,
            "avg_iterations_to_giveup": None,
            "most_common_failure_mode": None,
            "failure_mode_breakdown": {},
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "total_estimated_cost_usd": 0.00004,
            "avg_cost_per_successful_fix_usd": 0.00004,
            "avg_wall_clock_seconds": 2.5,
            "median_wall_clock_seconds": 2.5,
            "p90_wall_clock_seconds": None,
        },
    }
    report_path = tmp_path / "harness_report.json"
    report_path.write_text(json.dumps(fake_report), encoding="utf-8")
    monkeypatch.setattr(backend_main, "RESULTS_PATH", report_path)

    report_response = client.get("/api/eval/report")
    assert report_response.status_code == 200
    assert report_response.json()["aggregate"]["total_passed"] == 1

    detail_response = client.get("/api/eval/report/bug_001_off_by_one")
    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["result"]["bug_id"] == "bug_001_off_by_one"
    assert body["trace"][0]["type"] == "run_started"
    assert body["expected_diff"] is not None and "sum_first_n" in body["expected_diff"]

    missing_response = client.get("/api/eval/report/bug_does_not_exist")
    assert missing_response.status_code == 404
