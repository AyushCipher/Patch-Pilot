import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.sandbox import Sandbox, SandboxPathError, SandboxTimeoutError, SandboxRunDurationExceeded


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source_repo"
    repo.mkdir()
    (repo / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo / "test_app.py").write_text(
        "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    return repo


@pytest.fixture
def sandbox(tmp_path: Path, source_repo: Path) -> Sandbox:
    sb = Sandbox(run_id="test-run", runs_dir=tmp_path / "runs")
    sb.setup_from_dir(source_repo)
    return sb


def test_read_write_roundtrip(sandbox: Sandbox) -> None:
    sandbox.write_file("app.py", "def add(a, b):\n    return a + b + 0\n")
    assert "+ 0" in sandbox.read_file("app.py")


def test_list_files_excludes_git_and_cache_dirs(sandbox: Sandbox) -> None:
    (sandbox.root / ".git").mkdir()
    (sandbox.root / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    files = sandbox.list_files(".")
    assert "app.py" in files
    assert not any(f.startswith(".git") for f in files)


def test_write_file_rejects_path_traversal(sandbox: Sandbox) -> None:
    with pytest.raises(SandboxPathError):
        sandbox.write_file("../../evil.py", "malicious = True\n")


def test_read_file_rejects_path_traversal(sandbox: Sandbox) -> None:
    with pytest.raises(SandboxPathError):
        sandbox.read_file("../outside.py")


def test_write_file_rejects_absolute_escape(sandbox: Sandbox, tmp_path: Path) -> None:
    escape_target = str(tmp_path / "outside.txt")
    with pytest.raises(SandboxPathError):
        sandbox.write_file(escape_target, "data")


def test_run_tests_reports_pass(sandbox: Sandbox) -> None:
    result = sandbox.run_tests()
    assert result.all_passed
    assert result.passed == 1
    assert result.failed == 0


def test_run_tests_reports_failure_details(tmp_path: Path) -> None:
    repo = tmp_path / "broken_repo"
    repo.mkdir()
    (repo / "app.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "test_app.py").write_text(
        "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    sb = Sandbox(run_id="broken-run", runs_dir=tmp_path / "runs")
    sb.setup_from_dir(repo)

    result = sb.run_tests()
    assert not result.all_passed
    assert result.failed == 1
    assert len(result.failing_tests) >= 1


def test_run_tests_enforces_timeout(tmp_path: Path) -> None:
    repo = tmp_path / "slow_repo"
    repo.mkdir()
    (repo / "test_slow.py").write_text(
        textwrap.dedent(
            """
            import time

            def test_slow():
                time.sleep(5)
                assert True
            """
        ),
        encoding="utf-8",
    )
    sb = Sandbox(run_id="slow-run", runs_dir=tmp_path / "runs", test_timeout_seconds=1)
    sb.setup_from_dir(repo)

    with pytest.raises(SandboxTimeoutError):
        sb.run_tests()


def test_operations_rejected_once_run_duration_exceeded(sandbox: Sandbox) -> None:
    sandbox.max_run_duration_seconds = 0
    import time

    time.sleep(0.01)
    with pytest.raises(SandboxRunDurationExceeded):
        sandbox.read_file("app.py")


def test_write_patch_rejects_invalid_python_syntax(sandbox: Sandbox) -> None:
    from agent.tools import execute_tool

    original_code = sandbox.read_file("app.py")
    result = execute_tool(
        sandbox,
        "write_patch",
        {"file_path": "app.py", "new_content": "def add(a, b):\n    return a + b}\n"},  # stray }
    )
    assert "error" in result
    assert "SyntaxError in app.py" in result["error"]
    # Verify file content was not overwritten
    assert sandbox.read_file("app.py") == original_code


def test_apply_diff_search_and_replace_block(sandbox: Sandbox) -> None:
    from agent.tools import execute_tool

    result = execute_tool(
        sandbox,
        "apply_diff",
        {
            "file_path": "app.py",
            "search_block": "return a + b",
            "replace_block": "return (a + b) * 1",
        },
    )
    assert result.get("status") == "diff_applied"
    assert "return (a + b) * 1" in sandbox.read_file("app.py")


def test_apply_diff_unified_diff(sandbox: Sandbox) -> None:
    from agent.tools import execute_tool

    diff_text = """@@ -1,2 +1,2 @@
 def add(a, b):
-    return a + b
+    return a + b + 10
"""
    result = execute_tool(
        sandbox,
        "apply_diff",
        {"file_path": "app.py", "diff": diff_text},
    )
    assert result.get("status") == "diff_applied"
    assert "+ 10" in sandbox.read_file("app.py")


def test_apply_diff_rejects_syntax_error(sandbox: Sandbox) -> None:
    from agent.tools import execute_tool

    original_code = sandbox.read_file("app.py")
    result = execute_tool(
        sandbox,
        "apply_diff",
        {
            "file_path": "app.py",
            "search_block": "return a + b",
            "replace_block": "return a + b ::: syntax error",
        },
    )
    assert "error" in result
    assert "SyntaxError in app.py" in result["error"]
    assert sandbox.read_file("app.py") == original_code

