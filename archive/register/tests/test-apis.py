#!/usr/bin/env python
"""
Test script for Agent Registry:

- Create one Agent
- Create three Tasks linked to that Agent
- Run similarity search on tasks and agents
- Generate a .txt report with the results
"""

import os
import datetime as dt
import textwrap
from pathlib import Path

import requests
from dotenv import load_dotenv


# -------------------------------------------------------------------
# 1. Environment / config
# -------------------------------------------------------------------

# Project root: tests/..  -> register/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load the same .env used by main.py: register/config/.env
env_path = PROJECT_ROOT / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback: normal .env loading if you want
    load_dotenv()

def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val

BASE_URL = os.getenv("AGENT_REGISTRY_URL", "http://localhost:5432")
RPC_API_KEY = require_env("RPC_API_KEY")

HEADERS = {"x-api-key": RPC_API_KEY}


# -------------------------------------------------------------------
# 2. HTTP helpers
# -------------------------------------------------------------------

def post_json(path: str, payload: dict) -> dict:
    url = f"{BASE_URL}{path}"
    resp = requests.post(url, headers=HEADERS, json=payload)
    if not resp.ok:
        raise RuntimeError(f"POST {url} failed: {resp.status_code} {resp.text}")
    return resp.json()


def get_json(path: str, params: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, headers=HEADERS, params=params or {})
    if not resp.ok:
        raise RuntimeError(f"GET {url} failed: {resp.status_code} {resp.text}")
    return resp.json()


# -------------------------------------------------------------------
# 3. Registry operations
# -------------------------------------------------------------------

def create_agent(metadata: dict) -> tuple[str, list[dict]]:
    payload = {
        "method": "create_id",
        "params": {
            "length": 6,
            "deterministic": False,
            "metadata": metadata,
        },
        "id": "1",
    }
    data = post_json("/agents", payload)
    result = data.get("result", {})
    agent_id = result.get("id")
    if not agent_id:
        raise RuntimeError(f"Unexpected /agents response: {data}")
    similar_agents = result.get("similar_agents", []) or []
    return agent_id, similar_agents


def create_task(agent_id: str, metadata: dict) -> str:
    payload = {
        "method": "create_id",
        "params": {
            "agent_id": agent_id,
            "length": 6,
            "deterministic": False,
            "metadata": metadata,
        },
        "id": "1",
    }
    data = post_json("/tasks", payload)
    result = data.get("result", {})
    task_id = result.get("id")
    if not task_id:
        raise RuntimeError(f"Unexpected /tasks response: {data}")
    return task_id


def find_similar_tasks(task_id: str, threshold: float = 0.0, limit: int = 10) -> list[dict]:
    params = {"task_id": task_id, "threshold": threshold, "limit": limit}
    data = get_json("/similar/tasks", params=params)
    return data.get("items", []) or []


def find_similar_agents(agent_id: str, threshold: float = 0.0, limit: int = 10) -> list[dict]:
    params = {"agent_id": agent_id, "threshold": threshold, "limit": limit}
    data = get_json("/similar/agents", params=params)
    return data.get("items", []) or []


# -------------------------------------------------------------------
# 4. Main logic + report
# -------------------------------------------------------------------

