"""Tool implementations exposed to the LLM via tool use.

Each function takes the active Sandbox plus the tool's input dict and
returns a JSON-serializable result. `TOOL_SCHEMAS` is a provider-agnostic
schema list (name, description, input_schema); agent/llm_client.py
converts it into the wire format the active LLM provider expects.
"""

from __future__ import annotations

import ast
import re
from typing import Any

from agent.sandbox import Sandbox, SandboxPathError, TestResult

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "read_file",
        "description": (
            "Read the full contents of a file in the sandboxed repo. "
            "Path is relative to the repo root."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file, e.g. 'src/utils.py'",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and directories under a given directory in the sandboxed repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Relative directory path, e.g. '.' for repo root.",
                    "default": ".",
                }
            },
        },
    },
    {
        "name": "search_codebase",
        "description": (
            "Grep-style substring search across all .py files in the sandboxed repo. "
            "Returns matching file, line number, and line text. Use this to locate a "
            "symbol or string without reading every file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Substring or symbol to search for."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "run_tests",
        "description": (
            "Run the pytest suite inside the sandboxed repo. Returns pass/fail counts, "
            "stdout/stderr, and the specific failing test names with tracebacks."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "write_patch",
        "description": (
            "Write a full replacement of a file's content inside the sandboxed repo. "
            "This overwrites the entire file - always include the complete new file "
            "contents. Syntax is automatically validated before saving."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to the file to write."},
                "new_content": {"type": "string", "description": "The full new contents of the file."},
            },
            "required": ["file_path", "new_content"],
        },
    },
    {
        "name": "apply_diff",
        "description": (
            "Apply a targeted change to a file inside the sandboxed repo without rewriting "
            "the entire file. Supply either `search_block` + `replace_block` (recommended for "
            "precision) or a unified `diff` with @@ hunk headers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to the file to modify."},
                "search_block": {
                    "type": "string",
                    "description": "Exact lines in the original file to be replaced.",
                },
                "replace_block": {
                    "type": "string",
                    "description": "Replacement lines for the search_block.",
                },
                "diff": {
                    "type": "string",
                    "description": "Standard unified diff containing @@ -start,count +start,count @@ hunks.",
                },
            },
            "required": ["file_path"],
        },
    },
]


def _validate_python_syntax(file_path: str, content: str) -> str | None:
    """Validate that Python code parses without syntax errors before writing to disk."""
    if file_path.endswith(".py"):
        try:
            ast.parse(content, filename=file_path)
        except SyntaxError as exc:
            return (
                f"SyntaxError in {file_path} on line {exc.lineno}: {exc.msg}. "
                "The patch was NOT applied. Fix this syntax error and try again."
            )
    return None


def _apply_unified_diff(original_text: str, diff_text: str) -> str:
    """Apply a unified diff containing standard @@ hunks to original_text."""
    original_lines = original_text.splitlines(keepends=True)
    diff_lines = diff_text.strip().splitlines()

    hunks = []
    current_hunk = None
    hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    for line in diff_lines:
        match = hunk_header_re.match(line)
        if match:
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) is not None else 1
            current_hunk = {"old_start": old_start, "old_count": old_count, "lines": []}
            hunks.append(current_hunk)
        elif current_hunk is not None:
            if line.startswith(("+", "-", " ", "\\")):
                current_hunk["lines"].append(line)

    if not hunks:
        raise ValueError("No valid @@ -start,count +start,count @@ hunks found in diff.")

    result_lines = list(original_lines)
    for hunk in reversed(hunks):
        old_start = max(0, hunk["old_start"] - 1)
        old_count = hunk["old_count"]

        new_hunk_lines = []
        for hline in hunk["lines"]:
            if hline.startswith("+"):
                new_hunk_lines.append(hline[1:] + ("\n" if not hline[1:].endswith("\n") else ""))
            elif hline.startswith(" "):
                new_hunk_lines.append(hline[1:] + ("\n" if not hline[1:].endswith("\n") else ""))

        result_lines[old_start : old_start + old_count] = new_hunk_lines

    return "".join(result_lines)


def _apply_patch(
    original_text: str,
    file_path: str,
    search_block: str | None,
    replace_block: str | None,
    diff: str | None,
) -> str:
    """Compute new file content using either search/replace blocks or unified diff."""
    if search_block is not None:
        norm_orig = original_text.replace("\r\n", "\n")
        norm_search = search_block.replace("\r\n", "\n")
        norm_replace = (replace_block or "").replace("\r\n", "\n")

        if norm_search not in norm_orig:
            raise ValueError(f"search_block was not found in {file_path}")
        if norm_orig.count(norm_search) > 1:
            raise ValueError(
                f"search_block matched multiple times in {file_path}. "
                "Include additional surrounding context lines to make it unique."
            )
        return norm_orig.replace(norm_search, norm_replace, 1)

    if diff is not None:
        return _apply_unified_diff(original_text, diff)

    raise ValueError("Must provide either search_block + replace_block or diff")


def _test_result_to_dict(result: TestResult) -> dict:
    return {
        "passed": result.passed,
        "failed": result.failed,
        "errors": result.errors,
        "skipped": result.skipped,
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 3),
        "failing_tests": result.failing_tests,
        "stdout_tail": "\n".join(result.stdout.splitlines()[-200:]),
        "stderr_tail": "\n".join(result.stderr.splitlines()[-100:]),
    }


def execute_tool(sandbox: Sandbox, tool_name: str, tool_input: dict[str, Any]) -> dict:
    """Dispatch a single tool call against the sandbox. Never raises for
    expected/user-facing errors (path traversal, missing file, syntax error) -
    instead returns {"error": "..."} so the LLM can see and react to it."""
    try:
        if tool_name == "read_file":
            content = sandbox.read_file(tool_input["path"])
            return {"content": content}

        if tool_name == "list_files":
            files = sandbox.list_files(tool_input.get("directory", "."))
            return {"files": files}

        if tool_name == "search_codebase":
            matches = sandbox.search_codebase(tool_input["query"])
            return {"matches": matches}

        if tool_name == "run_tests":
            result = sandbox.run_tests()
            return _test_result_to_dict(result)

        if tool_name == "write_patch":
            file_path = tool_input["file_path"]
            new_content = tool_input["new_content"]
            syntax_err = _validate_python_syntax(file_path, new_content)
            if syntax_err:
                return {"error": syntax_err}
            sandbox.write_file(file_path, new_content)
            return {"status": "written", "file_path": file_path}

        if tool_name == "apply_diff":
            file_path = tool_input["file_path"]
            original_content = sandbox.read_file(file_path)
            new_content = _apply_patch(
                original_text=original_content,
                file_path=file_path,
                search_block=tool_input.get("search_block"),
                replace_block=tool_input.get("replace_block"),
                diff=tool_input.get("diff"),
            )
            syntax_err = _validate_python_syntax(file_path, new_content)
            if syntax_err:
                return {"error": syntax_err}
            sandbox.write_file(file_path, new_content)
            return {"status": "diff_applied", "file_path": file_path}

        return {"error": f"unknown tool: {tool_name}"}

    except SandboxPathError as exc:
        return {"error": f"rejected: {exc}"}
    except FileNotFoundError as exc:
        return {"error": str(exc)}
    except NotADirectoryError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - surfaced to the LLM, not swallowed silently
        return {"error": f"{type(exc).__name__}: {exc}"}
