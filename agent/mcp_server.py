"""FastMCP Server exposing PatchPilot's core tool capabilities over MCP.

Exposes:
1. Sandboxed code execution (read_file, list_files, search_codebase, run_tests)
2. AST syntax pre-validation (validate_syntax, and built into patch writers)
3. Search-and-replace hunk patching and full-file patching (apply_diff, write_patch)

Can be run standalone via stdio transport (local dev) or imported and connected
via FastMCP client in-process or over HTTP/SSE for production multi-tenant setups.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastmcp import FastMCP

from agent.sandbox import Sandbox
from agent.tools import (
    _apply_patch,
    _test_result_to_dict,
    _validate_python_syntax,
    execute_tool,
)


def create_mcp_server(
    sandbox: Sandbox | None = None,
    name: str = "PatchPilot-Tools",
) -> FastMCP:
    """Create and configure a FastMCP server bound to a Sandbox instance."""
    mcp = FastMCP(name)
    active_sandbox = sandbox or Sandbox(run_id="mcp_default", runs_dir="runs")

    @mcp.tool()
    def validate_syntax(code: str, file_path: str = "app.py") -> dict[str, Any]:
        """Validate that Python code parses without syntax errors before writing to disk."""
        error = _validate_python_syntax(file_path, code)
        if error:
            return {"valid": False, "error": error}
        return {"valid": True, "error": None}

    @mcp.tool()
    def read_file(path: str) -> dict[str, Any]:
        """Read the full contents of a file in the sandboxed repo. Path is relative to repo root."""
        return execute_tool(active_sandbox, "read_file", {"path": path})

    @mcp.tool()
    def list_files(directory: str = ".") -> dict[str, Any]:
        """List files and directories under a given directory in the sandboxed repo."""
        return execute_tool(active_sandbox, "list_files", {"directory": directory})

    @mcp.tool()
    def search_codebase(query: str) -> dict[str, Any]:
        """Grep-style substring search across all .py files in the sandboxed repo."""
        return execute_tool(active_sandbox, "search_codebase", {"query": query})

    @mcp.tool()
    def run_tests() -> dict[str, Any]:
        """Run the pytest suite inside the sandboxed repo. Returns pass/fail counts and tracebacks."""
        return execute_tool(active_sandbox, "run_tests", {})

    @mcp.tool()
    def write_patch(file_path: str, new_content: str) -> dict[str, Any]:
        """Write a full replacement of a file's content inside the sandboxed repo with AST validation."""
        return execute_tool(active_sandbox, "write_patch", {"file_path": file_path, "new_content": new_content})

    @mcp.tool()
    def apply_diff(
        file_path: str,
        search_block: Optional[str] = None,
        replace_block: Optional[str] = None,
        diff: Optional[str] = None,
    ) -> dict[str, Any]:
        """Apply a targeted change to a file using search_block + replace_block or a unified diff."""
        return execute_tool(
            active_sandbox,
            "apply_diff",
            {
                "file_path": file_path,
                "search_block": search_block,
                "replace_block": replace_block,
                "diff": diff,
            },
        )

    return mcp


# Standalone FastMCP server instance for stdio/SSE CLI execution
mcp_server = create_mcp_server()


if __name__ == "__main__":
    # Standard I/O transport for local development
    mcp_server.run()
