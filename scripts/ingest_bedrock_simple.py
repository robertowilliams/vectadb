#!/usr/bin/env python3
"""
Simple Bedrock log ingestion - creates entities without schema validation
"""

import json
import requests
import re
from datetime import datetime
from typing import List, Dict, Any

VECTADB_URL = "http://localhost:8080"
BEDROCK_LOGS_PATH = "test/bedrock_chain_of_thought_logs.json"


print("=" * 80)
print("VectaDB Simple Bedrock Ingestion (No Schema)")
print("=" * 80)

# Load logs
print(f"\nLoading Bedrock logs from: {BEDROCK_LOGS_PATH}")
with open(BEDROCK_LOGS_PATH, 'r') as f:
    logs = json.load(f)
print(f"Loaded {len(logs)} log entries")

stats = {
    "requests": 0,
    "agents": 0,
    "patients": 0,
    "relations": 0
}

agent_entities = {}
patient_entities = {}
request_entities = []

print(f"\nProcessing first 5 log entries as a test...")

for idx, log in enumerate(logs[:5], 1):
    print(f"\n[{idx}/5] Processing request...")

    # Extract data
    request_id = log.get("requestId", "")[:12]
    timestamp = log.get("timestamp", "")
    operation = log.get("operation", "")
    model_id = log.get("modelId", "").split(":")[0] if ":" in log.get("modelId", "") else log.get("modelId", "")

    # Extract user message
    user_message = ""
    try:
        messages = log.get("input", {}).get("inputBodyJson", {}).get("messages", [])
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", [])
                for item in content:
                    if "text" in item:
                        user_message = item["text"][:200]  # Truncate
                        break
    except:
        pass

    # Create entity
    request_props = {
        "request_id": request_id,
        "timestamp": timestamp,
        "operation": operation,
        "model_id": model_id,
        "user_message": user_message
    }

    print(f"  Creating Request entity: {request_id}")
    print(f"    Message: {user_message[:50]}...")

    response = requests.post(
        f"{VECTADB_URL}/api/v1/entities",
        json={"entity_type": "Request", "properties": request_props}
    )

    if response.status_code == 200:
        entity = response.json()
        request_entity_id = entity["id"]
        request_entities.append((timestamp, request_entity_id))
        stats["requests"] += 1
        print(f"  ✅ Created Request entity: {request_entity_id[:12]}")
    else:
        print(f"  ❌ Failed: {response.status_code} - {response.text[:100]}")
        continue

    # Create Agent entity
    arn = log.get("identity", {}).get("arn", "")
    if arn:
        agent_id = arn.split("/")[-1] if "/" in arn else arn

        if agent_id not in agent_entities:
            agent_props = {"agent_id": agent_id, "arn": arn}

            response = requests.post(
                f"{VECTADB_URL}/api/v1/entities",
                json={"entity_type": "Agent", "properties": agent_props}
            )

            if response.status_code == 200:
                entity = response.json()
                agent_entities[agent_id] = entity["id"]
                stats["agents"] += 1
                print(f"  ✅ Created Agent entity: {agent_id}")

        # Create MADE_BY relation
        response = requests.post(
            f"{VECTADB_URL}/api/v1/relations",
            json={
                "type": "MADE_BY",
                "from_entity_id": request_entity_id,
                "to_entity_id": agent_entities[agent_id],
                "properties": {}
            }
        )

        if response.status_code == 200:
            stats["relations"] += 1
            print(f"  ✅ Created MADE_BY relation")

    # Extract patient IDs
    patient_ids = set()
    if user_message:
        matches = re.findall(r'\b(PAT\d+|patient-\d+)\b', user_message, re.IGNORECASE)
        patient_ids.update(matches)

    # Create Patient entities
    for patient_id in patient_ids:
        if patient_id not in patient_entities:
            patient_props = {"patient_id": patient_id, "name": patient_id}

            response = requests.post(
                f"{VECTADB_URL}/api/v1/entities",
                json={"entity_type": "Patient", "properties": patient_props}
            )

            if response.status_code == 200:
                entity = response.json()
                patient_entities[patient_id] = entity["id"]
                stats["patients"] += 1
                print(f"  ✅ Created Patient entity: {patient_id}")

        # Create REFERENCES relation
        response = requests.post(
            f"{VECTADB_URL}/api/v1/relations",
            json={
                "type": "REFERENCES",
                "from_entity_id": request_entity_id,
                "to_entity_id": patient_entities[patient_id],
                "properties": {}
            }
        )

        if response.status_code == 200:
            stats["relations"] += 1
            print(f"  ✅ Created REFERENCES relation to {patient_id}")

# Create sequential relations
print(f"\nCreating sequential FOLLOWED_BY relations...")
request_entities.sort(key=lambda x: x[0])
for i in range(len(request_entities) - 1):
    response = requests.post(
        f"{VECTADB_URL}/api/v1/relations",
        json={
            "type": "FOLLOWED_BY",
            "from_entity_id": request_entities[i][1],
            "to_entity_id": request_entities[i + 1][1],
            "properties": {}
        }
    )

    if response.status_code == 200:
        stats["relations"] += 1

print("\n" + "=" * 80)
print("Ingestion Summary")
print("=" * 80)
print(f"Entities created:")
print(f"  - Requests: {stats['requests']}")
print(f"  - Patients: {stats['patients']}")
print(f"  - Agents: {stats['agents']}")
print(f"Total relations: {stats['relations']}")
print()
print(f"✅ Data ingestion complete!")
print(f"🌐 View the graph at: http://localhost:5173/graph")
