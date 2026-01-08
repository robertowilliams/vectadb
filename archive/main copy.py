# main.py
# ShortID service using CouchDB and Weaviate, updated for new config structure

import os
import json
import time
import logging
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from pydantic import BaseModel

from dotenv import load_dotenv
import yaml
import string, secrets, hashlib, base64

import couchdb
import weaviate
from weaviate.classes.config import Property, DataType

# ---------------------------------------------------------------
# CONFIG LOADER
# ---------------------------------------------------------------

def load_config(config_path=None, env_path=None):
    project_root = os.path.abspath(os.path.dirname(__file__))
    config_path = config_path or os.path.join(project_root, "config", "config.yaml")
    env_path = env_path or os.path.join(os.path.dirname(__file__), "config", ".env")

    print(f"[load_config] Project root: {project_root}")
    print(f"[load_config] Config file: {config_path}")
    print(f"[load_config] Env file: {env_path}")

    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        print(f"[load_config] Warning: .env file missing: {env_path}")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Missing config.yaml at {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config

# ---------------------------------------------------------------
# SHORT-ID GENERATOR
# ---------------------------------------------------------------

ALPHABET = string.ascii_letters + string.digits

def generate_short_id(length=6, deterministic=False, seed=None):
    if deterministic:
        if not seed:
            raise ValueError("Seed is required for deterministic mode.")
        h = hashlib.sha1(seed.encode()).digest()
        b64 = base64.b64encode(h).decode().replace("+", "A").replace("/", "B").replace("=", "")
        return b64[:length]
    return "".join(secrets.choice(ALPHABET) for _ in range(length))

# ---------------------------------------------------------------
# LOGGING SETUP
# ---------------------------------------------------------------

LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "shortid.log")

logger = logging.getLogger("shortid")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)

# ---------------------------------------------------------------
# LOAD CONFIG & ENV
# ---------------------------------------------------------------

load_dotenv(os.path.join(os.path.dirname(__file__), "config", ".env"))
RPC_API_KEY = os.getenv("RPC_API_KEY")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
COUCH_URL = os.getenv("COUCH_URL")

if not RPC_API_KEY:
    raise ValueError("RPC_API_KEY missing from .env")
if not COUCH_URL:
    raise ValueError("COUCH_URL missing from .env")

config = load_config()
HOST = config["server"]["host"]
PORT = config["server"]["port"]

# Couch config
COUCH_DB_NAME = config["couch"]["db_name"]
COUCH_AGENT_COLLECTION = config["couch"]["agent_collection_name"]
COUCH_TASK_COLLECTION = config["couch"]["task_collection_name"]

logger.info(f"Using CouchDB URL: {COUCH_URL}")
logger.info(f"Target CouchDB DB: {COUCH_DB_NAME}")
logger.info(f"Using Weaviate host: {config['weaviate']['host']}:{config['weaviate']['port']}")

# ---------------------------------------------------------------
# COUCHDB SETUP
# ---------------------------------------------------------------

couch_db = None

try:
    couch = couchdb.Server(COUCH_URL)
    if COUCH_DB_NAME not in couch:
        logger.warning(f"Database '{COUCH_DB_NAME}' not found. Creating it.")
        couch.create(COUCH_DB_NAME)
    couch_db = couch[COUCH_DB_NAME]
    logger.info(f"Connected to CouchDB database '{COUCH_DB_NAME}' successfully.")
except Exception as e:
    logger.exception(f"[CouchDB] Connection failed: {e}")
    couch_db = None

# ---------------------------------------------------------------
# WEAVIATE SETUP
# ---------------------------------------------------------------

client = None
try:
    auth_credentials = weaviate.auth.AuthApiKey(WEAVIATE_API_KEY) if WEAVIATE_API_KEY else None

    client = weaviate.connect_to_local(
        host=config["weaviate"]["host"],
        port=config["weaviate"]["port"],
        auth_credentials=auth_credentials
    )
    if client.is_ready():
        logger.info("Weaviate connection successful and ready.")
    else:
        logger.warning("Weaviate connected but is not ready.")

    for coll_name, desc in [
        (config["weaviate"]["class_name_agent"], "Stores agent metadata"),
        (config["weaviate"]["class_name_task"], "Stores task metadata"),
    ]:
        if not client.collections.exists(coll_name):
            logger.info(f"Creating Weaviate collection '{coll_name}'")
            client.collections.create(
                name=coll_name,
                description=desc,
                properties=[
                    Property(name="role", data_type=DataType.TEXT),
                    Property(name="goal", data_type=DataType.TEXT),
                    Property(name="backstory", data_type=DataType.TEXT),
                    Property(name="description", data_type=DataType.TEXT),
                    Property(name="expected_output", data_type=DataType.TEXT),
                    Property(name="agent", data_type=DataType.TEXT),
                    Property(name="metadata", data_type=DataType.TEXT),
                    Property(name="shortid", data_type=DataType.TEXT),
                ],
            )
        else:
            logger.info(f"Weaviate collection '{coll_name}' already exists.")

except Exception as e:
    logger.exception(f"[Weaviate] Connection failed: {e}")
    client = None


