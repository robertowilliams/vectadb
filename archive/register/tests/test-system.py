#!/usr/bin/env python3
"""
Agent Registry PoC End-to-End Tester

Usage:
    export AGENT_REGISTRY_URL="http://localhost:8000"
    export RPC_API_KEY="your-secret-here"

    python test_agent_registry_poc.py
"""

import os
import sys
import json
import time
import textwrap
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List

import requests


AGENT_REGISTRY_URL = os.getenv("AGENT_REGISTRY_URL", "http://localhost:5432")
RPC_API_KEY = os.getenv("RPC_API_KEY", "SfE4Vf5jkVQ4v27MrNC72R6H")


@dataclass
class StepResult:
    name: str
    success: bool
    detail: str = ""
    data: Optional[Dict[str, Any]] = None


def error(msg: str):
    print(msg, file=sys.stderr)


def safe_request(method: str, path: str, **kwargs) -> requests.Response:
    url = f"{AGENT_REGISTRY_URL.rstrip('/')}{path}"
    return requests.request(method, url, timeout=10, **kwargs)


def test_health() -> StepResult:
    try:
        resp = safe_request("GET", "/healthz")
        body = resp.json()
        ok = resp.status_code == 200 and body.get("status") == "ok"
        return StepResult(
            name="healthz",
            success=ok,
            detail=f"HTTP {resp.status_code}, body={body}",
            data=body,
        )
    except Exception as e:
        return StepResult("healthz", False, detail=str(e))


def create_agent(headers: Dict[str, str]) -> StepResult:
    try:
        payload = {
            "method": "create_id",
            "params": {
                "metadata": {
                    "role": "log-audit-agent",
                    "goal": "Analyze logs for anomalies",
                    "backstory": "PoC agent created by test script",
                    "description": "E2E test agent",
                    "expected_output": "Anomaly report",
                }
            },
            "id": "1",
        }
        resp = safe_request("POST", "/agents", json=payload, headers=headers)
        body = resp.json()
        ok = (
            resp.status_code == 200
            and "result" in body
            and body["result"].get("status") == "ok"
        )
        if not ok:
            return StepResult(
                name="create_agent",
                success=False,
                detail=f"HTTP {resp.status_code}, body={body}",
                data=body,
            )
        agent_id = body["result"]["id"]
        return StepResult(
            name="create_agent",
            success=True,
            detail=f"Agent created with id={agent_id}",
            data={"agent_id": agent_id, "raw": body},
        )
    except Exception as e:
        return StepResult("create_agent", False, detail=str(e))


def create_task(headers: Dict[str, str], agent_id: str) -> StepResult:
    try:
        payload = {
            "method": "create_id",
            "params": {
                "agent_id": agent_id,
                "metadata": {
                    "description": "Audit logs for anomalies in PoC",
                    "expected_output": "List of anomalies with scores",
                },
            },
            "id": "1",
        }
        resp = safe_request("POST", "/tasks", json=payload, headers=headers)
        body = resp.json()
        ok = (
            resp.status_code == 200
            and "result" in body
            and body["result"].get("status") == "ok"
        )
        if not ok:
            return StepResult(
                name="create_task",
                success=False,
                detail=f"HTTP {resp.status_code}, body={body}",
                data=body,
            )
        task_id = body["result"]["id"]
        return StepResult(
            name="create_task",
            success=True,
            detail=f"Task created with id={task_id} for agent={agent_id}",
            data={"task_id": task_id, "raw": body},
        )
    except Exception as e:
        return StepResult("create_task", False, detail=str(e))


