"""
Basic example: CrewAI research crew with VectaDB audit tracing.

Run:
    # 1. Start VectaDB (see vectadb3/docker-compose.yml)
    docker-compose up -d

    # 2. Set your LLM API key
    export OPENAI_API_KEY=sk-...

    # 3. Run this example
    python examples/basic_audit_example.py
"""

import os
from crewai import Agent, Crew, Task
from crewai_tools import SerperDevTool

from vectadb_crewai import VectaDBTracer

# ---------------------------------------------------------------------------
# 1. Define your agents and tasks as normal
# ---------------------------------------------------------------------------

search_tool = SerperDevTool()

researcher = Agent(
    role="Senior Research Analyst",
    goal="Find accurate, up-to-date information on the given topic",
    backstory=(
        "You are an expert researcher with a deep background in technology and AI. "
        "You always cite your sources and verify information before presenting it."
    ),
    tools=[search_tool],
    verbose=True,
)

writer = Agent(
    role="Technical Writer",
    goal="Transform research findings into a clear, concise report",
    backstory=(
        "You are a skilled technical writer who distills complex information "
        "into accessible prose without losing accuracy."
    ),
    verbose=True,
)

research_task = Task(
    description=(
        "Research the current state of {topic}. "
        "Identify the top 3 recent developments, key players, and open challenges. "
        "Provide at least 3 verifiable sources."
    ),
    expected_output="A structured research brief with findings and sources.",
    agent=researcher,
)

writing_task = Task(
    description=(
        "Using the research brief, write a 400-word executive summary on {topic} "
        "suitable for a non-technical audience."
    ),
    expected_output="A polished 400-word executive summary.",
    agent=writer,
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    verbose=True,
)

# ---------------------------------------------------------------------------
# 2. Wrap kickoff with VectaDBTracer
# ---------------------------------------------------------------------------

tracer = VectaDBTracer(
    vectadb_url=os.getenv("VECTADB_URL", "http://localhost:8080"),
    crew_name="research_crew",
    generate_embeddings=True,   # Enable semantic similarity search over events
    fail_silently=True,         # Don't crash the crew if VectaDB is unreachable
)

result = tracer.kickoff(crew, inputs={"topic": "ontology-native vector databases"})

# ---------------------------------------------------------------------------
# 3. Inspect the audit trail
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("Crew Result:")
print("=" * 60)
print(result)

print("\n" + "=" * 60)
print(f"VectaDB Audit Session: {tracer.session_id}")
print("=" * 60)
print(
    f"Query your audit trail at:\n"
    f"  GET {tracer.vectadb_url}/api/v1/events?session_id={tracer.session_id}\n"
    f"\nOr run a semantic search:\n"
    f"  POST {tracer.vectadb_url}/api/v1/query/hybrid\n"
    f'  {{"vector_query": "tool call errors", "session_id": "{tracer.session_id}"}}'
)

if tracer.run_state:
    print(f"\nAgents traced: {len(tracer.run_state.agents)}")
    for agent_id, state in tracer.run_state.agents.items():
        print(
            f"  [{state.role}] agent_id={agent_id} "
            f"trace_id={state.trace_id} "
            f"llm_calls={state.llm_call_count} "
            f"tool_calls={state.tool_call_count}"
        )
