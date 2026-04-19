# vectadb-langchain

LangChain observability and storage integrations for [VectaDB](https://github.com/vectadb/vectadb) — an ontology-native vector+graph database.

Provides four integrations: callback-based run tracing, a LangChain-compatible VectorStore, persistent chat message history, and LangGraph node tracing.

## Installation

```bash
pip install vectadb-langchain
```

LangGraph support is an optional extra:

```bash
pip install "vectadb-langchain[langgraph]"
```

**Requirements:** Python 3.10+, a running VectaDB instance.

---

## Integrations

### VectaDBTracer — LCEL chain and agent tracing

Wraps any LCEL chain or agent with a context manager. Every LangChain callback event (LLM start/end, tool call, chain step) is shipped to VectaDB as a typed audit event.

```python
from vectadb_langchain import VectaDBTracer

tracer = VectaDBTracer(vectadb_url="http://localhost:8080")

with tracer:
    result = chain.invoke(
        {"question": "What is RAG?"},
        config={"callbacks": [tracer.callback_handler]},
    )

print(tracer.session_id)  # use this ID to query the audit trail in VectaDB
```

To build a tracer purely from environment variables:

```python
from vectadb_langchain import create_tracer_from_env

tracer = create_tracer_from_env()  # reads VECTADB_URL, VECTADB_API_KEY, etc.
```

---

### VectaDBVectorStore — RAG document storage

A drop-in LangChain `VectorStore` backed by VectaDB. Supports `add_texts`, `similarity_search`, and `as_retriever`.

```python
from vectadb_langchain import VectaDBVectorStore

store = VectaDBVectorStore(vectadb_url="http://localhost:8080", collection="docs")
store.add_texts(["VectaDB is an ontology-native vector database..."])

retriever = store.as_retriever(search_kwargs={"k": 3})
```

---

### VectaDBChatMessageHistory — persistent conversation history

Stores and retrieves chat messages per session, compatible with `RunnableWithMessageHistory`.

```python
from langchain_core.runnables.history import RunnableWithMessageHistory
from vectadb_langchain import VectaDBChatMessageHistory

chain_with_history = RunnableWithMessageHistory(
    chain,
    lambda session_id: VectaDBChatMessageHistory(
        session_id=session_id,
        vectadb_url="http://localhost:8080",
    ),
)
```

---

### VectaDBLangGraphTracer — LangGraph node tracing

Wraps individual LangGraph nodes with trace instrumentation. Call `tracer.flush()` after graph execution to ensure all buffered events are sent.

```python
from langgraph.graph import StateGraph
from vectadb_langchain import VectaDBLangGraphTracer

tracer = VectaDBLangGraphTracer(vectadb_url="http://localhost:8080")

builder = StateGraph(MyState)
builder.add_node("planner",  tracer.traced_node("planner")(planner_fn))
builder.add_node("executor", tracer.traced_node("executor")(executor_fn))

graph = builder.compile()
graph.invoke({"messages": [...]})
tracer.flush()
```

---

## Configuration

All settings can be provided as constructor arguments or via environment variables.

| Environment variable    | Description                                              | Default     |
|-------------------------|----------------------------------------------------------|-------------|
| `VECTADB_URL`           | Base URL of the VectaDB API                             | *(required)*|
| `VECTADB_API_KEY`       | API key (leave unset for unauthenticated instances)     | `""`        |
| `VECTADB_SESSION_ID`    | Fixed session ID; auto-generated UUID if not set        | auto        |
| `VECTADB_RUN_NAME`      | Human-readable label attached to every event            | `""`        |
| `VECTADB_FAIL_SILENT`   | Log errors but never raise on VectaDB failures (`1`/`0`)| `0`         |

---

## License

Apache-2.0
