"""FastMCP Client adapter for the PatchPilot ReAct agent.

Dispatches agent tool calls over the Model Context Protocol (MCP) to a FastMCP server
rather than invoking internal Python functions directly.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import Client, FastMCP

from agent.mcp_server import create_mcp_server
from agent.sandbox import Sandbox, SandboxRunDurationExceeded


class MCPToolClient:
    """Client that communicates with a FastMCP tool server over the MCP protocol."""

    def __init__(self, sandbox_or_server: Sandbox | FastMCP | str) -> None:
        if isinstance(sandbox_or_server, Sandbox):
            self._server = create_mcp_server(sandbox_or_server)
        else:
            self._server = sandbox_or_server

    def call_tool(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool over MCP protocol and return the structured result."""
        async def _call() -> dict[str, Any]:
            async with Client(self._server) as client:
                try:
                    result = await client.call_tool(tool_name, tool_input)
                    if isinstance(result.data, dict):
                        return result.data
                    return {"result": result.data}
                except Exception as exc:
                    return {"error": f"MCP tool error: {exc}"}

        try:
            return asyncio.run(_call())
        except SandboxRunDurationExceeded:
            raise
        except Exception as exc:
            return {"error": f"MCP client dispatch failure: {exc}"}

    def list_tools(self) -> list[str]:
        """List available tools on the MCP server."""
        async def _list() -> list[str]:
            async with Client(self._server) as client:
                tools = await client.list_tools()
                return [t.name for t in tools]

        return asyncio.run(_list())
