"""AWS HTTP mcp for testings and stuff"""
from __future__ import annotations

import os
from typing import Any

from langchain_core.tools import BaseTool

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
except Exception:
    MultiServerMCPClient = None


class MCPService:
    def __init__(self) -> None:
        self._client: Any | None = None
        self._tools: list[BaseTool] | None = None

    def _server_config(self) -> dict[str, Any]:
        transport = os.getenv("MCP_TRANSPORT", "streamable_http")
        server_url = os.getenv("MCP_SERVER_URL", "").strip()
        server_name = os.getenv("MCP_SERVER_NAME", "app-mcp")

        if not server_url:
            raise ValueError("MCP_SERVER_URL is required")

        return {
            server_name: {
                "transport": transport,
                "url": server_url,
            }
        }

    async def get_client(self) -> Any:
        if MultiServerMCPClient is None:
            raise ImportError(
                "Install langchain-mcp-adapters to use MCP tools"
            )

        if self._client is None:
            self._client = MultiServerMCPClient(self._server_config())
        return self._client

    async def get_tools(self) -> list[BaseTool]:
        if self._tools is None:
            client = await self.get_client()
            self._tools = await client.get_tools()
        return self._tools

    async def refresh_tools(self) -> list[BaseTool]:
        self._tools = None
        return await self.get_tools()


mcpservice = MCPService()
