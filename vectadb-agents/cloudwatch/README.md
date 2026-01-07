# VectaDB CloudWatch Agent

CloudWatch log ingestion agent for VectaDB - automatically polls AWS CloudWatch Logs and sends events to VectaDB's event ingestion API.

## Features

- **Automatic Log Polling**: Continuously polls CloudWatch logs at configurable intervals
- **Built-in Parsers**: Pre-configured parsers for LangChain and LlamaIndex logs
- **Flexible Parsing**: Support for JSON, regex, and custom parsers
- **Resilient Trace Detection**: Automatically groups events into traces using session_id, request_id, or agent_id
- **Bulk Ingestion**: Batches events for efficient API calls (100 events per request)
- **Retry Logic**: Automatic retry with exponential backoff on failures
- **Multiple Log Groups**: Monitor multiple CloudWatch log groups simultaneously

## Prerequisites

- Rust 1.70 or higher
- AWS account with CloudWatch Logs
- VectaDB instance running (see main README)
- AWS credentials configured (via environment, credentials file, or IAM role)

## Installation

### From Source

```bash
cd vectadb-agents/cloudwatch
cargo build --release
```

The binary will be at `target/release/vectadb-cloudwatch-agent`.

## Configuration

Create a `config.yaml` file based on `config.example.yaml`:

```yaml
aws:
  region: "us-east-1"

vectadb:
  endpoint: "http://localhost:8080"
  batch_size: 100

log_groups:
  - name: "/aws/lambda/my-agent"
    agent_id: "my-agent-001"
    parsers:
      - name: "langchain"
        type: "langchain"
        priority: 10

agent:
  poll_interval_secs: 10
  lookback_secs: 300
```

### Configuration Options

#### AWS Section

- `region` (required): AWS region (e.g., "us-east-1")
- `profile` (optional): AWS profile name

#### VectaDB Section

- `endpoint` (required): VectaDB API URL
- `api_key` (optional): API key for authentication (future feature)
- `batch_size` (default: 100): Number of events per batch request
- `timeout_secs` (default: 30): HTTP request timeout

#### Log Groups

Each log group configuration includes:

- `name` (required): CloudWatch log group name
- `agent_id` (optional): Agent identifier for this log group
- `filter_pattern` (optional): CloudWatch filter pattern to reduce log volume
- `parsers` (required): List of parser rules (evaluated by priority)

#### Parser Rules

Each parser has:

- `name`: Parser name/description
- `type`: Parser type (json, regex, langchain, llamaindex)
- `pattern`: Regex pattern (required for regex type)
- `field_mapping`: Map capture groups to event properties
- `event_type`: Event type to assign when parser matches
- `priority`: Priority (lower number = higher priority, default: 100)

#### Agent Settings

- `poll_interval_secs` (default: 10): Seconds between polls
- `lookback_secs` (default: 300): Initial lookback window (5 minutes)
- `auto_create_traces` (default: true): Auto-create traces from session_id
- `generate_embeddings` (default: true): Generate embeddings for semantic search

## Usage

### Running Locally

```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key

# Set config path (optional, defaults to config.yaml)
export CONFIG_PATH=config.yaml

# Run agent
cargo run --release
```

### Running with Docker

```bash
docker build -t vectadb/cloudwatch-agent .

docker run -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
           -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
           -v $(pwd)/config.yaml:/config.yaml \
           -e CONFIG_PATH=/config.yaml \
           vectadb/cloudwatch-agent
```

### Environment Variables

- `CONFIG_PATH`: Path to config file (default: "config.yaml")
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `AWS_REGION`: AWS region (overrides config)
- `RUST_LOG`: Log level (e.g., "info", "debug")

## Built-in Parsers

### LangChain Parser

Automatically detects and parses LangChain log patterns:

- Tool calls: "Running WebSearch tool with input: ..."
- Chain execution: "Entering new LLMChain with input: ..."
- Agent actions: "Agent Action: tool=..., input=..."

**Example Config**:
```yaml
parsers:
  - name: "langchain"
    type: "langchain"
    priority: 10
```

### LlamaIndex Parser

Automatically detects and parses LlamaIndex log patterns:

- Queries: "query: What is the weather? response: ..."
- Retrieval: "retrieve query: ... nodes: 5"

**Example Config**:
```yaml
parsers:
  - name: "llamaindex"
    type: "llamaindex"
    priority: 10
```

### JSON Parser

Parses JSON-formatted log lines:

```yaml
parsers:
  - name: "json"
    type: "json"
    event_type: "custom_event"
    field_mapping:
      msg: "message"  # Rename 'msg' field to 'message'
    priority: 5
```

### Regex Parser

Custom regex patterns with named capture groups:

```yaml
parsers:
  - name: "error_parser"
    type: "regex"
    pattern: "ERROR:.*?(?P<message>.*?)in\\s*(?P<location>.*)"
    field_mapping:
      message: "error_message"
      location: "error_location"
    event_type: "error"
    priority: 5
```