def send_log(
    headers: Dict[str, str],
    agent_id: str,
    task_id: Optional[str],
    level: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> StepResult:
    try:
        body = {
            "agent_id": agent_id,
            "task_id": task_id,
            "level": level,
            "message": message,
            "metadata": metadata or {},
        }
        resp = safe_request("POST", "/logs", json=body, headers=headers)
        j = resp.json()
        ok = resp.status_code == 200 and j.get("status") == "ok"
        if not ok:
            return StepResult(
                name=f"send_log_{level}",
                success=False,
                detail=f"HTTP {resp.status_code}, body={j}",
                data=j,
            )
        log_id = j.get("log_id")
        return StepResult(
            name=f"send_log_{level}",
            success=True,
            detail=f"{level} log sent with id={log_id}",
            data={"log_id": log_id, "raw": j},
        )
    except Exception as e:
        return StepResult(f"send_log_{level}", False, detail=str(e))


def verify_couch_for_logs(
    headers: Dict[str, str],
    log_ids: List[str],
) -> StepResult:
    try:
        resp = safe_request(
            "GET",
            "/couch/all",
            params={"limit": 500},
            headers=headers,
        )
        body = resp.json()
        docs = body.get("items", [])
        found = {lid: False for lid in log_ids}

        for doc in docs:
            _id = doc.get("_id")
            if _id in found:
                found[_id] = True

        missing = [lid for lid, ok in found.items() if not ok]
        if missing:
            return StepResult(
                name="verify_couch_logs",
                success=False,
                detail=f"Missing logs in CouchDB: {missing}",
                data={"found": found, "total_docs_scanned": len(docs)},
            )
        return StepResult(
            name="verify_couch_logs",
            success=True,
            detail=f"All logs present in CouchDB. Scanned {len(docs)} docs.",
            data={"found": found},
        )
    except Exception as e:
        return StepResult("verify_couch_logs", False, detail=str(e))


def verify_metrics(agent_id: str) -> StepResult:
    try:
        resp = safe_request("GET", "/metrics")
        text = resp.text
        # very simple check: metric lines exist for this agent
        logs_line = f'agent_logs_total{{agent="{agent_id}"}}'
        errors_line = f'agent_errors_total{{agent="{agent_id}"}}'

        logs_present = logs_line in text
        errors_present = errors_line in text

        detail_parts = []
        if logs_present:
            detail_parts.append("agent_logs_total line found")
        else:
            detail_parts.append("agent_logs_total line NOT found")
        if errors_present:
            detail_parts.append("agent_errors_total line found")
        else:
            detail_parts.append("agent_errors_total line NOT found")

        return StepResult(
            name="verify_metrics",
            success=logs_present,  # at least logs_total must be there
            detail="; ".join(detail_parts),
        )
    except Exception as e:
        return StepResult("verify_metrics", False, detail=str(e))


def print_report(results: List[StepResult]):
    print("\n=== Agent Registry PoC Test Report ===\n")
    overall_ok = all(r.success for r in results)
    for r in results:
        status = "OK" if r.success else "FAIL"
        print(f"[{status:4}] {r.name}")
        if r.detail:
            wrapped = textwrap.fill(r.detail, width=90)
            for line in wrapped.splitlines():
                print(f"       {line}")
        print()

    print("Overall result:", "SUCCESS ✅" if overall_ok else "FAIL ❌")

    summary = {
        "overall_success": overall_ok,
        "steps": [asdict(r) for r in results],
    }
    print("\n--- JSON summary (copy/paste into notebook or logs) ---")
    print(json.dumps(summary, indent=2))


def main():
    if not RPC_API_KEY:
        error("ERROR: RPC_API_KEY environment variable is not set.")
        sys.exit(1)

    print(f"Using AGENT_REGISTRY_URL={AGENT_REGISTRY_URL}")
    print("Running Agent Registry PoC tests...\n")

    headers = {"x-api-key": RPC_API_KEY}
    results: List[StepResult] = []

    # 1. healthz
    r_health = test_health()
    results.append(r_health)
    if not r_health.success:
        print_report(results)
        sys.exit(1)

    # 2. create agent
    r_agent = create_agent(headers)
    results.append(r_agent)
    if not r_agent.success:
        print_report(results)
        sys.exit(1)
    agent_id = r_agent.data["agent_id"]

    # 3. create task
    r_task = create_task(headers, agent_id)
    results.append(r_task)
    if not r_task.success:
        print_report(results)
        sys.exit(1)
    task_id = r_task.data["task_id"]

    # 4. send INFO log
    r_log_info = send_log(
        headers=headers,
        agent_id=agent_id,
        task_id=task_id,
        level="INFO",
        message="PoC INFO log from test script",
        metadata={"phase": "test", "kind": "info"},
    )
    results.append(r_log_info)

    # 5. send ERROR log
    r_log_err = send_log(
        headers=headers,
        agent_id=agent_id,
        task_id=task_id,
        level="ERROR",
        message="PoC ERROR log from test script",
        metadata={"phase": "test", "kind": "error"},
    )
    results.append(r_log_err)

    log_ids = []
    if r_log_info.success and r_log_info.data:
        log_ids.append(r_log_info.data["log_id"])
    if r_log_err.success and r_log_err.data:
        log_ids.append(r_log_err.data["log_id"])

    # 6. verify CouchDB logs (best effort)
    if log_ids:
        r_couch = verify_couch_for_logs(headers, log_ids)
        results.append(r_couch)
    else:
        results.append(
            StepResult(
                name="verify_couch_logs",
                success=False,
                detail="No log_ids to verify (log creation failed earlier).",
            )
        )

    # 7. verify metrics (best effort)
    r_metrics = verify_metrics(agent_id)
    results.append(r_metrics)

    # Final report
    print_report(results)


if __name__ == "__main__":
    main()