def main():
    now = dt.datetime.utcnow()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"Using base URL: {BASE_URL}")
    print(f"Script started at {now_str}")

    report_lines: list[str] = []
    report_lines.append(f"Agent Registry test report - {now_str}")
    report_lines.append(f"Base URL: {BASE_URL}")
    report_lines.append("")

    # --- Create Agent ---
    agent_meta = {
        "role": "Network Troubleshooting Support Agent",
        "goal": "Help diagnose issues in multi-agent / crew executions",
        "backstory": textwrap.dedent(
            """
            This agent is part of an auditing and observability system.
            It explains how agents, tasks, tracing and similarity search
            work inside the Agent Registry.
            """
        ).strip(),
    }

    print("\n=== Creating Agent ===")
    agent_id, similar_agents_from_creation = create_agent(agent_meta)
    print(f"Created Agent ID: {agent_id}")

    report_lines.append("=== Agent Created ===")
    report_lines.append(f"Agent ID: {agent_id}")
    report_lines.append("Agent metadata:")
    for k, v in agent_meta.items():
        report_lines.append(f"  {k}: {v}")
    report_lines.append("")

    if similar_agents_from_creation:
        print("Similar agents at creation:")
        report_lines.append("Similar agents (from /agents create_id):")
        for s in similar_agents_from_creation:
            sid = s.get("shortid")
            sim = s.get("similarity")
            report_lines.append(f"  - {sid} (similarity={sim:.3f})")
            print(f"  - {sid} (similarity={sim:.3f})")
    else:
        print("No similar agents found at creation.")
        report_lines.append("Similar agents (from /agents create_id): none")
    report_lines.append("")

    # --- Create 3 Tasks ---
    print("\n=== Creating 3 Tasks for this Agent ===")
    report_lines.append("=== Tasks Created ===")

    task_metadatas = [
        {
            "description": "Analyze CrewAI execution logs and highlight potential failures.",
            "expected_output": "A summarized list of failures and warnings from the logs.",
        },
        {
            "description": "Detect anomalous patterns in agent interactions using embeddings.",
            "expected_output": "A report with anomalies and suggested investigations.",
        },
        {
            "description": "Summarize recent CrewAI traces and suggest improvements.",
            "expected_output": "A concise summary of traces and recommendations.",
        },
    ]

    task_ids: list[str] = []
    for i, meta in enumerate(task_metadatas, start=1):
        tid = create_task(agent_id, meta)
        task_ids.append(tid)
        print(f"Task {i} created with ID: {tid}")
        report_lines.append(f"Task {i} ID: {tid}")
        for k, v in meta.items():
            report_lines.append(f"  {k}: {v}")
        report_lines.append("")
    report_lines.append("")

    # --- Similar tasks (using first task as reference) ---
    print("\n=== Similar Tasks to Task 1 ===")
    report_lines.append("=== Similar Tasks ===")

    if task_ids:
        base_task_id = task_ids[0]
        similar_tasks = find_similar_tasks(base_task_id, threshold=0.0, limit=10)
        if not similar_tasks:
            print("No similar tasks found.")
            report_lines.append("No similar tasks found.")
        else:
            print(f"Similar tasks to {base_task_id}:")
            report_lines.append(f"Base Task ID: {base_task_id}")
            for t in similar_tasks:
                sid = t.get("shortid")
                sim = t.get("similarity")
                meta = t.get("metadata", {}) or {}
                desc = meta.get("description", "(no description)")
                short_desc = textwrap.shorten(desc, width=80)
                print(f"  - {sid}: similarity={sim:.3f}, description={short_desc}")
                report_lines.append(
                    f"  - {sid}: similarity={sim:.3f}, description={desc}"
                )
    report_lines.append("")

    # --- Similar agents ---
    print("\n=== Similar Agents ===")
    report_lines.append("=== Similar Agents ===")

    similar_agents = find_similar_agents(agent_id, threshold=0.0, limit=10)
    if not similar_agents:
        print("No similar agents found.")
        report_lines.append("No similar agents found.")
    else:
        print(f"Agents similar to {agent_id}:")
        for a in similar_agents:
            sid = a.get("shortid")
            sim = a.get("similarity")
            role = a.get("role")
            print(f"  - {sid}: similarity={sim:.3f}, role={role!r}")
            report_lines.append(
                f"  - {sid}: similarity={sim:.3f}, role={role!r}"
            )

    # --- Write report ---
    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_filename = reports_dir / f"agent_registry_report_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    report_text = "\n".join(report_lines)
    report_filename.write_text(report_text, encoding="utf-8")

    print(f"\nReport written to: {report_filename}")


if __name__ == "__main__":
    main()
