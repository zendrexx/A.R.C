import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from arc.service import ArcService
from arc.observer import control, poll


def test_new_agent_can_call_project_state_over_stdio(sample_repo, tmp_path):
    database = tmp_path / "arc.sqlite3"
    service = ArcService(database)
    try:
        service.register_project(sample_repo)
        task = service.add_task(sample_repo, "Finish the login flow")
        work_session = service.start_session(sample_repo, "Login work")
        evidence = service.record_note(sample_repo, "note", "Started login work")
        control(service, sample_repo, 'enable')
        (sample_repo / 'app.py').write_text('print("observed")\n')
        observed = poll(service, sample_repo)[0]
        decision = service.record_note(sample_repo, "decision", "Keep sessions in SQLite", task["id"])
        error = service.record_note(sample_repo, "error", "SQLite migration failed: users table missing")
        incident = service.open_incident(sample_repo, error["id"], "users table absent")

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
                assert "arc_get_session_history" in {tool.name for tool in tools.tools}
                assert 'arc_get_timeline' in {tool.name for tool in tools.tools}
                assert "arc_get_task_review" in {tool.name for tool in tools.tools}
                assert "arc_get_project_handoff" in {tool.name for tool in tools.tools}
                assert "arc_get_incident" in {tool.name for tool in tools.tools}
                assert "arc_list_incidents" in {tool.name for tool in tools.tools}
                assert "arc_search_incidents" in {tool.name for tool in tools.tools}

                result = await session.call_tool("arc_get_project_state", {})
                assert result.is_error is False
                assert task["id"] in str(result)
                history = await session.call_tool(
                    "arc_get_session_history", {"session_id": work_session["id"]}
                )
                assert history.is_error is False
                assert evidence["id"] in str(history)
                handoff = await session.call_tool("arc_get_project_handoff", {})
                assert handoff.is_error is False
                assert task["id"] in str(handoff)
                assert decision["source_ref"] in str(handoff)
                review = await session.call_tool(
                    "arc_get_task_review", {"task_id": task["id"]}
                )
                assert review.is_error is False
                assert "current_passing_test" in str(review)
                searched = await session.call_tool(
                    "arc_search_memory",
                    {"query": "login", "kind": "note", "keyword_only": True},
                )
                assert searched.is_error is False
                assert evidence["id"] in str(searched)
                timeline = await session.call_tool('arc_get_timeline', {'kind': 'git'})
                assert timeline.is_error is False
                assert observed['id'] in str(timeline)
                inspected = await session.call_tool('arc_get_event', {'event_id': observed['id']})
                assert inspected.is_error is False
                assert observed['id'] in str(inspected)

                incident_result = await session.call_tool(
                    "arc_get_incident", {"incident_id": incident["id"]}
                )
                assert incident_result.is_error is False
                assert error["source_ref"] in str(incident_result)
                incident_list = await session.call_tool("arc_list_incidents", {})
                assert incident_list.is_error is False
                assert incident["id"] in str(incident_list)
                incident_search = await session.call_tool(
                    "arc_search_incidents", {"query": "SQLite migration users table"}
                )
                assert incident_search.is_error is False
                assert incident["id"] in str(incident_search)


    asyncio.run(round_trip())
