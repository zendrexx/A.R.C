import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from arc.service import ArcService


def test_new_agent_can_call_project_state_over_stdio(sample_repo, tmp_path):
    database = tmp_path / "arc.sqlite3"
    service = ArcService(database)
    try:
        service.register_project(sample_repo)
        task = service.add_task(sample_repo, "Finish the login flow")
    finally:
        service.close()

    async def round_trip():
        environment = os.environ.copy()
        environment["ARC_PROJECT"] = str(sample_repo)
        environment["ARC_DB"] = str(database)
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "arc.mcp_server"], env=environment,
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert "arc_get_project_state" in {tool.name for tool in tools.tools}
                assert "arc_get_event" in {tool.name for tool in tools.tools}
                result = await session.call_tool("arc_get_project_state", {})
                assert result.is_error is False
                assert task["id"] in str(result)

    asyncio.run(round_trip())