## Resilient Trace Detection

The agent automatically extracts trace identifiers using multiple strategies:

### ID Extraction Patterns

The agent searches for these patterns in log messages:

1. **Session ID**: `session_id`, `session-id`, `sess_id`, `sess-id`
2. **Request ID**: `request_id`, `request-id`, `req_id`, `req-id`, `trace_id`, `trace-id`
3. **Agent ID**: `agent_id`, `agent-id`, `agent_name`, `agent-name`

**Example Log Lines**:
```
INFO: Processing request (request_id: req-12345)
DEBUG: Session started (session-id: sess-abc123)
INFO: Agent langchain-agent-001 handling query
```

These IDs are automatically extracted and used by VectaDB's resilient trace detection system.

## AWS IAM Permissions

The agent requires the following IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:FilterLogEvents",
        "logs:GetLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": [
        "arn:aws:logs:*:*:log-group:/aws/lambda/*",
        "arn:aws:logs:*:*:log-group:/aws/ecs/*"
      ]
    }
  ]
}
```

## Monitoring

The agent outputs structured JSON logs for easy monitoring:

```bash
# View logs with jq
cargo run 2>&1 | jq .

# Filter for errors
cargo run 2>&1 | jq 'select(.level == "ERROR")'

# Monitor ingestion stats
cargo run 2>&1 | jq 'select(.message | contains("Ingestion complete"))'
```

## Troubleshooting

### Agent not fetching logs

1. Check AWS credentials: `aws sts get-caller-identity`
2. Verify log group exists: `aws logs describe-log-groups --log-group-name-prefix "/aws/lambda"`
3. Check IAM permissions (see above)
4. Increase lookback window in config: `lookback_secs: 600`

### VectaDB connection errors

1. Check VectaDB is running: `curl http://localhost:8080/health`
2. Verify endpoint in config matches VectaDB address
3. Check network connectivity

### Parsing errors

1. Enable debug logging: `export RUST_LOG=debug`
2. Check parser priority (lower = higher priority)
3. Test regex patterns at https://regex101.com
4. Add fallback parser with priority 100

### High AWS costs

1. Use `filter_pattern` to reduce log volume
2. Increase `poll_interval_secs` to poll less frequently
3. Reduce `lookback_secs` to fetch fewer historical logs
4. Monitor CloudWatch API usage in AWS Cost Explorer

## Performance

- **Throughput**: ~1,000 events/second per log group
- **Memory**: ~50-100 MB per agent instance
- **CPU**: <5% (idle), 10-20% (active polling)
- **Network**: Batched API calls minimize overhead

## Development

### Running Tests

```bash
cargo test
```

### Building for Production

```bash
cargo build --release --target x86_64-unknown-linux-musl
```

### Code Structure

```
src/
├── main.rs              # Main agent loop
├── config.rs            # Configuration parsing and validation
├── cloudwatch_client.rs # AWS CloudWatch SDK wrapper
├── vectadb_client.rs    # VectaDB API client with retry logic
└── parser.rs            # Log parsing with built-in patterns
```

## Examples

### Example 1: LangChain on Lambda

```yaml
log_groups:
  - name: "/aws/lambda/langchain-weather-bot"
    agent_id: "weather-bot"
    parsers:
      - name: "langchain"
        type: "langchain"
        priority: 10
```

### Example 2: Multiple Parsers with Fallback

```yaml
log_groups:
  - name: "/aws/lambda/multi-agent"
    parsers:
      # Try JSON first
      - name: "json"
        type: "json"
        priority: 5

      # Then LangChain patterns
      - name: "langchain"
        type: "langchain"
        priority: 10

      # Catch errors
      - name: "errors"
        type: "regex"
        pattern: "(?i)ERROR.*?(?P<message>.*)"
        event_type: "error"
        priority: 20

      # Fallback for everything else
      - name: "fallback"
        type: "regex"
        pattern: "(?P<message>.*)"
        event_type: "info"
        priority: 100
```

### Example 3: High-Volume Production Setup

```yaml
vectadb:
  endpoint: "https://vectadb.prod.example.com"
  batch_size: 200  # Larger batches for efficiency
  timeout_secs: 60

log_groups:
  - name: "/aws/ecs/agent-cluster"
    filter_pattern: '[level=INFO || level=ERROR]'  # Reduce volume
    parsers:
      - name: "langchain"
        type: "langchain"
        priority: 10

agent:
  poll_interval_secs: 30  # Poll every 30 seconds (less frequent)
  lookback_secs: 60       # Only 1 minute lookback on restart
```

## License

Apache 2.0

## Support

For issues and questions:
- GitHub: https://github.com/robertowilliams/vectadb/issues
- Documentation: https://github.com/robertowilliams/vectadb

## Related

- [VectaDB Core](../../README.md) - Main VectaDB database
- [Event Ingestion API](../../vectadb/src/api/handlers.rs) - API documentation
- [Phase 5 Plan](../../PHASE5_PLAN.md) - Implementation details
