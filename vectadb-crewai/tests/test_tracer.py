"""
Tests for VectaDBTracer — focusing on task lifecycle tracing
(task_start / task_end event coverage) and the _wrap_task_execute patch.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vectadb_crewai.models import CrewEventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(description: str = "Analyse the data", agent_role: str = "analyst") -> MagicMock:
    """Return a minimal Task mock with a working execute_sync."""
    task = MagicMock()
    task.description = description
    task.expected_output = "A detailed report"
    task.agent = MagicMock()
    task.agent.role = agent_role
    task._original_called = False

    def original_execute(*args, **kwargs):
        task._original_called = True
        return "task_result"

    task.execute_sync = original_execute
    return task


def _make_agent(role: str = "researcher") -> MagicMock:
    agent = MagicMock()
    agent.role = role
    agent.goal = "Do research"
    agent.backstory = "Expert"
    agent.tools = []
    agent.callbacks = []
    agent.llm = "gpt-4"
    return agent


def _make_crew(agents=None, tasks=None) -> MagicMock:
    crew = MagicMock()
    crew.agents = agents or [_make_agent()]
    crew.tasks = tasks or [_make_task()]
    crew.step_callback = None
    crew.task_callback = None
    return crew


# ---------------------------------------------------------------------------
# _wrap_task_execute tests
# ---------------------------------------------------------------------------

class TestWrapTaskExecute:
    """Unit tests for VectaDBTracer._wrap_task_execute."""

    @pytest.fixture
    def tracer(self):
        """A VectaDBTracer instance with a mocked SyncVectaDBClient."""
        from vectadb_crewai.tracer import VectaDBTracer

        with patch("vectadb_crewai.tracer.SyncVectaDBClient"):
            t = VectaDBTracer(vectadb_url="http://localhost:8080", fail_silently=True)
        t._session_id = "sess-wrap-test"
        return t

    def test_task_start_event_emitted(self, tracer):
        """Wrapping a task emits a task_start event when execute_sync is called."""
        ingested = []
        tracer._ingest_event = ingested.append

        task = _make_task(description="Analyse Q1 data", agent_role="analyst")
        tracer._wrap_task_execute(task, task_idx=0)

        task.execute_sync()

        assert len(ingested) == 1
        ev = ingested[0]
        assert ev.event_type == CrewEventType.TASK_START.value
        assert ev.properties["task_index"] == 0
        assert "Analyse Q1 data" in ev.properties["description"]
        assert ev.properties["agent_role"] == "analyst"
        assert ev.session_id == "sess-wrap-test"

    def test_original_execute_still_called(self, tracer):
        """The original execute_sync must still be invoked after patching."""
        tracer._ingest_event = lambda e: None

        task = _make_task()
        original_fn = task.execute_sync
        tracer._wrap_task_execute(task, task_idx=0)

        result = task.execute_sync("positional_arg", kw="value")

        assert task._original_called is True
        assert result == "task_result"

    def test_task_start_includes_expected_output(self, tracer):
        ingested = []
        tracer._ingest_event = ingested.append

        task = _make_task()
        task.expected_output = "Anomaly list with severity ratings"
        tracer._wrap_task_execute(task, task_idx=2)
        task.execute_sync()

        ev = ingested[0]
        assert "Anomaly list" in ev.properties["expected_output"]

    def test_task_idx_propagated_correctly(self, tracer):
        ingested = []
        tracer._ingest_event = ingested.append

        for idx in range(3):
            task = _make_task(description=f"Task {idx}")
            tracer._wrap_task_execute(task, task_idx=idx)
            task.execute_sync()

        indices = [e.properties["task_index"] for e in ingested]
        assert indices == [0, 1, 2]

    def test_no_patch_when_execute_sync_missing(self, tracer):
        """Tasks without execute_sync (future API changes) are skipped gracefully."""
        tracer._ingest_event = lambda e: None

        task = MagicMock(spec=[])           # no attributes at all
        del task.execute_sync               # ensure it's absent
        task = MagicMock()
        del task.execute_sync

        # Should not raise
        tracer._wrap_task_execute(task, task_idx=0)

    def test_event_emission_failure_does_not_crash_task(self, tracer):
        """If _ingest_event raises, the original task must still run."""
        def exploding_ingest(event):
            raise RuntimeError("VectaDB is down")

        tracer._ingest_event = exploding_ingest

        task = _make_task()
        tracer._wrap_task_execute(task, task_idx=0)

        result = task.execute_sync()        # must not raise
        assert result == "task_result"
        assert task._original_called is True


# ---------------------------------------------------------------------------
# Integration: _begin_run wraps all tasks
# ---------------------------------------------------------------------------

class TestBeginRunWrapsAllTasks:
    """Verify that _begin_run patches every task in the crew."""

    @pytest.fixture
    def tracer_with_mock_client(self):
        from vectadb_crewai.tracer import VectaDBTracer

        with patch("vectadb_crewai.tracer.SyncVectaDBClient"):
            return VectaDBTracer(vectadb_url="http://localhost:8080", fail_silently=True)

    def test_all_tasks_have_wrapped_execute(self, tracer_with_mock_client):
        """After _begin_run, every task.execute_sync should be the wrapped version."""
        tracer = tracer_with_mock_client
        ingested = []
        tracer._ingest_event = ingested.append

        tasks = [_make_task(description=f"Task {i}") for i in range(3)]
        original_fns = [t.execute_sync for t in tasks]  # capture before wrapping

        crew = _make_crew(tasks=tasks)
        tracer._begin_run(crew)

        # Each task.execute_sync should now be a different callable (the wrapper)
        for i, task in enumerate(tasks):
            assert task.execute_sync is not original_fns[i], (
                f"Task {i} execute_sync was not replaced by _begin_run"
            )

    def test_task_start_events_fired_for_each_task(self, tracer_with_mock_client):
        tracer = tracer_with_mock_client
        ingested = []
        tracer._ingest_event = ingested.append

        tasks = [_make_task(description=f"Step {i}") for i in range(2)]
        crew = _make_crew(tasks=tasks)
        tracer._begin_run(crew)

        # Clear crew_start / agent_start events that fire in _begin_run
        ingested.clear()

        # Simulate each task running
        for task in tasks:
            task.execute_sync()

        task_start_events = [
            e for e in ingested if e.event_type == CrewEventType.TASK_START.value
        ]
        assert len(task_start_events) == 2
        descriptions = {e.properties["description"] for e in task_start_events}
        assert "Step 0" in descriptions
        assert "Step 1" in descriptions
