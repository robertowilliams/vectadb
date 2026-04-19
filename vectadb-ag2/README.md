# vectadb-ag2

AG2 (AutoGen) observability and RAG integration for [VectaDB](https://github.com/vectadb/vectadb) — an ontology-native vector+graph database.

Provides typed audit event emission for multi-agent conversations and a hybrid-search retriever that replaces ChromaDB in AG2 RAG pipelines.

## Installation

```bash
pip install vectadb-ag2
```

Install with the AG2 runtime:

```bash
pip install "vectadb-ag2[ag2]"           # core AG2
pip install "vectadb-ag2[retrievechat]"  # AG2 + RetrieveChat RAG support
```

**Requirements:** Python 3.10+, a running VectaDB instance.

---

## Integrations

### VectaDBAG2Tracer — multi-agent context manager

Instruments a group of `ConversableAgent` instances and flushes all buffered audit events to VectaDB when the context exits.

```python
from vectadb_ag2 import VectaDBAG2Tracer
import autogen

assistant = autogen.AssistantAgent("assistant", llm_config={...})
user_proxy = autogen.UserProxyAgent("user_proxy")

tracer = VectaDBAG2Tracer(vectadb_url="http://localhost:8080")

with tracer.instrument(assistant, user_proxy):
    user_proxy.initiate_chat(assistant, message="Summarise the Q1 report.")
# events are flushed automatically on context exit
```

Build a tracer from environment variables:

```python
from vectadb_ag2 import create_tracer_from_env

tracer = create_tracer_from_env()
```

---

### VectaDBLoggingHook — per-agent manual instrumentation

Attach directly to a single agent when you need finer control over which agents are traced.

```python
from vectadb_ag2 import VectaDBLoggingHook

hook = VectaDBLoggingHook(vectadb_url="http://localhost:8080", agent_id="assistant")
assistant.register_hook("process_message_before_send", hook.on_send)
assistant.register_hook("process_last_received_message", hook.on_receive)
```

Events are emitted immediately on each hook invocation; call `hook.flush()` to drain any remaining buffer.

---

### VectaDBRetriever — hybrid RAG retrieval

Drop-in replacement for ChromaDB in AG2 `RetrieveUserProxyAgent` pipelines. Combines vector similarity search with VectaDB's graph-aware retrieval.

```python
from vectadb_ag2 import VectaDBRetriever
import autogen

retriever = VectaDBRetriever(
    vectadb_url="http://localhost:8080",
    collection="knowledge-base",
    top_k=5,
)

retrieve_agent = autogen.RetrieveUserProxyAgent(
    "retriever",
    retrieve_config={
        "customized_retriever": retriever,
    },
)
```

---

## Environment variables for `create_tracer_from_env()`

| Variable              | Description                                               | Default      |
|-----------------------|-----------------------------------------------------------|--------------|
| `VECTADB_URL`         | Base URL of the VectaDB API                              | *(required)* |
| `VECTADB_API_KEY`     | API key (omit for unauthenticated instances)             | `""`         |
| `VECTADB_SESSION_ID`  | Fixed session ID; auto-generated UUID if not set         | auto         |
| `VECTADB_RUN_NAME`    | Human-readable label attached to every event             | `""`         |
| `VECTADB_FAIL_SILENT` | Log errors but never raise on VectaDB failures (`1`/`0`) | `0`          |

---

## License

Apache-2.0
