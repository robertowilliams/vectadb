#!/usr/bin/env python3
"""
Test script to ingest Bedrock logs into VectaDB
Parses bedrock_chain_of_thought_logs.json and sends to /api/v1/events/batch
"""

import json
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

VECTADB_URL = "http://localhost:8080"
BEDROCK_LOGS_PATH = "notes/bedrock_chain_of_thought_logs.json"


def load_bedrock_logs() -> List[Dict[str, Any]]:
    """Load Bedrock logs from JSON file"""
    print(f"Loading Bedrock logs from: {BEDROCK_LOGS_PATH}")
    with open(BEDROCK_LOGS_PATH, 'r') as f:
        logs = json.load(f)
    print(f"Loaded {len(logs)} Bedrock log events")
    return logs


def extract_tool_name(log: Dict[str, Any]) -> Optional[str]:
    """Extract tool name from Bedrock log if present"""
    try:
        content = log.get("output", {}).get("outputBodyJson", {}).get("output", {}).get("message", {}).get("content", [])
        for item in content:
            if "toolUse" in item:
                return item["toolUse"].get("name")
    except (KeyError, TypeError):
        pass
    return None


def parse_bedrock_event(log: Dict[str, Any], agent_id: str = "bedrock-healthcare-assistant") -> Dict[str, Any]:
    """Parse a single Bedrock log into VectaDB event format"""

    # Extract key fields
    request_id = log.get("requestId")
    timestamp = log.get("timestamp", datetime.utcnow().isoformat() + "Z")
    operation = log.get("operation")
    model_id = log.get("modelId")
    error_code = log.get("errorCode")

    # Extract tool use
    tool_name = extract_tool_name(log)

    # Extract metrics
    latency_ms = log.get("output", {}).get("outputBodyJson", {}).get("metrics", {}).get("latencyMs")
    input_tokens = log.get("input", {}).get("inputTokenCount") or \
                   log.get("output", {}).get("outputBodyJson", {}).get("usage", {}).get("inputTokens")
    output_tokens = log.get("output", {}).get("outputTokenCount") or \
                    log.get("output", {}).get("outputBodyJson", {}).get("usage", {}).get("outputTokens")

    # Determine event type
    if error_code:
        event_type = "bedrock_error"
    elif tool_name:
        event_type = "bedrock_tool_use"
    else:
        event_type = "bedrock_invocation"

    # Build properties
    properties = {
        "request_id": request_id,
        "operation": operation,
        "model_id": model_id,
    }

    if error_code:
        properties["error_code"] = error_code

    if tool_name:
        properties["tool_name"] = tool_name
        # Try to extract tool use ID and input
        try:
            content = log["output"]["outputBodyJson"]["output"]["message"]["content"]
            for item in content:
                if "toolUse" in item:
                    properties["tool_use_id"] = item["toolUse"].get("toolUseId")
                    properties["tool_input"] = item["toolUse"].get("input")
                    break
        except (KeyError, TypeError):
            pass

    if latency_ms:
        properties["latency_ms"] = latency_ms
    if input_tokens:
        properties["input_tokens"] = input_tokens
    if output_tokens:
        properties["output_tokens"] = output_tokens

    # Add full log for debugging
    properties["raw_log"] = log

    # Build VectaDB event
    event = {
        "timestamp": timestamp,
        "event_type": event_type,
        "agent_id": agent_id,
        "session_id": request_id,  # Use requestId as session for trace grouping
        "properties": properties,
        "source": {
            "system": "cloudwatch",
            "log_group": "/aws/bedrock/agent/invocations",
            "log_stream": "2025-12-17",
            "log_id": request_id
        }
    }

    return event


def send_events_batch(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Send events to VectaDB batch ingestion endpoint"""
    url = f"{VECTADB_URL}/api/v1/events/batch"

    payload = {
        "events": events,
        "options": {
            "auto_create_traces": True,
            "generate_embeddings": False
        }
    }

    print(f"\nSending {len(events)} events to VectaDB...")
    print(f"URL: {url}")

    response = requests.post(url, json=payload)

    print(f"Response status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Success!")
        print(f"   Ingested: {result.get('ingested', 0)}")
        print(f"   Failed: {result.get('failed', 0)}")
        print(f"   Traces created: {len(result.get('trace_ids', []))}")
        if result.get('errors'):
            print(f"   Errors: {result['errors'][:3]}...")  # Show first 3 errors
        return result
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   Response: {response.text}")
        return None


def check_vectadb_health() -> bool:
    """Check if VectaDB is running"""
    try:
        response = requests.get(f"{VECTADB_URL}/health", timeout=2)
        if response.status_code == 200:
            health = response.json()
            print(f"✅ VectaDB is healthy: {health.get('status')} v{health.get('version')}")
            return True
    except requests.exceptions.RequestException as e:
        print(f"❌ VectaDB is not accessible: {e}")
        return False


def query_traces(limit: int = 5) -> Optional[List[Dict[str, Any]]]:
    """Query traces from VectaDB to verify ingestion"""
    url = f"{VECTADB_URL}/api/v1/traces?limit={limit}"

    print(f"\nQuerying traces from VectaDB...")
    response = requests.get(url)

    if response.status_code == 200:
        traces = response.json()
        print(f"✅ Found {len(traces)} traces")
        return traces
    else:
        print(f"❌ Failed to query traces: {response.status_code}")
        return None


def main():
    print("=" * 80)
    print("VectaDB Bedrock Log Ingestion Test")
    print("=" * 80)
    print()

    # Check VectaDB health
    if not check_vectadb_health():
        print("\nPlease start VectaDB first: cd vectadb && cargo run --release")
        return

    # Load logs
    bedrock_logs = load_bedrock_logs()

    # Parse events
    print(f"\nParsing {len(bedrock_logs)} Bedrock events...")
    events = []
    for log in bedrock_logs:
        try:
            event = parse_bedrock_event(log)
            events.append(event)
        except Exception as e:
            print(f"Error parsing log: {e}")

    print(f"Successfully parsed {len(events)} events")

    # Show sample event
    if events:
        print("\nSample event:")
        print(json.dumps(events[0], indent=2, default=str)[:500] + "...")

    # Send to VectaDB
    result = send_events_batch(events)

    if result:
        print("\n" + "=" * 80)
        print("Ingestion Summary")
        print("=" * 80)
        print(f"Total events sent: {len(events)}")
        print(f"Successfully ingested: {result.get('ingested', 0)}")
        print(f"Failed: {result.get('failed', 0)}")
        print(f"Traces created: {len(result.get('trace_ids', []))}")
        print(f"Unique trace IDs: {len(set(result.get('trace_ids', [])))}")

        # Show sample trace IDs
        if result.get('trace_ids'):
            print(f"\nSample trace IDs (first 5):")
            for trace_id in result['trace_ids'][:5]:
                print(f"  - {trace_id}")

        # Query traces to verify
        traces = query_traces(limit=5)
        if traces:
            print(f"\nSample traces from database:")
            for i, trace in enumerate(traces[:3], 1):
                print(f"\n  Trace #{i}:")
                print(f"    ID: {trace.get('id')}")
                print(f"    Agent: {trace.get('agent_id')}")
                print(f"    Event count: {len(trace.get('events', []))}")
                print(f"    Start: {trace.get('start_time')}")


if __name__ == "__main__":
    main()
