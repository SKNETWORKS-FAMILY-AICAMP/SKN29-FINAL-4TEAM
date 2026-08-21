"""Actual stdio MCP Server registration smoke test."""

import asyncio

from ai.app.integrations.mcp.client import WaterBridgeMCPClient


def test_stdio_server_lists_context_and_evidence_tools():
    async def execute():
        async with WaterBridgeMCPClient() as client:
            return await client.list_tools()

    result = asyncio.run(execute())
    names = {tool.name for tool in result.tools}

    assert names == {
        "health_check",
        "warmup_search_runtime",
        "lookup_product_context",
        "get_inquiry_context",
        "search_official_evidence",
    }
