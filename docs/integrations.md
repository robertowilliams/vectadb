# Integrations

All integrations follow the same principle: wrap the agent's execution path with VectaDB callbacks or loggers, and observability happens automatically.

## LangChain

```bash
pip install vectadb langchain langchain-openai
```

```python
from langchain.agents import AgentExecutor, initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from vectadb import VectaDB, VectaDBCallback

db = VectaDB("vectadb://localhost:3000")
llm = ChatOpenAI(model="gpt-4", temperature=0)

agent_executor = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    callbacks=[VectaDBCallback(db=db, agent_name="researcher_42")],
    verbose=True
)

result = agent_executor.run("Analyze Q4 earnings for AAPL")
```

### What Gets Captured

| Event | Data |
|---|---|
| Agent start | Name, task, timestamp |
| Tool call | Tool name, input, output, latency |
| LLM call | Prompt, response, model, tokens, cost |
| Thought | Chain-of-thought text, sequence |
| Error | Message + stack trace (embedded for clustering) |
| Agent finish | Output, total duration, total cost |

---

## AutoGPT

```python
from vectadb import VectaDB, VectaDBLogger

db = VectaDB("vectadb://localhost:3000")
logger = VectaDBLogger(db=db, agent_id="autogpt_researcher_1", auto_vector=True)
agent = Agent(ai_name="Researcher", memory=memory, logger=logger)
```

---

## Custom Integration

```python
from vectadb import VectaDB
import time

db = VectaDB("vectadb://localhost:3000")
agent = db.agents.create(role="custom_researcher", goal="analyze trends", auto_vector=True)
task = db.tasks.create(agent_id=agent.id, description="Analyze Q4 2025 market trends")

try:
    db.thoughts.create(agent_id=agent.id, task_id=task.id, content="Loading data...")
    result = fetch_data()
    db.tasks.complete(task.id, output=result)
except Exception as e:
    db.logs.ingest(agent_id=agent.id, task_id=task.id, level="ERROR", message=str(e))
    db.tasks.fail(task.id, error=str(e))
    raise
```

---

## REST API (Any Language)

```bash
# Register agent
curl -X POST http://localhost:3000/agents \
  -H "Content-Type: application/json" \
  -d '{"role": "data_processor", "goal": "Process reports", "auto_vector": true}'

# Batch log ingestion
curl -X POST http://localhost:3000/logs/batch \
  -H "Content-Type: application/json" \
  -d '{"entries": [{"agent_id": "a1", "level": "ERROR", "message": "Timeout"}]}'
```

---

## Compatibility

| Framework | Integration | Effort |
|---|---|---|
| LangChain | Callback plugin | < 5 lines |
| LangGraph | Callback plugin | < 5 lines |
| AutoGPT | Logger replacement | < 5 lines |
| CrewAI | Callback plugin | < 5 lines |
| BabyAGI | Manual | ~20 lines |
| Custom Python | Direct SDK | ~20 lines |
| Custom Rust | Direct SDK | ~30 lines |
| Any language | REST API | ~10 lines |

## Planned

- Semantic Kernel (Microsoft)
- Haystack pipeline node
- DSPy module callback
- Vertex AI Agents
- AWS Bedrock Agents
- GraphQL API
