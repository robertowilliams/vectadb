"""
vectadb-crewai: VectaDB audit and observability integration for CrewAI.

Quickstart::

    from crewai import Agent, Crew, Task
    from vectadb_crewai import VectaDBTracer

    # Define your crew normally
    researcher = Agent(role="Researcher", goal="...", backstory="...")
    task = Task(description="...", agent=researcher)
    crew = Crew(agents=[researcher], tasks=[task])

    # Wrap kickoff with the tracer
    tracer = VectaDBTracer(vectadb_url="http://localhost:8080")
    result = tracer.kickoff(crew, inputs={"topic": "AI safety"})

    print(f"Session: {tracer.session_id}")
    # → Query VectaDB's /api/v1/events?session_id=<session_id> to see the audit trail
"""

from .tracer import VectaDBTracer, create_tracer_from_env
from .callbacks import VectaDBCallbackHandler
from .client import VectaDBClient, SyncVectaDBClient, VectaDBClientError
from .models import (
    VectaDBEvent,
    CrewEventType,
    CrewRunState,
    AgentRunState,
    BulkIngestionResponse,
    HealthResponse,
)

__version__ = "0.1.0"
__author__ = "Roberto Williams Batista"

__all__ = [
    # Main interface
    "VectaDBTracer",
    "create_tracer_from_env",
    # Lower-level components
    "VectaDBCallbackHandler",
    "VectaDBClient",
    "SyncVectaDBClient",
    "VectaDBClientError",
    # Models
    "VectaDBEvent",
    "CrewEventType",
    "CrewRunState",
    "AgentRunState",
    "BulkIngestionResponse",
    "HealthResponse",
]
