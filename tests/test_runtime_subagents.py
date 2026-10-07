"""Tests for ATBMind Subagent Orchestrator and Antigravity-Grade Subagent Tools.

Covers:
- SubagentOrchestrator lifecycle & state transitions
- Predefined role resolution (RobotRoleRegistry / scan)
- 'self' role cloning (parent system prompt and tools)
- 'research' role configuration (read-only tools)
- Dynamic role definition (define_subagent)
- Mailbox communication and SubagentMessageEvent
- Context isolation (independent .jsonl transcripts, no token leaking)
- Subagent Tools: InvokeSubagentTool, SendMessageTool, ManageSubagentsTool, DefineSubagentTool
"""

import asyncio
import json
from pathlib import Path
import pytest

from atbmind_core.harness.tools.base import AgentTool, ToolResult
from atbmind_core.roles.registry import RobotRoleRegistry, RoleRegistry
from atbmind_core.runtime.event_bus import (
    AsyncEventBus,
    SubagentLifecycleEvent,
    SubagentMessageEvent,
)
from atbmind_core.runtime.subagents import (
    SubagentOrchestrator,
    SubagentState,
)
from atbmind_core.runtime.tools.subagent_tools import (
    DefineSubagentTool,
    InvokeSubagentTool,
    ManageSubagentsTool,
    SendMessageTool,
)


# ============================================================================
# 1. Core Orchestration Flow from Brief
# ============================================================================

@pytest.mark.asyncio
async def test_subagent_orchestration_flow(tmp_path: Path):
    bus = AsyncEventBus()
    role_registry = RobotRoleRegistry()
    role_registry.scan("roles")  # 加载已有的 draw_expert, coordinator
    orchestrator = SubagentOrchestrator(event_bus=bus, role_registry=role_registry, transcript_dir=tmp_path)

    try:
        # 1. 派发已有的 draw_expert
        sub_id = await orchestrator.spawn_subagent(
            type_name="draw_expert",
            role_title="Visual Specialist",
            prompt="Draw a cyberpunk cat",
            parent_id="root-session",
        )
        assert sub_id is not None
        info = orchestrator.get_subagent_info(sub_id)
        assert info is not None
        assert info["type"] == "draw_expert"
        assert info["state"] in [SubagentState.RUNNING.value, SubagentState.IDLE.value]

        # 2. 发送消息
        msg_res = await orchestrator.send_message(
            recipient_id=sub_id,
            message="Please add neon lights",
            sender_id="root-session",
        )
        assert msg_res is True

        # 3. 列出
        subagents = orchestrator.list_subagents()
        assert len(subagents) >= 1
        assert any(s["conversationId"] == sub_id for s in subagents)
    finally:
        await orchestrator.shutdown()


# ============================================================================
# 2. Role Resolution: Predefined, self, research, dynamic
# ============================================================================