# ---------------------------------------------------------------
# FASTAPI LIFESPAN
# ---------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if client:
        try:
            client.close()
            logger.info("Weaviate client closed")
        except Exception as e:
            logger.warning(f"Error closing Weaviate client: {e}")

# ---------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------

def _json_safe(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj

def authenticate_request(x_api_key: str = Header(None)):
    if x_api_key != RPC_API_KEY:
        logger.warning("Unauthorized request")
        raise HTTPException(status_code=401, detail="Unauthorized")

# ---------------------------------------------------------------
# RETRY QUEUE
# ---------------------------------------------------------------

RETRY_FILE = os.path.join(os.path.dirname(__file__), "weaviate_retry_queue.json")

def load_retry_queue():
    if os.path.exists(RETRY_FILE):
        try:
            with open(RETRY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_retry_queue(queue):
    with open(RETRY_FILE, "w") as f:
        json.dump(json.loads(json.dumps(queue, default=_json_safe)), f, indent=2)

retry_queue = load_retry_queue()

# ---------------------------------------------------------------
# WEAVIATE INSERT
# ---------------------------------------------------------------

def weaviate_insert(record, collection):
    if not client:
        raise ConnectionError("Weaviate not connected")

    coll = client.collections.get(collection)
    meta = record.get("metadata", {})

    coll.data.insert(
        properties={
            "role": meta.get("role"),
            "goal": meta.get("goal"),
            "backstory": meta.get("backstory"),
            "description": meta.get("description"),
            "expected_output": meta.get("expected_output"),
            "agent": meta.get("agent"),
            "metadata": json.dumps(meta),
            "shortid": record["id"],
        }
    )

# ---------------------------------------------------------------
# RETRY WORKER
# ---------------------------------------------------------------

def retry_worker():
    global retry_queue
    while True:
        if client and retry_queue:
            item = retry_queue.pop(0)
            record = item.get("record", item)
            collection = item.get("collection", config["weaviate"]["class_name_agent"])
            try:
                weaviate_insert(record, collection)
                logger.info(f"Retry success for {record['id']}")
            except Exception as e:
                logger.warning(f"Retry failed for {record['id']}: {e}")
                retry_queue.append(item)
            save_retry_queue(retry_queue)
        time.sleep(30)

threading.Thread(target=retry_worker, daemon=True).start()

# ---------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------

class AgentRequest(BaseModel):
    method: str
    params: Optional[Dict[str, Any]] = {}
    id: str = "1"

class TaskRequest(BaseModel):
    method: str
    params: Optional[Dict[str, Any]] = {}
    id: str = "1"

# ---------------------------------------------------------------
# FASTAPI APP
# ---------------------------------------------------------------

app = FastAPI(title="ShortID JSON-RPC Server", lifespan=lifespan)

@app.post("/agents")
async def rpc_agents(body: AgentRequest, x_api_key: str = Header(...)):
    authenticate_request(x_api_key)
    return await handle_json_rpc(
        body,
        weaviate_collection=config["weaviate"]["class_name_agent"],
        type_tag=COUCH_AGENT_COLLECTION
    )

@app.post("/tasks")
async def rpc_tasks(body: TaskRequest, x_api_key: str = Header(...)):
    authenticate_request(x_api_key)
    return await handle_json_rpc(
        body,
        weaviate_collection=config["weaviate"]["class_name_task"],
        type_tag=COUCH_TASK_COLLECTION
    )

# ---------------------------------------------------------------
# JSON-RPC HANDLER
# ---------------------------------------------------------------

async def handle_json_rpc(body: BaseModel, weaviate_collection: str, type_tag: Optional[str] = None):
    if body.method != "create_id":
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "Method not found"},
            "id": body.id
        })

    try:
        uid = generate_short_id(
            body.params.get("length", 6),
            body.params.get("deterministic", False),
            body.params.get("seed")
        )
        record = {
            "id": uid,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": body.params.get("metadata", {})
        }

        if type_tag:
            record["type"] = type_tag

        couch_db.save(record)

        try:
            weaviate_insert(record, weaviate_collection)
        except Exception as e:
            retry_queue.append({"record": record, "collection": weaviate_collection})
            save_retry_queue(retry_queue)

        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {"status": "ok", "id": uid, "collection": weaviate_collection},
            "id": body.id
        })

    except Exception as e:
        logger.exception("RPC error")
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": "Internal error", "data": str(e)},
            "id": body.id
        })

# ---------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------

@app.get("/healthz")
async def health():
    result = {
        "status": "ok",
        "retry_queue": len(retry_queue),
    }

    try:
        if couch_db:
            db_info = couch_db.info()
            result["couchdb"] = True
            logger.debug(f"CouchDB info: {json.dumps(db_info, indent=2)}")
        else:
            result["couchdb"] = False
    except Exception as e:
        result["couchdb"] = False
        result["couchdb_error"] = str(e)
        logger.warning(f"CouchDB health check failed: {e}")

    try:
        result["weaviate"] = client is not None and client.is_ready()
    except Exception as e:
        result["weaviate"] = False
        result["weaviate_error"] = str(e)
        logger.warning(f"Weaviate health check failed: {e}")

    return result

# ---------------------------------------------------------------
# MAIN ENTRYPOINT
# ---------------------------------------------------------------

if __name__ == "__main__":
    logger.info(f"Starting JSON-RPC Server on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
