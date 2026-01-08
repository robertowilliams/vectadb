# main.py - Updated Agent Registry System

# This version consolidates config, logging, DB setup, and FastAPI app init cleanly.
# All core components (CouchDB, Weaviate, Nebula) are initialized once and reused.

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

import os
import json
import time
import threading
import logging
import string
import secrets
import hashlib
import base64

import couchdb
import yaml
import uvicorn
from dotenv import load_dotenv
import weaviate
from weaviate.classes.config import Property, DataType
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config as NebulaConfig

# ---------------------- CONFIG & ENV ----------------------
load_dotenv(dotenv_path=os.path.join("config", ".env"))

REQUIRED_ENV = ["RPC_API_KEY", "COUCH_URL"]
for key in REQUIRED_ENV:
    if not os.getenv(key):
        raise EnvironmentError(f"Missing environment variable: {key}")

RPC_API_KEY = os.getenv("RPC_API_KEY")
COUCH_URL = os.getenv("COUCH_URL")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")

project_root = os.path.dirname(__file__)
with open(os.path.join(project_root, "config", "config.yaml"), "r") as f:
    config = yaml.safe_load(f)

# ---------------------- LOGGING ----------------------
log_path = os.path.join("logs", "system.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent_registry")

# ---------------------- SHORT ID ----------------------
ALPHABET = string.ascii_letters + string.digits

def generate_short_id(length=6, deterministic=False, seed=None):
    if deterministic and seed:
        h = hashlib.sha1(seed.encode()).digest()
        b64 = base64.b64encode(h).decode().replace("+", "A").replace("/", "B").replace("=", "")
        return b64[:length]
    return ''.join(secrets.choice(ALPHABET) for _ in range(length))

# ---------------------- FASTAPI ----------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if weaviate_client:
        weaviate_client.close()
    if nebula_pool:
        nebula_pool.close()

app = FastAPI(title="Agent Registry System", lifespan=lifespan)

# ---------------------- DATABASES ----------------------
# CouchDB
couch = couchdb.Server(COUCH_URL)
COUCH_DB_NAME = config["couch"]["db_name"]
if COUCH_DB_NAME not in couch:
    couch.create(COUCH_DB_NAME)
couch_db = couch[COUCH_DB_NAME]

# Weaviate
weaviate_client = None
try:
    creds = weaviate.auth.AuthApiKey(WEAVIATE_API_KEY) if WEAVIATE_API_KEY else None
    weaviate_client = weaviate.connect_to_local(
        host=config["weaviate"]["host"],
        port=config["weaviate"]["port"],
        auth_credentials=creds
    )
except Exception as e:
    logger.warning(f"Weaviate error: {e}")

# Nebula Graph
nebula_pool: Optional[ConnectionPool] = None
try:
    nebula_conf = NebulaConfig()
    nebula_conf.max_connection_pool_size = 10
    nebula_pool = ConnectionPool()
    if not nebula_pool.init([(config["nebula"]["graphd_host"], config["nebula"]["graphd_port"])], nebula_conf):
        nebula_pool = None
except Exception as e:
    logger.warning(f"Nebula init error: {e}")

# ---------------------- MODELS ----------------------
class AgentRequest(BaseModel):
    method: str = "create_id"
    params: Optional[Dict[str, Any]] = {
        "metadata": {
            "role": "Data Analyst",
            "goal": "Analyze user behavior",
            "backstory": "Trained on anonymized e-commerce clickstream data",
            "description": "Agent capable of identifying user trends",
            "expected_output": "User segmentation report",
            "agent": "analytics-agent"
        },
        "deterministic": True,
        "length": 8,
        "seed": "agent-seed-2025"
    }
    id: str = "1"

class TaskRequest(BaseModel):
    method: str = "create_id"
    params: Optional[Dict[str, Any]] = {
        "agent_id": "abc12345",
        "metadata": {
            "role": "Task Runner",
            "goal": "Execute preprocessing",
            "backstory": "Configured for batch data cleaning",
            "description": "Runs data normalization routines",
            "expected_output": "Cleaned dataset",
            "agent": "cleaner-task"
        },
        "deterministic": False,
        "length": 10
    }
    id: str = "1"

# ---------------------- AUTH ----------------------
def authenticate_request(x_api_key: str = Header(...)):
    if x_api_key != RPC_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ---------------------- ENDPOINTS ----------------------
@app.post("/agents")
async def rpc_agents(body: AgentRequest, x_api_key: str = Header(...)):
    authenticate_request(x_api_key)
    return await handle_json_rpc(body, is_task=False)

@app.post("/tasks")
async def rpc_tasks(body: TaskRequest, x_api_key: str = Header(...)):
    authenticate_request(x_api_key)
    return await handle_json_rpc(body, is_task=True)

@app.get("/healthz")
async def health():
    result = {
        "status": "ok",
        "retry_queue": len(retry_queue),
    }

    def safe_check(name, func):
        start = perf_counter()
        try:
            value = func()
            result[name] = value
        except Exception as e:
            result[name] = False
            result[f"{name}_error"] = str(e)
            logger.warning(f"[HEALTHZ] {name} check failed: {e}")
        finally:
            result[f"{name}_latency_ms"] = round((perf_counter() - start) * 1000, 2)

    # CouchDB
    safe_check(
        "couchdb", 
        lambda: bool(couch_db and couch_db.info())
    )

    # Weaviate
    safe_check(
        "weaviate",
        lambda: client is not None and client.is_ready()
    )

    # Nebula
    def check_nebula():
        if nebula_pool:
            with nebula_pool.session_context(NEBULA_USER, NEBULA_PASSWORD) as session:
                res = session.execute(f"USE {NEBULA_SPACE};")
                return res.is_succeeded()
        return False

    safe_check("nebula", check_nebula)

    return result

# ---------------------- JSON-RPC HANDLER ----------------------
async def handle_json_rpc(body: BaseModel, is_task: bool):
    if body.method != "create_id":
        return JSONResponse(status_code=400, content={"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": body.id})

    params = body.params or {}
    uid = generate_short_id(
        params.get("length", 6),
        params.get("deterministic", False),
        params.get("seed")
    )
    record = {
        "id": uid,
        "created_at": datetime.utcnow().isoformat(),
        "metadata": params.get("metadata", {}) or {}
    }
    couch_db.save(record)

    try:
        if weaviate_client:
            collection = config["weaviate"]["class_name_task"] if is_task else config["weaviate"]["class_name_agent"]
            coll = weaviate_client.collections.get(collection)
            coll.data.insert(properties={"shortid": uid, "metadata": json.dumps(record["metadata"])})
    except Exception as e:
        logger.warning(f"Weaviate insert failed: {e}")

    return JSONResponse({"jsonrpc": "2.0", "result": {"status": "ok", "id": uid}, "id": body.id})


# ---------------------- MAIN ----------------------
if __name__ == "__main__":
    uvicorn.run(app, host=config["server"]["host"], port=config["server"]["port"])
