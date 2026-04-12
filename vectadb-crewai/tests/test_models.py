"""Tests for VectaDB data models."""

from datetime import datetime, timezone

import pytest

from vectadb_crewai.models import (
    AgentRunState,
    BulkIngestionOptions,
    BulkIngestionRequest,
    CrewEventType,
    CrewRunState,
    VectaDBEvent,
    VectaDBSource,
)


class TestVectaDBEvent:
    def test_default_timestamp(self):
        event = VectaDBEvent(properties={"x": 1})
        assert event.timestamp is not None
        assert event.timestamp.tzinfo is not None

    def test_to_api_dict_minimal(self):
        event = VectaDBEvent(properties={"msg": "hello"})
        d = event.to_api_dict()
        assert "timestamp" in d
        assert d["properties"] == {"msg": "hello"}
        # Optional fields absent when None
        assert "trace_id" not in d
        assert "agent_id" not in d

    def test_to_api_dict_full(self):
        event = VectaDBEvent(
            trace_id="t1",
            event_type=CrewEventType.TOOL_START.value,
            agent_id="agent-xyz",
            session_id="sess-001",
            properties={"tool_name": "search"},
            source=VectaDBSource(log_id="evt-1"),
        )
        d = event.to_api_dict()
        assert d["trace_id"] == "t1"
        assert d["event_type"] == "tool_start"
        assert d["agent_id"] == "agent-xyz"
        assert d["session_id"] == "sess-001"
        assert d["properties"]["tool_name"] == "search"
        assert d["source"]["system"] == "crewai"

    def test_crew_event_type_values(self):
        assert CrewEventType.CREW_START.value == "crew_start"
        assert CrewEventType.LLM_END.value == "llm_end"
        assert CrewEventType.TOOL_ERROR.value == "tool_error"


class TestBulkIngestionRequest:
    def test_to_api_dict(self):
        events = [
            VectaDBEvent(properties={"i": 0}),
            VectaDBEvent(properties={"i": 1}),
        ]
        req = BulkIngestionRequest(events=events)
        d = req.to_api_dict()
        assert len(d["events"]) == 2
        assert d["options"]["auto_create_traces"] is True
        assert d["options"]["generate_embeddings"] is True

    def test_custom_options(self):
        req = BulkIngestionRequest(
            events=[VectaDBEvent(properties={})],
            options=BulkIngestionOptions(
                auto_create_traces=False,
                generate_embeddings=False,
                extract_relationships=True,
            ),
        )
        d = req.to_api_dict()
        assert d["options"]["auto_create_traces"] is False
        assert d["options"]["extract_relationships"] is True


class TestRunState:
    def test_agent_run_state_creation(self):
        state = AgentRunState(
            agent_id="agent-001",
            role="researcher",
            session_id="sess-abc",
            trace_id="trace-xyz",
        )
        assert state.agent_id == "agent-001"
        assert state.tool_call_count == 0
        assert state.llm_call_count == 0
        assert state.action_sequence == 0

    def test_crew_run_state(self):
        state = CrewRunState(session_id="sess-001", crew_name="test_crew")
        assert state.session_id == "sess-001"
        assert state.agents == {}
        assert state.task_trace_map == {}
