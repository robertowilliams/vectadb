import requests
import json
import time
import random
import os

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
API_HOST = "http://127.0.0.1:5432"
X_API_KEY = "SfE4Vf5jkVQ4v27MrNC72R6H"   

headers = {
    "Content-Type": "application/json",
    "x-api-key": X_API_KEY,
}

print("\n=========== Agent Registry Test Script ===========")

# ---------------------------------------------------------
# Helper function
# ---------------------------------------------------------
def print_step(description):
    print(f"\n🔹 {description}")
    print("--------------------------------------------------")


def pretty(j):
    print(json.dumps(j, indent=2))


# ---------------------------------------------------------
# 1. HEALTH CHECK
# ---------------------------------------------------------
print_step("1) Checking /healthz")
resp = requests.get(f"{API_HOST}/healthz")
pretty(resp.json())


# ---------------------------------------------------------
# 2. CREATE AGENT
# ---------------------------------------------------------
print_step("2) Creating Agent using /agents RPC")

agent_metadata = {
    "role": "Linux security log auditor",
    "goal": "Detect anomalies in Ubuntu logs",
    "backstory": "SRE with deep security experience",
    "description": "Scans syslog and auth.log",
    "expected_output": "JSON anomaly report",
}

payload_agent = {
    "jsonrpc": "2.0",
    "method": "create_id",
    "params": {
        "metadata": agent_metadata
    },
    "id": "1"
}

resp = requests.post(f"{API_HOST}/agents", headers=headers, json=payload_agent)
pretty(resp.json())

agent_id = resp.json()["result"]["id"]
print(f"✔ Created Agent ID: {agent_id}")


# ---------------------------------------------------------
# 3. CREATE TASK (linked to agent)
# ---------------------------------------------------------
print_step("3) Creating Task using /tasks RPC")

task_metadata = {
    "role": "Daily security check",
    "description": "Scan logs for anomalies every 24 hours",
    "expected_output": "Daily anomaly summary"
}

payload_task = {
    "jsonrpc": "2.0",
    "method": "create_id",
    "params": {
        "agent_id": agent_id,
        "metadata": task_metadata
    },
    "id": "1"
}

resp = requests.post(f"{API_HOST}/tasks", headers=headers, json=payload_task)
pretty(resp.json())

task_id = resp.json()["result"]["id"]
print(f"✔ Created Task ID: {task_id}")


# ---------------------------------------------------------
# 4. INGEST LOG
# ---------------------------------------------------------
print_step("4) Sending Log to /logs")

log_payload = {
    "agent_id": agent_id,
    "task_id": task_id,
    "level": "INFO",
    "message": "This is a test log entry from test_registry.py",
    "metadata": {"iteration": random.randint(1, 999)}
}

resp = requests.post(f"{API_HOST}/logs", headers=headers, json=log_payload)
pretty(resp.json())


# ---------------------------------------------------------
# 5. READ FROM COUCHDB
# ---------------------------------------------------------
print_step("5) Reading CouchDB Agents using /couch/agents")

resp = requests.get(f"{API_HOST}/couch/agents", headers=headers)
pretty(resp.json())


print_step("Reading CouchDB Tasks using /couch/tasks")

resp = requests.get(f"{API_HOST}/couch/tasks", headers=headers)
pretty(resp.json())


# ---------------------------------------------------------
# 6. READ FROM WEAVIATE
# ---------------------------------------------------------
print_step("6) Reading Weaviate Agents")

resp = requests.get(f"{API_HOST}/weaviate/agents", headers=headers)
pretty(resp.json())


print_step("Reading Weaviate Tasks")

resp = requests.get(f"{API_HOST}/weaviate/tasks", headers=headers)
pretty(resp.json())


# ---------------------------------------------------------
# 6B. VECTORIZATION TEST (Weaviate)
# ---------------------------------------------------------
print_step("6B) Testing Vectorization on Weaviate objects")

# 1. Fetch raw objects directly from Weaviate REST API with vectors
weaviate_raw = requests.get(
    "http://localhost:8080/v1/objects?include=vector",
    headers={"Authorization": f"Bearer {os.getenv('WEAVIATE_API_KEY', '')}"}
).json()

print("Raw vector-enabled Weaviate response:")
pretty(weaviate_raw)

objects = weaviate_raw.get("objects", [])

if not objects:
    print("❌ No objects returned for vector test. You must first create an agent.")
else:
    # Pick first object
    obj = objects[0]
    vector = obj.get("vector")

    print("\n🔍 Vector length:", len(vector) if vector else "NO VECTOR FOUND")

    if vector and len(vector) > 10:
        print("✔ Vector appears valid (non-empty transformer embedding).")
    else:
        print("❌ Vector missing or too short — transformer model may not be running.")

# 2. Perform an explicit nearText vector search
print("\n🔹 Running nearText similarity search for phrase: 'linux security audit logs'")

payload = {
    "query": f"""
    {{
      Get {{
        {WEAVIATE_CLASS_NAME_AGENT}(
          nearText: {{
            concepts: ["linux security audit logs"]
          }}
          limit: 3
        ) {{
          shortid
          role
          goal
          _additional {{
            distance
            id
          }}
        }}
      }}
    }}
    """
}

resp = requests.post(
    "http://localhost:8080/v1/graphql",
    headers={"Authorization": f"Bearer {os.getenv('WEAVIATE_API_KEY', '')}"},
    json=payload
)

print("\nSimilarity search result:")
pretty(resp.json())

try:
    items = resp.json()["data"][WEAVIATE_CLASS_NAME_AGENT]
    if items:
        d = items[0]["_additional"]["distance"]
        sim = 1 - d
        print(f"\nDistance: {d}, Similarity: {sim}")
        print("✔ nearText vector search working.")
    else:
        print("❌ nearText returned no results.")
except Exception as e:
    print("❌ Error parsing nearText response:", e)



# ---------------------------------------------------------
# 7. READ FROM NEO4J
# ---------------------------------------------------------
print_step("7) Reading Neo4j Agent Nodes")

resp = requests.get(f"{API_HOST}/neo4j/agents", headers=headers)
pretty(resp.json())


print_step("Reading Neo4j Task Nodes")

resp = requests.get(f"{API_HOST}/neo4j/tasks", headers=headers)
pretty(resp.json())


# ---------------------------------------------------------
# 8. SCRAPE METRICS
# ---------------------------------------------------------
print_step("8) Scraping Prometheus /metrics")

resp = requests.get(f"{API_HOST}/metrics")
print(resp.text[:500] + "\n...\n")


print("\n=========== TEST COMPLETE ===========\n")