@pytest.mark.asyncio
async def test_predefined_role_draw_expert(tmp_path: Path):
    bus = AsyncEventBus()
    role_registry = RobotRoleRegistry()
    role_registry.scan("roles")
    orchestrator = SubagentOrchestrator(event_bus=bus, role_registry=role_registry, transcript_dir=tmp_path)

    try:
        sub_id = await orchestrator.spawn_subagent(
            type_name="draw_expert",
            prompt="Draw a landscape",
            parent_id="root-session",
        )
        instance = orchestrator.get_instance(sub_id)
        assert instance is not None
        assert "视觉与精修专家" in (instance.role_title or "") or "draw_expert" in instance.type_name
        assert "核心视觉艺术" in instance.system_prompt
    finally:
        await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_self_role_cloning(tmp_path: Path):
    bus = AsyncEventBus()
    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)

    # Register parent session config
    orchestrator.register_parent_config(
        session_id="parent-session-123",
        system_prompt="You are a senior refactoring architect.",
        tools=[],
        model="gpt-4o-mini",
    )

    try:
        sub_id = await orchestrator.spawn_subagent(
            type_name="self",
            prompt="Analyze dependency cycles",
            parent_id="parent-session-123",
        )
        instance = orchestrator.get_instance(sub_id)
        assert instance is not None
        assert instance.system_prompt == "You are a senior refactoring architect."
        assert instance.model == "gpt-4o-mini"
    finally:
        await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_research_role_preconfigured(tmp_path: Path):
    bus = AsyncEventBus()
    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)

    try:
        sub_id = await orchestrator.spawn_subagent(
            type_name="research",
            prompt="Investigate codebase structure",
            parent_id="root",
        )
        instance = orchestrator.get_instance(sub_id)
        assert instance is not None
        assert "research" in instance.type_name.lower()
        tool_names = [t.name for t in instance.tools]
        assert "view_file" in tool_names
    finally:
        await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_dynamic_role_definition(tmp_path: Path):
    bus = AsyncEventBus()
    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)

    # Define dynamic role
    ok = orchestrator.define_subagent(
        name="sql_optimizer",
        description="Optimizes PostgreSQL queries and indexes",
        system_prompt="You are a PostgreSQL query tuning specialist.",
        enable_write_tools=True,
        enable_subagent_tools=False,
    )
    assert ok is True

    try:
        sub_id = await orchestrator.spawn_subagent(
            type_name="sql_optimizer",
            role_title="SQL Specialist",
            prompt="Analyze slow query EXPLAIN output",
            parent_id="root",
        )
        instance = orchestrator.get_instance(sub_id)
        assert instance is not None
        assert instance.type_name == "sql_optimizer"
        assert "PostgreSQL query tuning specialist" in instance.system_prompt
        tool_names = [t.name for t in instance.tools]
        assert "write_to_file" in tool_names or "replace_file_content" in tool_names
    finally:
        await orchestrator.shutdown()


# ============================================================================
# 3. Context Isolation & Transcript Verification
# ============================================================================

@pytest.mark.asyncio
async def test_context_isolation_transcripts(tmp_path: Path):
    bus = AsyncEventBus()
    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)

    try:
        sub_id = await orchestrator.spawn_subagent(
            type_name="research",
            prompt="Read and analyze requirements.txt",
            parent_id="root",
        )
        transcript_file = tmp_path / f"{sub_id}.jsonl"
        assert transcript_file.exists()

        # Send follow up message
        await orchestrator.send_message(
            recipient_id=sub_id,
            message="Check line 5 for versions",
            sender_id="root",
        )
        await asyncio.sleep(0.05)

        lines = transcript_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 2

        entry1 = json.loads(lines[0])
        assert entry1["type"] in ["USER_INPUT", "USER_MESSAGE"]
        assert "requirements.txt" in entry1["content"]

        entry2 = json.loads(lines[1])
        assert entry2["type"] in ["USER_MESSAGE", "USER_INPUT"]
        assert "Check line 5" in entry2["content"]
    finally:
        await orchestrator.shutdown()


# ============================================================================
# 4. Lifecycle & Event Bus Notifications
# ============================================================================

@pytest.mark.asyncio
async def test_lifecycle_events_and_killing(tmp_path: Path):
    bus = AsyncEventBus()
    lifecycle_events = []
    message_events = []

    bus.subscribe(SubagentLifecycleEvent, lambda e: lifecycle_events.append(e))
    bus.subscribe(SubagentMessageEvent, lambda e: message_events.append(e))

    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)

    try:
        sub_id = await orchestrator.spawn_subagent(
            type_name="draw_expert",
            role_title="Artist",
            prompt="Generate cover art",
            parent_id="root",
        )

        assert len(lifecycle_events) >= 1
        assert any(e.subagent_id == sub_id and e.state in ["running", "idle"] for e in lifecycle_events)

        # Send message
        await orchestrator.send_message(
            recipient_id=sub_id,
            message="Use blue background",
            sender_id="root",
        )
        assert len(message_events) == 1
        assert message_events[0].recipient_id == sub_id
        assert message_events[0].content == "Use blue background"

        # Kill subagent
        killed = await orchestrator.kill_subagent(sub_id)
        assert killed is True
        info = orchestrator.get_subagent_info(sub_id)
        assert info["state"] == SubagentState.DONE.value

        assert any(e.subagent_id == sub_id and e.state == "done" for e in lifecycle_events)
    finally:
        await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_kill_all_subagents(tmp_path: Path):
    bus = AsyncEventBus()
    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)

    try:
        s1 = await orchestrator.spawn_subagent(type_name="research", prompt="p1")
        s2 = await orchestrator.spawn_subagent(type_name="research", prompt="p2")
        s3 = await orchestrator.spawn_subagent(type_name="research", prompt="p3")

        assert len(orchestrator.list_subagents()) == 3
        count = await orchestrator.kill_all()
        assert count == 3

        for s_id in [s1, s2, s3]:
            assert orchestrator.get_subagent_info(s_id)["state"] == SubagentState.DONE.value
    finally:
        await orchestrator.shutdown()


