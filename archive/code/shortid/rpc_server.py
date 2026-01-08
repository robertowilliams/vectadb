import os
import json
import time
import logging
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uvicorn
from pymongo import MongoClient
from weaviate import connect_to_local
from weaviate.classes.config import Property, DataType, Configure
from dotenv import load_dotenv

from shortid.generator import generate_short_id
from shortid.config import load_config

# ------------------------------------------------------------------ #
# Logging Setup
# ------------------------------------------------------------------ #

LOG_DIR = "/opt/vecgraph/logs"
LOG_FILE = os.path.join(LOG_DIR, "shortid.log")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("shortid")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S"
)
handler.setFormatter(formatter)
logger.addHandler(handler)

# ------------------------------------------------------------------ #
# Configuration & API Key
# ------------------------------------------------------------------ #

load_dotenv(dotenv_path="/opt/vecgraph/config/.env")
RPC_API_KEY = os.getenv("RPC_API_KEY")
if not RPC_API_KEY:
    raise ValueError("RPC_API_KEY not set in .env file!")

config = load_config()
HOST = config["server"]["host"]
PORT = config["server"]["port"]
MONGO_URI = config["MONGO_URI"]
DB_NAME = config["database"]["name"]
COLLECTION_NAME = config["database"]["collection"]

# ------------------------------------------------------------------ #
# MongoDB Setup
# ------------------------------------------------------------------ #

try:
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[DB_NAME]
    mongo_col = mongo_db[COLLECTION_NAME]
    mongo_col.create_index("id", unique=True)
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.exception(f"Failed to connect to MongoDB: {e}")

# ------------------------------------------------------------------ #
# Weaviate Setup
# ------------------------------------------------------------------ #

client = None
try:
    client = connect_to_local(host="localhost", port=8081)

    for coll_name, desc in [
        ("AgentMetadata", "Stores agent roles, goals, and backstories with embeddings"),
        ("TaskMetadata", "Stores task-related descriptions, outputs, and assigned agents"),
    ]:
        if not client.collections.exists(coll_name):
            logger.info(f"Creating Weaviate collection: {coll_name}")
            client.collections.create(
                name=coll_name,
                description=desc,
                vectorizer_config=Configure.Vectorizer.text2vec_transformers(),
                properties=[
                    Property(name="role", data_type=DataType.TEXT),
                    Property(name="goal", data_type=DataType.TEXT),
                    Property(name="backstory", data_type=DataType.TEXT),
                    Property(name="metadata", data_type=DataType.TEXT),
                    Property(name="shortid", data_type=DataType.TEXT),
                    Property(name="description", data_type=DataType.TEXT),
                    Property(name="expected_output", data_type=DataType.TEXT),
                    Property(name="agent", data_type=DataType.TEXT),
                ],
            )
    logger.info("Connected to Weaviate successfully")
except Exception as e:
    logger.error(f"Failed to connect to Weaviate: {e}")
    client = None

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _json_safe(obj):
    """Convert ObjectId and datetime to JSON-safe types."""
    from bson import ObjectId
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    return obj

def authenticate_request(x_api_key: str = Header(None)):
    """Header-based API key validation."""
    if x_api_key != RPC_API_KEY:
        logger.warning("Unauthorized access attempt detected.")
        raise HTTPException(status_code=401, detail="Unauthorized")

# ------------------------------------------------------------------ #
# Retry Queue
# ------------------------------------------------------------------ #

RETRY_FILE = "/opt/shortid/weaviate_retry_queue.json"

