#!/usr/bin/env python3
"""
nebula_diagnostic_report.py

Run a comprehensive diagnostic against a Nebula Graph cluster and
generate a PDF report with the results.

Usage:
    python nebula_diagnostic_report.py

Adjust the CONFIG section below for your environment.
"""

import os
import sys
import traceback
from datetime import datetime

from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config as NebulaConfig
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

# ============================
# CONFIG – ADJUST AS NEEDED
# ============================

NEBULA_HOST = "127.0.0.1"
NEBULA_PORT = 9669
NEBULA_USER = "root"
NEBULA_PASSWORD = "nebula"

# Space used for testing. Will be created if it doesn't exist.
TEST_SPACE = "agent_registry_diag"

# DDL test objects (kept simple)
TAG_PERSON = "Person"
EDGE_KNOWS = "Knows"


# ============================
# HELPER FUNCTIONS
# ============================

def value_to_str(v):
    """Convert Nebula Value to a safe string representation."""
    try:
        if hasattr(v, "is_string") and v.is_string():
            return v.as_string()
        if hasattr(v, "is_int") and v.is_int():
            return str(v.as_int())
        if hasattr(v, "is_bool") and v.is_bool():
            return str(v.as_bool())
        if hasattr(v, "is_double") and v.is_double():
            return str(v.as_double())
        if hasattr(v, "is_time") and v.is_time():
            return str(v.as_time())
        if hasattr(v, "is_date") and v.is_date():
            return str(v.as_date())
        if hasattr(v, "is_datetime") and v.is_datetime():
            return str(v.as_datetime())
    except Exception:
        pass
    # Fallback
    return str(v)


def run_query(session, nql, description="", record_rows=True, max_rows=20):
    """
    Execute a single nGQL query and capture metadata + rows.
    Returns a dict with keys:
      - description, nql, succeeded, error, latency_ms, rows, keys
    """
    result = {
        "description": description,
        "nql": nql,
        "succeeded": False,
        "error": None,
        "latency_ms": None,
        "rows": [],
        "keys": [],
    }

    try:
        res = session.execute(nql)
        result["latency_ms"] = getattr(res, "latency", None)
        if not res.is_succeeded():
            result["error"] = res.error_msg()
            return result

        result["succeeded"] = True
        result["keys"] = res.keys()

        if record_rows:
            rows = []
            for i, row in enumerate(res.rows()):
                if i >= max_rows:
                    break
                rows.append([value_to_str(v) for v in row.values])
            result["rows"] = rows

    except Exception as e:
        result["error"] = f"{e.__class__.__name__}: {e}"
    return result


# ============================
# MAIN DIAGNOSTIC LOGIC
# ============================

def run_diagnostics():
    """
    Runs the diagnostic suite and returns a big dict with:
      - meta info
      - connection status
      - queries (SHOW HOSTS, SHOW SPACES, DDL, DML, MATCH, etc.)
    """
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "config": {
            "host": NEBULA_HOST,
            "port": NEBULA_PORT,
            "user": NEBULA_USER,
            "space": TEST_SPACE,
        },
        "connection": {
            "pool_init": False,
            "error": None,
        },
        "steps": [],
    }

    conf = NebulaConfig()
    conf.max_connection_pool_size = 5
    pool = ConnectionPool()

    try:
        ok = pool.init([(NEBULA_HOST, NEBULA_PORT)], conf)
    except Exception as e:
        report["connection"]["pool_init"] = False
        report["connection"]["error"] = f"{e.__class__.__name__}: {e}"
        return report

    report["connection"]["pool_init"] = ok
    if not ok:
        report["connection"]["error"] = "pool.init returned False"
        return report

    try:
        with pool.session_context(NEBULA_USER, NEBULA_PASSWORD) as session:
            # 1) SHOW HOSTS
            report["steps"].append(
                run_query(
                    session,
                    "SHOW HOSTS;",
                    description="Cluster hosts status (meta + storage)",
                )
            )

            # 2) SHOW SPACES
            report["steps"].append(
                run_query(
                    session,
                    "SHOW SPACES;",
                    description="List existing spaces",
                )
            )

            # 3) CREATE TEST SPACE
            create_space_nql = (
                f"CREATE SPACE IF NOT EXISTS {TEST_SPACE}("
                "partition_num=16, replica_factor=1, vid_type=FIXED_STRING(64));"
            )
            report["steps"].append(
                run_query(
                    session,
                    create_space_nql,
                    description=f"Create test space `{TEST_SPACE}` if not exists",
                    record_rows=False,
                )
            )

            # 4) USE TEST SPACE
            report["steps"].append(
                run_query(
                    session,
                    f"USE {TEST_SPACE};",
                    description=f"Switch to space `{TEST_SPACE}`",
                    record_rows=False,
                )
            )

            # If USE failed, further queries in this space will also fail; but we still run
            # them to capture error messages in report.

            # 5) CREATE TAG & EDGE
            ddl_person = f"CREATE TAG IF NOT EXISTS {TAG_PERSON}(name string, age int);"
            ddl_knows = f"CREATE EDGE IF NOT EXISTS {EDGE_KNOWS}(since int);"

            report["steps"].append(
                run_query(
                    session,
                    ddl_person,
                    description=f"Create TAG `{TAG_PERSON}`",
                    record_rows=False,
                )
            )
            report["steps"].append(
                run_query(
                    session,
                    ddl_knows,
                    description=f"Create EDGE `{EDGE_KNOWS}`",
                    record_rows=False,
                )
            )

            # 6) SHOW TAGS / EDGES
            report["steps"].append(
                run_query(
                    session,
                    "SHOW TAGS;",
                    description="List tags in test space",
                )
            )
            report["steps"].append(
                run_query(
                    session,
                    "SHOW EDGES;",
                    description="List edges in test space",
                )
            )

            # 7) Insert some test vertices and edges
            insert_vertices = (
                f'INSERT VERTEX {TAG_PERSON}(name, age) VALUES '
                '"alice":("Alice", 30), '
                '"bob":("Bob", 28);'
            )
            insert_edge = (
                f'INSERT EDGE {EDGE_KNOWS}(since) VALUES '
                '"alice"->"bob":(2020);'
            )

            report["steps"].append(
                run_query(
                    session,
                    insert_vertices,
                    description="Insert sample Person vertices (alice, bob)",
                    record_rows=False,
                )
            )
            report["steps"].append(
                run_query(
                    session,
                    insert_edge,
                    description="Insert sample Knows edge (alice -> bob)",
                    record_rows=False,
                )
            )

            # 8) Simple MATCH query
            match_query = (
                f'MATCH (a:{TAG_PERSON})-[:{EDGE_KNOWS}]->(b:{TAG_PERSON}) '
                'RETURN a.name, a.age, b.name, b.age, edge.since;'
            )
            report["steps"].append(
                run_query(
                    session,
                    match_query,
                    description="MATCH query over Person-Knows-Person",
                )
            )

            # 9) Stats query (optional)
            report["steps"].append(
                run_query(
                    session,
                    "SHOW STATS;",
                    description="Basic stats overview (if enabled for this version)",
                )
            )

    except Exception as e:
        # Capture any unexpected high-level errors in steps
        exc_info = traceback.format_exc()
        report["steps"].append(
            {
                "description": "Unexpected error in diagnostic session",
                "nql": None,
                "succeeded": False,
                "error": f"{e.__class__.__name__}: {e}",
                "latency_ms": None,
                "rows": [exc_info.splitlines()],
                "keys": [],
            }
        )

    return report