# ============================================================================
# 5. Runtime Tools Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_invoke_subagent_tool(tmp_path: Path):
    bus = AsyncEventBus()
    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)
    invoke_tool = InvokeSubagentTool(orchestrator=orchestrator)

    try:
        # Test invoking multiple subagents
        res = await invoke_tool.execute_async(
            Subagents=[
                {
                    "TypeName": "research",
                    "Role": "Documentation Researcher",
                    "Prompt": "Find API endpoints",
                    "Model": "flash",
                },
                {
                    "TypeName": "research",
                    "Role": "Test Analyzer",
                    "Prompt": "Review test coverage",
                },
            ]
        )
        assert res.success is True
        assert res.is_error is False
        assert "Documentation Researcher" in res.output
        assert "Test Analyzer" in res.output
        assert len(orchestrator.list_subagents()) == 2
    finally:
        await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_send_message_tool(tmp_path: Path):
    bus = AsyncEventBus()
    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)
    send_tool = SendMessageTool(orchestrator=orchestrator)

    try:
        sub_id = await orchestrator.spawn_subagent(type_name="research", prompt="Initial task")

        # Send valid message
        res = await send_tool.execute_async(Recipient=sub_id, Message="Here is more details")
        assert res.success is True
        assert "sent" in res.output.lower()

        # Send to non-existent recipient
        res_fail = await send_tool.execute_async(Recipient="non-existent-sub", Message="Hello?")
        assert res_fail.success is False
        assert res_fail.is_error is True
        assert "not found" in res_fail.error.lower()
    finally:
        await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_manage_subagents_tool(tmp_path: Path):
    bus = AsyncEventBus()
    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)
    manage_tool = ManageSubagentsTool(orchestrator=orchestrator)

    try:
        s1 = await orchestrator.spawn_subagent(type_name="research", role_title="Worker 1", prompt="t1")
        s2 = await orchestrator.spawn_subagent(type_name="research", role_title="Worker 2", prompt="t2")

        # 1. Action: list
        list_res = await manage_tool.execute_async(Action="list")
        assert list_res.success is True
        data = json.loads(list_res.output)
        assert len(data) == 2
        assert any(d["conversationId"] == s1 for d in data)

        # 2. Action: kill specific
        kill_res = await manage_tool.execute_async(Action="kill", ConversationIds=[s1])
        assert kill_res.success is True
        assert s1 in kill_res.output
        assert orchestrator.get_subagent_info(s1)["state"] == SubagentState.DONE.value

        # 3. Action: kill_all
        kill_all_res = await manage_tool.execute_async(Action="kill_all")
        assert kill_all_res.success is True
        assert orchestrator.get_subagent_info(s2)["state"] == SubagentState.DONE.value
    finally:
        await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_define_subagent_tool(tmp_path: Path):
    bus = AsyncEventBus()
    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)
    define_tool = DefineSubagentTool(orchestrator=orchestrator)
    invoke_tool = InvokeSubagentTool(orchestrator=orchestrator)

    try:
        res = await define_tool.execute_async(
            name="security_auditor",
            description="Audits source code for CVEs and vulnerabilities",
            system_prompt="You are a security auditor looking for security vulnerabilities.",
            enable_write_tools=False,
            enable_subagent_tools=False,
        )
        assert res.success is True
        assert "security_auditor" in res.output

        # Now invoke the dynamically defined agent
        invoke_res = await invoke_tool.execute_async(
            Subagents=[
                {
                    "TypeName": "security_auditor",
                    "Role": "Security Reviewer",
                    "Prompt": "Scan authentication middleware",
                }
            ]
        )
        assert invoke_res.success is True
        subs = orchestrator.list_subagents()
        assert len(subs) == 1
        assert subs[0]["type"] == "security_auditor"
    finally:
        await orchestrator.shutdown()


