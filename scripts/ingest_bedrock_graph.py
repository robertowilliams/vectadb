#!/usr/bin/env python3
"""
Ingest Bedrock logs into VectaDB as entities and relations for graph visualization.
This script creates BedrockRequest, ToolUse, Patient, and Agent entities with their relationships.
"""

import json
import requests
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Set

VECTADB_URL = "http://localhost:8080"
BEDROCK_LOGS_PATH = "test/bedrock_chain_of_thought_logs.json"
SCHEMA_PATH = "bedrock_schema_correct.json"


def check_health() -> bool:
    """Check if VectaDB is running and if schema is loaded"""
    try:
        response = requests.get(f"{VECTADB_URL}/health", timeout=2)
        if response.status_code == 200:
            health = response.json()
            print(f"✅ VectaDB is healthy: {health.get('status')} v{health.get('version')}")
            if health.get('ontology_loaded'):
                print(f"✅ Schema already loaded: {health.get('ontology_namespace')} v{health.get('ontology_version')}")
            return True
    except requests.exceptions.RequestException as e:
        print(f"❌ VectaDB is not accessible: {e}")
        return False


def upload_schema(schema: Dict[str, Any]) -> bool:
    """Upload ontology schema to VectaDB"""
    url = f"{VECTADB_URL}/api/v1/ontology/schema"

    print(f"\nUploading schema: {schema['namespace']} v{schema['version']}")

    # Wrap schema in the expected format
    payload = {
        "schema": json.dumps(schema),
        "format": "json"
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        print(f"✅ Schema uploaded successfully")
        return True
    else:
        print(f"❌ Failed to upload schema: {response.status_code}")
        print(f"   Response: {response.text}")
        return False


def create_entity(entity_type: str, properties: Dict[str, Any]) -> Optional[str]:
    """Create an entity in VectaDB"""
    url = f"{VECTADB_URL}/api/v1/entities"

    payload = {
        "entity_type": entity_type,
        "properties": properties
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        entity = response.json()
        return entity.get("id")
    else:
        print(f"❌ Failed to create {entity_type}: {response.status_code}")
        print(f"   Properties: {properties}")
        print(f"   Response: {response.text}")
        return None


def create_relation(relation_type: str, from_id: str, to_id: str, properties: Dict[str, Any] = None) -> bool:
    """Create a relation in VectaDB"""
    url = f"{VECTADB_URL}/api/v1/relations"

    payload = {
        "relation_type": relation_type,
        "source_id": from_id,
        "target_id": to_id,
        "properties": properties or {}
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        return True
    else:
        print(f"❌ Failed to create relation {relation_type}: {response.status_code}")
        return False


def extract_patient_ids(log: Dict[str, Any]) -> Set[str]:
    """Extract patient IDs from the log"""
    patient_ids = set()

    # Check user message
    try:
        messages = log.get("input", {}).get("inputBodyJson", {}).get("messages", [])
        for msg in messages:
            content = msg.get("content", [])
            for item in content:
                text = item.get("text", "")
                # Look for patterns like PAT001, patient-001, etc.
                matches = re.findall(r'\b(PAT\d+|patient-\d+)\b', text, re.IGNORECASE)
                patient_ids.update(matches)
    except (KeyError, TypeError):
        pass

    # Check tool inputs
    try:
        content = log.get("output", {}).get("outputBodyJson", {}).get("output", {}).get("message", {}).get("content", [])
        for item in content:
            if "toolUse" in item:
                tool_input = item["toolUse"].get("input", {})
                if "patient_id" in tool_input:
                    patient_ids.add(tool_input["patient_id"])
    except (KeyError, TypeError):
        pass

    return patient_ids


def extract_tool_uses(log: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract tool uses from the log"""
    tool_uses = []

    try:
        content = log.get("output", {}).get("outputBodyJson", {}).get("output", {}).get("message", {}).get("content", [])
        for item in content:
            if "toolUse" in item:
                tool_use = item["toolUse"]
                tool_uses.append({
                    "tool_name": tool_use.get("name", "unknown"),
                    "tool_use_id": tool_use.get("toolUseId", ""),
                    "input_data": json.dumps(tool_use.get("input", {}))
                })
    except (KeyError, TypeError):
        pass

    return tool_uses


def extract_user_message(log: Dict[str, Any]) -> Optional[str]:
    """Extract user message from the log"""
    try:
        messages = log.get("input", {}).get("inputBodyJson", {}).get("messages", [])
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", [])
                for item in content:
                    if "text" in item:
                        return item["text"]
    except (KeyError, TypeError):
        pass
    return None


def ingest_bedrock_logs(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ingest Bedrock logs as entities and relations"""

    stats = {
        "requests": 0,
        "tool_uses": 0,
        "patients": 0,
        "agents": 0,
        "relations": 0
    }

    # Track created entities to avoid duplicates
    agent_entities = {}  # arn -> entity_id
    patient_entities = {}  # patient_id -> entity_id
    request_entities = []  # List of (timestamp, entity_id) for sequential linking

    print(f"\nProcessing {len(logs)} Bedrock log entries...")

    for idx, log in enumerate(logs, 1):
        print(f"\n[{idx}/{len(logs)}] Processing request {log.get('requestId', 'unknown')[:8]}...")

        # Extract data
        request_id = log.get("requestId", "")
        timestamp = log.get("timestamp", "")
        operation = log.get("operation", "")
        model_id = log.get("modelId", "")
        user_message = extract_user_message(log)

        # Extract metrics
        latency_ms = log.get("output", {}).get("outputBodyJson", {}).get("metrics", {}).get("latencyMs")
        input_tokens = (log.get("input", {}).get("inputTokenCount") or
                       log.get("output", {}).get("outputBodyJson", {}).get("usage", {}).get("inputTokens"))
        output_tokens = (log.get("output", {}).get("outputTokenCount") or
                        log.get("output", {}).get("outputBodyJson", {}).get("usage", {}).get("outputTokens"))

        # Create BedrockRequest entity
        request_props = {
            "request_id": request_id,
            "timestamp": timestamp,
            "operation": operation,
            "model_id": model_id
        }

        if user_message:
            request_props["user_message"] = user_message
        if latency_ms:
            request_props["latency_ms"] = latency_ms
        if input_tokens:
            request_props["input_tokens"] = input_tokens
        if output_tokens:
            request_props["output_tokens"] = output_tokens

        request_entity_id = create_entity("BedrockRequest", request_props)
        if request_entity_id:
            stats["requests"] += 1
            request_entities.append((timestamp, request_entity_id))
            print(f"  ✅ Created BedrockRequest entity")
        else:
            print(f"  ❌ Failed to create BedrockRequest")
            continue

        # Create Agent entity (if not exists)
        arn = log.get("identity", {}).get("arn", "")
        if arn and arn not in agent_entities:
            agent_props = {
                "agent_id": arn.split("/")[-1] if "/" in arn else arn,
                "agent_type": "aws_user",
                "arn": arn
            }
            agent_entity_id = create_entity("Agent", agent_props)
            if agent_entity_id:
                agent_entities[arn] = agent_entity_id
                stats["agents"] += 1
                print(f"  ✅ Created Agent entity: {agent_props['agent_id']}")

        # Create MADE_BY relation
        if arn and arn in agent_entities:
            if create_relation("MADE_BY", request_entity_id, agent_entities[arn]):
                stats["relations"] += 1
                print(f"  ✅ Created MADE_BY relation")

        # Extract and create Patient entities
        patient_ids = extract_patient_ids(log)
        for patient_id in patient_ids:
            if patient_id not in patient_entities:
                patient_props = {
                    "patient_id": patient_id,
                    "name": patient_id  # Use ID as name if not available
                }
                patient_entity_id = create_entity("Patient", patient_props)
                if patient_entity_id:
                    patient_entities[patient_id] = patient_entity_id
                    stats["patients"] += 1
                    print(f"  ✅ Created Patient entity: {patient_id}")

            # Create REFERENCES_PATIENT relation
            if patient_id in patient_entities:
                if create_relation("REFERENCES_PATIENT_FROM_REQUEST", request_entity_id, patient_entities[patient_id]):
                    stats["relations"] += 1
                    print(f"  ✅ Created REFERENCES_PATIENT relation")

        # Extract and create ToolUse entities
        tool_uses = extract_tool_uses(log)
        for tool_use in tool_uses:
            tool_entity_id = create_entity("ToolUse", tool_use)
            if tool_entity_id:
                stats["tool_uses"] += 1
                print(f"  ✅ Created ToolUse entity: {tool_use['tool_name']}")

                # Create INVOKED_TOOL relation
                if create_relation("INVOKED_TOOL", request_entity_id, tool_entity_id):
                    stats["relations"] += 1
                    print(f"  ✅ Created INVOKED_TOOL relation")

                # Link tool use to patients
                for patient_id in patient_ids:
                    if patient_id in patient_entities:
                        if create_relation("REFERENCES_PATIENT_FROM_REQUEST", tool_entity_id, patient_entities[patient_id]):
                            stats["relations"] += 1

    # Create sequential FOLLOWED_BY relations between requests
    print(f"\nCreating sequential FOLLOWED_BY relations...")
    request_entities.sort(key=lambda x: x[0])  # Sort by timestamp
    for i in range(len(request_entities) - 1):
        from_id = request_entities[i][1]
        to_id = request_entities[i + 1][1]

        # Calculate time delta
        try:
            from_time = datetime.fromisoformat(request_entities[i][0].replace('Z', '+00:00'))
            to_time = datetime.fromisoformat(request_entities[i + 1][0].replace('Z', '+00:00'))
            time_delta_ms = int((to_time - from_time).total_seconds() * 1000)
        except:
            time_delta_ms = 0

        if create_relation("FOLLOWED_BY", from_id, to_id, {"time_delta_ms": time_delta_ms}):
            stats["relations"] += 1

    return stats


def main():
    print("=" * 80)
    print("VectaDB Bedrock Graph Ingestion")
    print("=" * 80)

    # Check health
    if not check_health():
        print("\nPlease start VectaDB first: cd vectadb && cargo run --release")
        return

    # Check if schema is already loaded
    health = requests.get(f"{VECTADB_URL}/health").json()
    if not health.get('ontology_loaded'):
        # Load and upload schema
        print(f"\nLoading schema from: {SCHEMA_PATH}")
        with open(SCHEMA_PATH, 'r') as f:
            schema = json.load(f)

        if not upload_schema(schema):
            return
    else:
        print(f"⏩ Skipping schema upload (already loaded)")



    # Load logs
    print(f"\nLoading Bedrock logs from: {BEDROCK_LOGS_PATH}")
    with open(BEDROCK_LOGS_PATH, 'r') as f:
        logs = json.load(f)
    print(f"Loaded {len(logs)} log entries")

    # Ingest data
    stats = ingest_bedrock_logs(logs)

    # Print summary
    print("\n" + "=" * 80)
    print("Ingestion Summary")
    print("=" * 80)
    print(f"Entities created:")
    print(f"  - BedrockRequest: {stats['requests']}")
    print(f"  - ToolUse: {stats['tool_uses']}")
    print(f"  - Patient: {stats['patients']}")
    print(f"  - Agent: {stats['agents']}")
    print(f"Total relations: {stats['relations']}")
    print()
    print(f"✅ Data ingestion complete!")
    print(f"🌐 View the graph at: http://localhost:5173/graph")


if __name__ == "__main__":
    main()