def load_retry_queue():
    if os.path.exists(RETRY_FILE):
        with open(RETRY_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_retry_queue(queue):
    safe_queue = json.loads(json.dumps(queue, default=_json_safe))
    with open(RETRY_FILE, "w") as f:
        json.dump(safe_queue, f, indent=2)

retry_queue = load_retry_queue()

# ------------------------------------------------------------------ #
# Weaviate Insert Function
# ------------------------------------------------------------------ #

def weaviate_insert(record, collection):
    """Insert record into Weaviate."""
    if not client:
        raise ConnectionError("Weaviate client not connected")

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
    logger.info(f"Inserted {record['id']} into Weaviate collection '{collection}'")

# ------------------------------------------------------------------ #
# Retry Worker Thread
# ------------------------------------------------------------------ #

def retry_worker():
    global retry_queue
    while True:
        if client and retry_queue:
            item = retry_queue.pop(0)
            record = item.get("record", item)
            collection = item.get("collection", "AgentMetadata")
            shortid = record.get("shortid") or record.get("id")

            try:
                weaviate_insert(record, collection)
                logger.info(f"Retried and inserted {shortid} into Weaviate ({collection})")
            except Exception as e:
                logger.warning(f"Retry failed for {shortid} ({collection}): {e}")
                retry_queue.append(item)
            save_retry_queue(retry_queue)
        time.sleep(30)

threading.Thread(target=retry_worker, daemon=True).start()

# ------------------------------------------------------------------ #
# Pydantic Models (Swagger Examples)
# ------------------------------------------------------------------ #

class AgentRequest(BaseModel):
    method: str = Field(..., description="The JSON-RPC method name (must be 'create_id')")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    id: Optional[str] = Field("1", description="Request ID for matching responses")

    class Config:
        json_schema_extra = {
            "example": {
                "method": "create_id",
                "params": {
                    "length": 6,
                    "metadata": {
                        "backstory": "An AI engineer improving embeddings",
                        "goal": "optimize model performance",
                        "role": "engineer"
                    }
                },
                "id": "1"
            }
        }

class TaskRequest(BaseModel):
    method: str = Field(..., description="The JSON-RPC method name (must be 'create_id')")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    id: Optional[str] = Field("1", description="Request ID for matching responses")

    class Config:
        json_schema_extra = {
            "example": {
                "method": "create_id",
                "params": {
                    "length": 6,
                    "metadata": {
                        "description": (
                            "Using the provided results, write a short article that highlights "
                            "the latest papers in Graph Neural Network."
                        ),
                        "expected_output": (
                            "Full blog post of at least 3 paragraphs and maximum of 20."
                        ),
                        "agent": "Ms3ijK"
                    }
                },
                "id": "1"
            }
        }

# ------------------------------------------------------------------ #
# FastAPI App
# ------------------------------------------------------------------ #

app = FastAPI(
    title="ShortID JSON-RPC Server",
    description="Generates and stores short IDs with metadata for agents and tasks.",
    version="1.0.2"
)

@app.post("/agents", tags=["Agents"])
async def rpc_agents(body: AgentRequest, x_api_key: str = Header(...)):
    authenticate_request(x_api_key)
    return await handle_json_rpc(body, "AgentMetadata")

@app.post("/tasks", tags=["Tasks"])
async def rpc_tasks(body: TaskRequest, x_api_key: str = Header(...)):
    authenticate_request(x_api_key)
    return await handle_json_rpc(body, "TaskMetadata")

# ------------------------------------------------------------------ #
# JSON-RPC Handler
# ------------------------------------------------------------------ #

async def handle_json_rpc(body: BaseModel, collection: str):
    method = body.method
    params = body.params or {}
    req_id = body.id

    if method != "create_id":
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "Method not found"},
            "id": req_id,
        })

    try:
        uid = generate_short_id(
            params.get("length", 6),
            params.get("deterministic", False),
            params.get("seed")
        )
        record = {
            "id": uid,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": params.get("metadata", {}),
        }

        mongo_col.insert_one(record)
        logger.info(f"Stored ID {uid} in MongoDB with metadata: {record['metadata']}")

        try:
            weaviate_insert(record, collection)
        except Exception as e:
            logger.error(f"Failed to insert {uid} into Weaviate: {e}")
            retry_queue.append({"record": record, "collection": collection})
            save_retry_queue(retry_queue)

        return JSONResponse(content={
            "jsonrpc": "2.0",
            "result": {"status": "ok", "id": uid, "collection": collection},
            "id": req_id,
        })

    except Exception as e:
        logger.exception("Error processing RPC request")
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": "Internal error", "data": str(e)},
            "id": req_id,
        })

# ------------------------------------------------------------------ #
# Health Check
# ------------------------------------------------------------------ #

@app.get("/healthz", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "mongo": mongo_client is not None,
        "weaviate": client is not None,
        "retry_queue": len(retry_queue),
    }

# ------------------------------------------------------------------ #
# Entry Point
# ------------------------------------------------------------------ #

def run_rpc_server():
    logger.info(f"Starting JSON-RPC Server on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)

if __name__ == "__main__":
    run_rpc_server()