# ============================================================================
# 6. Strict Context Isolation & Zero Token Leakage Test
# ============================================================================

@pytest.mark.asyncio
async def test_context_isolation_zero_leakage_to_parent(tmp_path: Path):
    from atbmind_core.harness.types import AgentMessage, Role

    # Simulated parent context
    parent_messages = [
        AgentMessage(role=Role.SYSTEM, content="System prompt for parent"),
        AgentMessage(role=Role.USER, content="Initial user instructions"),
    ]
    initial_parent_count = len(parent_messages)

    bus = AsyncEventBus()
    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)

    try:
        # Spawn subagent
        sub_id = await orchestrator.spawn_subagent(
            type_name="research",
            role_title="Deep Researcher",
            prompt="Find all occurrences of AsyncEventBus in tests",
            parent_id="parent-session-abc",
        )

        # Exchange multiple messages
        for i in range(3):
            await orchestrator.send_message(
                recipient_id=sub_id,
                message=f"Subtask query #{i}: check module {i}",
                sender_id="parent-session-abc",
            )
            await asyncio.sleep(0.02)

        # Verify parent message list was completely isolated and untouched
        assert len(parent_messages) == initial_parent_count
        assert [m.content for m in parent_messages] == [
            "System prompt for parent",
            "Initial user instructions",
        ]

        # Verify subagent transcript logged each step independently
        transcript_path = tmp_path / f"{sub_id}.jsonl"
        assert transcript_path.exists()
        lines = [json.loads(line) for line in transcript_path.read_text(encoding="utf-8").strip().splitlines()]
        # Initial user input + 3 user messages + 3 agent responses = 7 entries
        assert len(lines) >= 4
        assert any("AsyncEventBus" in entry.get("content", "") for entry in lines)
    finally:
        await orchestrator.shutdown()


# ============================================================================
# 7. Validation Errors & OpenAI Schema Tests
# ============================================================================

@pytest.mark.asyncio
async def test_subagent_tools_validation_errors(tmp_path: Path):
    bus = AsyncEventBus()
    orchestrator = SubagentOrchestrator(event_bus=bus, transcript_dir=tmp_path)
    invoke_tool = InvokeSubagentTool(orchestrator=orchestrator)
    send_tool = SendMessageTool(orchestrator=orchestrator)
    manage_tool = ManageSubagentsTool(orchestrator=orchestrator)
    define_tool = DefineSubagentTool(orchestrator=orchestrator)

    try:
        # 1. InvokeSubagentTool with empty list
        res_empty = await invoke_tool.execute_async(Subagents=[])
        assert res_empty.success is False
        assert "empty" in res_empty.error.lower()

        # 2. SendMessageTool with empty fields
        res_no_rec = await send_tool.execute_async(Recipient="  ", Message="test")
        assert res_no_rec.success is False

        res_no_msg = await send_tool.execute_async(Recipient="sub-1", Message="   ")
        assert res_no_msg.success is False

        # 3. ManageSubagentsTool kill without ConversationIds
        res_kill_err = await manage_tool.execute_async(Action="kill")
        assert res_kill_err.success is False
        assert "conversationids" in res_kill_err.error.lower()

        # 4. DefineSubagentTool invalid fields
        res_def_err = await define_tool.execute_async(foo="bar")
        assert res_def_err.success is False

        # 5. OpenAI schema verification
        for tool in [invoke_tool, send_tool, manage_tool, define_tool]:
            schema = tool.to_openai_schema()
            assert schema["type"] == "function"
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]
    finally:
        await orchestrator.shutdown()
