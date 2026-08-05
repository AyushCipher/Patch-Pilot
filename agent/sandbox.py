"""Isolated repo execution for the PatchPilot agent.

# MOCK - full Docker container isolation is a documented stretch goal;
# v1 isolation is directory-jailed subprocess execution with timeouts.
Every write is resolved against the sandbox root and rejected if it would
land outside it (path-traversal check). Test runs are wall-clock bounded
and the whole run additionally has a max total duration.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


class SandboxPathError(Exception):
    """Raised when a requested path resolves outside the sandbox root."""


class SandboxTimeoutError(Exception):
    """Raised when a test run exceeds its wall-clock timeout."""


class SandboxRunDurationExceeded(Exception):
    """Raised when the total run duration budget for a sandbox is exhausted."""


_FAILURE_LINE_RE = re.compile(r"^(FAILED|ERROR) (\S+)")
_SUMMARY_RE = re.compile(
    r"(\d+) passed|(\d+) failed|(\d+) error|(\d+) skipped"
)


@dataclass
class TestResult:
    passed: int
    failed: int
    errors: int
    skipped: int
    stdout: str
    stderr: str
    returncode: int
    duration_seconds: float
    failing_tests: list[dict] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.returncode == 0 and self.failed == 0 and self.errors == 0


class Sandbox:
    """A path-jailed working copy of a target repo used for one agent run."""

    def __init__(
        self,
        run_id: str,
        runs_dir: str | Path = "runs",
        test_timeout_seconds: int = 30,
        max_run_duration_seconds: int = 300,
    ) -> None:
        self.run_id = run_id
        self.root = (Path(runs_dir) / run_id / "sandbox").resolve()
        self.test_timeout_seconds = test_timeout_seconds
        self.max_run_duration_seconds = max_run_duration_seconds
        self._started_at = time.monotonic()

    # ------------------------------------------------------------------
    # setup
    # ------------------------------------------------------------------
    def setup_from_dir(self, source_dir: str | Path) -> None:
        """Copy a source repo/directory into the sandbox root."""
        source_dir = Path(source_dir).resolve()
        if not source_dir.exists():
            raise FileNotFoundError(f"source repo does not exist: {source_dir}")
        if self.root.exists():
            shutil.rmtree(self.root)
        shutil.copytree(source_dir, self.root)

    # ------------------------------------------------------------------
    # path jail
    # ------------------------------------------------------------------
    def _resolve(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise SandboxPathError(
                f"path '{relative_path}' resolves outside sandbox root"
            )
        return candidate

    def _check_duration_budget(self) -> None:
        elapsed = time.monotonic() - self._started_at
        if elapsed > self.max_run_duration_seconds:
            raise SandboxRunDurationExceeded(
                f"run exceeded max duration of {self.max_run_duration_seconds}s "
                f"(elapsed {elapsed:.1f}s)"
            )

    # ------------------------------------------------------------------
    # tool primitives
    # ------------------------------------------------------------------
    def read_file(self, relative_path: str) -> str:
        self._check_duration_budget()
        path = self._resolve(relative_path)
        if not path.is_file():
            raise FileNotFoundError(f"no such file: {relative_path}")
        return path.read_text(encoding="utf-8", errors="replace")

    def write_file(self, relative_path: str, content: str) -> None:
        self._check_duration_budget()
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def list_files(self, relative_directory: str = ".") -> list[str]:
        self._check_duration_budget()
        directory = self._resolve(relative_directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"no such directory: {relative_directory}")
        entries = []
        for p in sorted(directory.rglob("*")):
            if any(part in {".git", "__pycache__", ".pytest_cache"} for part in p.parts):
                continue
            entries.append(str(p.relative_to(self.root)).replace("\\", "/"))
        return entries

    def search_codebase(self, query: str, max_results: int = 50) -> list[dict]:
        """Simple grep-style text search across all .py files in the sandbox."""
        self._check_duration_budget()
        results = []
        for p in sorted(self.root.rglob("*.py")):
            if any(part in {".git", "__pycache__", ".pytest_cache"} for part in p.parts):
                continue
            try:
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, start=1):
                if query in line:
                    results.append(
                        {
                            "file": str(p.relative_to(self.root)).replace("\\", "/"),
                            "line": lineno,
                            "text": line.strip(),
                        }
                    )
                    if len(results) >= max_results:
                        return results
        return results

    def run_tests(self) -> TestResult:
        self._check_duration_budget()
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=self.test_timeout_seconds,
            )
            timed_out = False
            stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            returncode = -1
        duration = time.monotonic() - start

        if timed_out:
            raise SandboxTimeoutError(
                f"test run exceeded {self.test_timeout_seconds}s wall-clock timeout"
            )

        return self._parse_pytest_output(stdout, stderr, returncode, duration)

    @staticmethod
    def _parse_pytest_output(
        stdout: str, stderr: str, returncode: int, duration: float
    ) -> TestResult:
        passed = failed = errors = skipped = 0
        for match in _SUMMARY_RE.finditer(stdout):
            if match.group(1):
                passed = int(match.group(1))
            elif match.group(2):
                failed = int(match.group(2))
            elif match.group(3):
                errors = int(match.group(3))
            elif match.group(4):
                skipped = int(match.group(4))

        failing_tests: list[dict] = []
        current_name = None
        current_lines: list[str] = []
        in_failures_section = False
        for line in stdout.splitlines():
            if line.startswith("=") and "FAILURES" in line:
                in_failures_section = True
                continue
            if line.startswith("=") and "short test summary" in line.lower():
                in_failures_section = False
            if in_failures_section and line.startswith("_") and line.strip("_"):
                if current_name is not None:
                    failing_tests.append(
                        {"name": current_name, "traceback": "\n".join(current_lines).strip()}
                    )
                current_name = line.strip("_ ").strip()
                current_lines = []
            elif in_failures_section and current_name is not None:
                current_lines.append(line)
        if current_name is not None:
            failing_tests.append(
                {"name": current_name, "traceback": "\n".join(current_lines).strip()}
            )

        if not failing_tests:
            for match in _FAILURE_LINE_RE.finditer(stdout):
                failing_tests.append({"name": match.group(2), "traceback": ""})

        return TestResult(
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            duration_seconds=duration,
            failing_tests=failing_tests,
        )
