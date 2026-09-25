import sys
from pathlib import Path

import pytest
from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.mcp_server import create_mcp_server
from agent.sandbox import Sandbox
from agent.tools import execute_tool


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def test_sandbox(tmp_path: Path) -> Sandbox:
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
    sb = Sandbox(run_id="mcp-test-run", runs_dir=tmp_path / "runs")
    sb.setup_from_dir(repo)
    return sb


@pytest.mark.anyio
async def test_mcp_server_lists_tools(test_sandbox: Sandbox) -> None:
    server = create_mcp_server(test_sandbox)
    async with Client(server) as client:
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        expected_tools = {
            "validate_syntax",
            "read_file",
            "list_files",
            "search_codebase",
            "run_tests",
            "write_patch",
            "apply_diff",
        }
        assert expected_tools.issubset(tool_names)


@pytest.mark.anyio
async def test_mcp_server_validate_syntax(test_sandbox: Sandbox) -> None:
    server = create_mcp_server(test_sandbox)
    async with Client(server) as client:
        # Valid code
        valid_res = await client.call_tool("validate_syntax", {"code": "x = 1\n", "file_path": "test.py"})
        assert valid_res.data == {"valid": True, "error": None}

        # Invalid syntax
        invalid_res = await client.call_tool("validate_syntax", {"code": "def foo():\n    return 1}\n", "file_path": "test.py"})
        assert invalid_res.data["valid"] is False
        assert "SyntaxError" in invalid_res.data["error"]


@pytest.mark.anyio
async def test_mcp_server_tool_parity_with_direct_execution(test_sandbox: Sandbox) -> None:
    server = create_mcp_server(test_sandbox)
    async with Client(server) as client:
        # 1. read_file
        mcp_read = await client.call_tool("read_file", {"path": "mathutils.py"})
        direct_read = execute_tool(test_sandbox, "read_file", {"path": "mathutils.py"})
        assert mcp_read.data == direct_read

        # 2. list_files
        mcp_list = await client.call_tool("list_files", {"directory": "."})
        direct_list = execute_tool(test_sandbox, "list_files", {"directory": "."})
        assert mcp_list.data == direct_list

        # 3. search_codebase
        mcp_search = await client.call_tool("search_codebase", {"query": "sum_first_n"})
        direct_search = execute_tool(test_sandbox, "search_codebase", {"query": "sum_first_n"})
        assert mcp_search.data == direct_search

        # 4. run_tests (initially failing)
        mcp_tests = await client.call_tool("run_tests", {})
        direct_tests = execute_tool(test_sandbox, "run_tests", {})
        assert mcp_tests.data["passed"] == direct_tests["passed"]
        assert mcp_tests.data["failed"] == direct_tests["failed"]
        assert mcp_tests.data["failed"] == 1

        # 5. write_patch with invalid syntax -> rejected
        mcp_bad_patch = await client.call_tool(
            "write_patch",
            {"file_path": "mathutils.py", "new_content": "def broken():\n    return 0}\n"}
        )
        assert "error" in mcp_bad_patch.data
        assert "SyntaxError" in mcp_bad_patch.data["error"]

        # 6. apply_diff fixing the bug
        mcp_diff = await client.call_tool(
            "apply_diff",
            {
                "file_path": "mathutils.py",
                "search_block": "range(1, n)",
                "replace_block": "range(1, n + 1)",
            }
        )
        assert mcp_diff.data == {"status": "diff_applied", "file_path": "mathutils.py"}

        # 7. run_tests again (now passing)
        mcp_passed_tests = await client.call_tool("run_tests", {})
        assert mcp_passed_tests.data["passed"] == 1
        assert mcp_passed_tests.data["failed"] == 0