# ============================
# PDF GENERATION
# ============================

def render_report_to_pdf(report, output_path):
    """
    Render the diagnostic report dict to a simple PDF using reportlab.
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    margin = 2 * cm
    text_width = width - 2 * margin
    y = height - margin

    def draw_heading(text, size=16, underline=False):
        nonlocal y
        c.setFont("Helvetica-Bold", size)
        c.drawString(margin, y, text)
        y -= 0.6 * cm
        if underline:
            c.line(margin, y, margin + text_width, y)
            y -= 0.3 * cm

    def draw_text(text, size=10):
        """
        Draw multi-line text with wrapping; adds new pages if needed.
        """
        nonlocal y
        c.setFont("Helvetica", size)
        lines = []
        for logical_line in text.splitlines():
            if len(logical_line) * size * 0.5 < text_width:
                lines.append(logical_line)
            else:
                # naive wrap
                chunk_size = max(int(text_width / (size * 0.5)), 1)
                for i in range(0, len(logical_line), chunk_size):
                    lines.append(logical_line[i:i + chunk_size])

        for line in lines:
            if y < margin:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", size)
            c.drawString(margin, y, line)
            y -= 0.4 * cm

    # Title
    draw_heading("Nebula Graph Diagnostic Report", size=18, underline=True)
    draw_text(f"Generated at (UTC): {report['generated_at']}")
    cfg = report["config"]
    draw_text(
        f"Target: {cfg['host']}:{cfg['port']}  |  User: {cfg['user']}  |  Test space: {cfg['space']}"
    )
    y -= 0.5 * cm

    # Connection section
    draw_heading("1. Connection", size=14)
    conn = report["connection"]
    if conn["pool_init"]:
        draw_text("Connection pool: OK")
    else:
        draw_text("Connection pool: FAILED")
        draw_text(f"Error: {conn['error']}")
        c.showPage()
        c.save()
        return

    if conn["error"]:
        draw_text(f"Warnings: {conn['error']}")
    y -= 0.3 * cm

    # Steps summary
    draw_heading("2. Diagnostic Steps", size=14)
    successes = sum(1 for s in report["steps"] if s.get("succeeded"))
    total = len(report["steps"])
    draw_text(f"Queries succeeded: {successes}/{total}")
    y -= 0.4 * cm

    # Each step
    step_no = 1
    for step in report["steps"]:
        desc = step.get("description") or "(no description)"
        succeeded = step.get("succeeded", False)
        status = "OK" if succeeded else "FAILED"
        latency = step.get("latency_ms")
        nql = step.get("nql")
        error = step.get("error")
        keys = step.get("keys", [])
        rows = step.get("rows", [])

        draw_heading(f"Step {step_no}: {desc}", size=12)
        line = f"Status: {status}"
        if latency is not None:
            line += f" | Latency: {latency} ms"
        draw_text(line)

        if nql:
            draw_text("Query:")
            draw_text(f"  {nql}")

        if error:
            draw_text("Error:")
            draw_text(f"  {error}")

        if rows:
            draw_text("Rows (up to first 20):")
            # format rows as simple columns
            if keys:
                draw_text("  " + " | ".join(keys))
            for r in rows:
                if isinstance(r, list):
                    draw_text("  " + " | ".join(r))
                else:
                    draw_text("  " + str(r))

        y -= 0.4 * cm
        step_no += 1

    c.showPage()
    c.save()


# ============================
# ENTRYPOINT
# ============================

def main():
    print("Running Nebula Graph diagnostics...")
    report = run_diagnostics()

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_name = f"nebula_diagnostic_report_{timestamp}.pdf"
    output_path = os.path.join(os.getcwd(), output_name)

    print(f"Generating PDF report: {output_path}")
    try:
        render_report_to_pdf(report, output_path)
        print("Done.")
        print(f"Report saved at: {output_path}")
    except Exception as e:
        print("Failed to render PDF:", e, file=sys.stderr)
        traceback.print_exc()


if __name__ == "__main__":
    main()
