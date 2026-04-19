# vectadb-semantic-kernel

VectaDB observability and memory integration for [Microsoft Semantic Kernel](https://github.com/microsoft/semantic-kernel).

Capture every kernel function invocation, vector store access, and retrieval operation as typed, searchable events in VectaDB — giving you full audit trails, session replay, and semantic similarity search over your agent's history.

## Features

- **Function observability** — wraps every SK kernel function via `IFunctionInvocationFilter`, recording inputs, outputs, errors, and duration
- **Vector store** — use VectaDB as a first-class SK memory backend with `upsert`, `get`, `search`, and `delete`
- **Plugin** — expose VectaDB's search and memory as native kernel functions callable from plans and prompts
- **Session tracing** — `VectaDBSKTracer` ties all events to a session ID and bulk-ingests them in one shot
- **No SK required at import** — works without `semantic-kernel` installed (useful for testing); the stub `@kernel_function` decorator is replaced by the real one when SK is present

## Installation

```bash
pip install vectadb-semantic-kernel
# or with Semantic Kernel
pip install "vectadb-semantic-kernel[sk]"
```

## Quick start

### Observability

```python
from semantic_kernel import Kernel
from vectadb_sk import VectaDBSKTracer

kernel = Kernel()
# ... add your plugins and services ...

with VectaDBSKTracer("http://localhost:8080", session_id="run-001") as tracer:
    tracer.register(kernel)
    result = await kernel.invoke("MyPlugin", "my_function", input="hello")
# Events flushed automatically on __exit__
```

### Memory / vector store

```python
from vectadb_sk import VectaDBVectorStore

store = VectaDBVectorStore(base_url="http://localhost:8080", collection="docs")

await store.upsert("doc-1", "VectaDB is a graph-vector hybrid database.", metadata={"tag": "db"})

results = await store.search("graph database", n_results=5)
for r in results:
    print(f"[{r.score:.2f}] {r.content}")
```

### Plugin (kernel functions)

```python
from semantic_kernel import Kernel
from vectadb_sk import VectaDBPlugin

kernel = Kernel()
plugin = VectaDBPlugin(base_url="http://localhost:8080")
kernel.add_plugin(plugin, plugin_name="VectaDB")

# Now callable from prompts:
# {{VectaDB.search query="what is VectaDB"}}
```

### Environment variables

```python
from vectadb_sk import create_tracer_from_env

tracer = create_tracer_from_env()  # reads from env
```

| Variable | Default | Description |
|---|---|---|
| `VECTADB_URL` | `http://localhost:8080` | VectaDB base URL |
| `VECTADB_API_KEY` | _(none)_ | Optional API key |
| `VECTADB_SESSION_ID` | auto-generated | Fixed session ID |
| `VECTADB_FAIL_SILENT` | `true` | Set `false` to surface errors |

## Event types

| Type | Emitted when |
|---|---|
| `function_invoked` | A kernel function completed successfully |
| `function_error` | A kernel function raised an exception |
| `prompt_rendered` | A prompt template was rendered |
| `memory_read` | A vector store get or search was performed |
| `memory_write` | A vector store upsert or delete was performed |
| `vector_search` | A semantic similarity search returned results |

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

## License

Apache-2.0
