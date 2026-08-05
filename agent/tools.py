"""Tool implementations exposed to the LLM via Anthropic tool-use.

Each function takes the active Sandbox plus the tool's input dict and
returns a JSON-serializable result. `TOOL_SCHEMAS` is the Anthropic
`tools=[...]` schema list passed to the Messages API.
"""

from __future__ import annotations

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
            "contents, not a diff or partial snippet."
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
]


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
    expected/user-facing errors (path traversal, missing file, timeout) -
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
            sandbox.write_file(tool_input["file_path"], tool_input["new_content"])
            return {"status": "written", "file_path": tool_input["file_path"]}

        return {"error": f"unknown tool: {tool_name}"}

    except SandboxPathError as exc:
        return {"error": f"rejected: {exc}"}
    except FileNotFoundError as exc:
        return {"error": str(exc)}
    except NotADirectoryError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - surfaced to the LLM, not swallowed silently
        return {"error": f"{type(exc).__name__}: {exc}"}
