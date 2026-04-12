"""
Advanced example: multi-crew runs with context-manager usage and
manual flush — demonstrates the full VectaDB provenance graph pattern
described in the VectaDB paper (Section 6.4 incident investigation).

This example shows:
  - Using tracer as a context manager
  - Multiple sequential crew runs under separate sessions
  - Querying the VectaDB audit trail after each run
  - Semantic incident search across all runs
"""

from __future__ import annotations

import os
import asyncio
import httpx

from crewai import Agent, Crew, Task
from vectadb_crewai import VectaDBTracer, VectaDBClient

VECTADB_URL = os.getenv("VECTADB_URL", "http://localhost:8080")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ---------------------------------------------------------------------------
# Shared agent definitions
# ---------------------------------------------------------------------------

analyst = Agent(
    role="Data Analyst",
    goal="Analyze the provided data and identify anomalies",
    backstory="Expert in statistical analysis and anomaly detection.",
    verbose=False,
)

auditor = Agent(
    role="Compliance Auditor",
    goal="Verify that the analyst's findings comply with policy",
    backstory="Ensures all analysis follows regulatory guidelines.",
    verbose=False,
)


def make_analysis_crew(dataset_name: str) -> Crew:
    """Factory that creates a fresh crew for a given dataset."""
    task1 = Task(
        description=f"Analyse the dataset '{dataset_name}' and list any anomalies found.",
        expected_output="A list of anomalies with severity ratings.",
        agent=analyst,
    )
    task2 = Task(
        description="Review the anomaly list and flag any policy violations.",
        expected_output="A compliance assessment report.",
        agent=auditor,
    )
    return Crew(agents=[analyst, auditor], tasks=[task1, task2])


# ---------------------------------------------------------------------------
# Run multiple crews and collect session IDs
# ---------------------------------------------------------------------------

session_ids: list[str] = []
datasets = ["Q1_transactions", "Q2_transactions"]

for ds in datasets:
    print(f"\n>>> Running analysis for {ds}")

    tracer = VectaDBTracer(
        vectadb_url=VECTADB_URL,
        crew_name=f"compliance_crew_{ds}",
        fail_silently=True,
    )

    # Use context manager for automatic flush on exit
    with tracer:
        crew = make_analysis_crew(ds)
        tracer.instrument(crew)   # attach callbacks without running
        try:
            result = crew.kickoff(inputs={"dataset": ds})
            print(f"Result: {str(result)[:200]}")
        except Exception as exc:
            print(f"Crew error: {exc}")
            tracer.flush(error=exc)
            continue

    if tracer.session_id:
        session_ids.append(tracer.session_id)
        print(f"Session recorded: {tracer.session_id}")


# ---------------------------------------------------------------------------
# Post-run: semantic incident investigation (async)
# ---------------------------------------------------------------------------

async def investigate_incidents(sessions: list[str]) -> None:
    """
    Demonstrates VectaDB's four-query incident investigation pattern
    from Section 6.4 of the paper:
      1. Provenance query  — what evidence was used?
      2. Causality query   — what triggered the anomaly?
      3. Scope query       — blast radius assessment
      4. Control query     — did safeguards function?
    """
    async with VectaDBClient(VECTADB_URL) as client:
        # Check VectaDB is reachable
        if not await client.is_healthy():
            print("\nVectaDB not reachable — skipping incident investigation.")
            return

        print("\n" + "=" * 60)
        print("VectaDB Incident Investigation")
        print("=" * 60)

        # 1. Semantic search: find similar tool errors across all runs
        print("\n[1] Semantic search: tool call errors across all sessions")
        async with httpx.AsyncClient(base_url=VECTADB_URL) as http:
            for session_id in sessions:
                resp = await http.post(
                    "/api/v1/query/hybrid",
                    json={
                        "vector_query": "tool call error failure",
                        "session_id": session_id,
                        "limit": 5,
                    },
                )
                if resp.is_success:
                    data = resp.json()
                    count = len(data.get("results", []))
                    print(f"  Session {session_id}: {count} error-related events")

        # 2. Provenance: list all events for a session
        print("\n[2] Provenance trail for each session")
        for session_id in sessions:
            async with httpx.AsyncClient(base_url=VECTADB_URL) as http:
                resp = await http.get(f"/api/v1/events?session_id={session_id}")
                if resp.is_success:
                    events = resp.json().get("events", [])
                    type_counts: dict[str, int] = {}
                    for ev in events:
                        et = ev.get("event_type", "unknown")
                        type_counts[et] = type_counts.get(et, 0) + 1
                    print(f"  Session {session_id}:")
                    for etype, count in sorted(type_counts.items()):
                        print(f"    {etype}: {count}")

    print(
        f"\nFull audit data available at:\n"
        f"  {VECTADB_URL}/api/v1/events?session_id=<session_id>"
    )


if session_ids:
    asyncio.run(investigate_incidents(session_ids))
else:
    print("\nNo sessions recorded — ensure VectaDB is running and crews completed.")
