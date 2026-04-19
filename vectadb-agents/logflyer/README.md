# vectadb-logflyer

A daemon that tails log files, classifies agentic activity with an LLM, and ingests the results into [VectaDB](https://github.com/vectadb/vectadb).

**Poll loop (per watched file):**
1. Tail new lines since the last poll
2. Send lines in batches to an OpenAI-compatible LLM for classification
3. Keep only lines where `is_agentic == true`
4. Bulk-ingest the resulting events into VectaDB

Works with any log format — structured JSON, AG2 conversation logs, or plain application logs. Falls back to regex pattern matching if the LLM server is unreachable.

## Build

```bash
cargo build --release
```

**Requirements:** Rust 1.75+, a running VectaDB instance.

## Run

```bash
cp config.example.yaml config.yaml
# edit config.yaml
CONFIG_PATH=config.yaml ./target/release/vectadb-logflyer
```

The `CONFIG_PATH` environment variable overrides the default `config.yaml` path. Individual fields can also be overridden with environment variables using double-underscore separators (e.g. `LOGFLYER_LLM__BASE_URL`).

---

## Configuration

```yaml
llm:
  base_url: "http://localhost:11434"  # OpenAI-compatible server (no trailing slash)
  api_key: ""                         # leave empty for local servers
  model: "llama3"                     # model name as the server expects it
  max_tokens: 2048
  temperature: 0.0                    # 0.0 = deterministic (best for classification)
  timeout_secs: 60
  json_mode: true                     # disable if your server rejects json_object mode

vectadb:
  endpoint: "http://localhost:8080"
  # api_key: "your-key"
  batch_size: 100
  timeout_secs: 30

log_files:
  - path: "/var/log/myapp/langchain.log"
    agent_id: "langchain-agent-prod"
    # session_id: "fixed-id"          # optional; extracted from log lines if absent
  - path: "/tmp/ag2_conversation.log"
    agent_id: "ag2-orchestrator"

agent:
  poll_interval_secs: 5          # how often to check each file for new lines
  classification_batch_size: 30  # lines per LLM request (larger = fewer calls)
  lookback_lines: 100            # lines read on first startup (0 = tail from now)
  generate_embeddings: true      # ask VectaDB to embed events for semantic search
  auto_create_traces: true       # auto-link events to traces via session_id
  fail_silently: true            # log errors and keep running instead of crashing
```

---

## LLM compatibility

| Server      | `llm.base_url`                   | Notes                             |
|-------------|----------------------------------|-----------------------------------|
| Ollama      | `http://localhost:11434`         | No API key required               |
| vLLM        | `http://localhost:8000`          | No API key required               |
| LM Studio   | `http://localhost:1234`          | No API key required               |
| OpenAI      | `https://api.openai.com`         | Set `api_key`                     |

Any server that implements the OpenAI `/v1/chat/completions` endpoint is supported. Set `json_mode: false` if the server does not accept `response_format: json_object`.

## Pattern fallback

If the LLM server is unavailable, logflyer falls back to built-in regex patterns to identify agentic lines (tool calls, agent replies, chain steps). Classification accuracy is lower but the daemon keeps running and retries LLM classification on the next poll cycle.

---

## License

Apache-2.0
