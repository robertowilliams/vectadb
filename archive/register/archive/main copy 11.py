# main.py
# Agent Registry System using CouchDB, Weaviate, and Neo4j
# Provides ID generation, registration via JSON-RPC, and read-only endpoints for each backing database.
# Adding log ingestion endpoint
# Adding Custom Logger
# adding unique conf file (.env)
# main.py
# Agent Registry System using CouchDB, Weaviate, and Neo4j
# Provides ID generation, registration via JSON-RPC, and read-only endpoints for each backing database.
# Adding log ingestion endpoint
# Adding Custom Logger

import os
import json
import time
import logging
import threading
import string
import secrets
import hashlib
import base64
import datetime
from datetime import datetime
from time import perf_counter
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import requests  # currently unused but kept if you plan to use it later

import uvicorn
import couchdb
import weaviate
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from dotenv import load_dotenv
from weaviate.classes.config import Property, DataType
from weaviate.classes.query import MetadataQuery
from neo4j import GraphDatabase
from prometheus_client import Counter, Gauge, Histogram, generate_latest


# ---------------------------------------------------------------
# SIMILARITY CONFIG
# ---------------------------------------------------------------
AGENT_SIMILARITY_THRESHOLD = 0.85  # 85% similarity
AGENT_SIMILARITY_LIMIT = 10        # max similar agents to return

# ---------------------------------------------------------------
# SHORT-ID GENERATOR
# ---------------------------------------------------------------

ALPHABET = string.ascii_letters + string.digits


def generate_short_id(length: int = 6, deterministic: bool = False, seed: Optional[str] = None) -> str:
    """
    Generate a short ID. Can be deterministic given a seed.
    """
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
handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    "%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)
logger.addHandler(handler)


# ---------------------------------------------------------------
# LOAD ENVIRONMENT
# ---------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
ENV_PATH = os.path.join(PROJECT_ROOT, "config", ".env")

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    logger.info(f"Loaded environment variables from {ENV_PATH}")
else:
    # Fallback: try default .env locations
    load_dotenv()
    logger.warning(f".env file not found at {ENV_PATH}, falling back to default .env loading")

# Core API keys
RPC_API_KEY = os.getenv("RPC_API_KEY")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
COUCH_URL = os.getenv("COUCH_URL")

if not RPC_API_KEY:
    raise ValueError("RPC_API_KEY missing from environment")
if not COUCH_URL:
    raise ValueError("COUCH_URL missing from environment")

# Server config
HOST = os.getenv("SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("SERVER_PORT", "5432"))

# Couch config
COUCH_DB_NAME = os.getenv("COUCH_DB_NAME", "enroll")
COUCH_AGENT_COLLECTION = os.getenv("COUCH_AGENT_COLLECTION_NAME", "agents")
COUCH_TASK_COLLECTION = os.getenv("COUCH_TASK_COLLECTION_NAME", "tasks")

# Neo4j config
NEO4J_URL = os.getenv("NEO4J_URL", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Weaviate config
WEAVIATE_HOST = os.getenv("WEAVIATE_HOST", "127.0.0.1")
WEAVIATE_PORT = int(os.getenv("WEAVIATE_PORT", "8080"))
WEAVIATE_CLASS_NAME_AGENT = os.getenv("WEAVIATE_CLASS_NAME_AGENT", "AgentMetadata")
WEAVIATE_CLASS_NAME_TASK = os.getenv("WEAVIATE_CLASS_NAME_TASK", "TaskMetadata")

logger.info(f"Using CouchDB URL: {COUCH_URL}")
logger.info(f"Target CouchDB DB: {COUCH_DB_NAME}")
logger.info(f"Using Weaviate host: {WEAVIATE_HOST}:{WEAVIATE_PORT}")
logger.info(f"Using Neo4j URL: {NEO4J_URL}")


# ---------------------------------------------------------------
# LOG INGESTOR
# ---------------------------------------------------------------

class LogRequest(BaseModel):
    agent_id: str
    task_id: Optional[str] = None
    level: str = "INFO"
    message: str
    metadata: Optional[Dict[str, Any]] = {}


def ingest_log(agent_id: str, message: str, level="INFO", task_id=None, metadata=None):
    metadata = metadata or {}
    uid = generate_short_id(10)

    log_record = {
        "_id": uid,
        "agent_id": agent_id,
        "task_id": task_id,
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        "metadata": metadata
    }

    # 1. Store raw log in CouchDB
    couch_db.save(log_record)

    # 2. Store in Neo4J (best-effort)
    try:
        if neo4j_driver is None:
            logger.warning("[Neo4J] Log link skipped: driver not initialized")
            return uid

        with neo4j_driver.session() as session:
            session.run(
                """
                MERGE (l:Log {id: $id})
                SET l.timestamp = $timestamp,
                    l.level = $level,
                    l.message = $message,
                    l.metadata = $metadata
                """,
                id=uid,
                timestamp=log_record["timestamp"],
                level=level,
                message=message,
                metadata=json.dumps(metadata)
            )

            # Link to agent
            session.run(
                """
                MATCH (a:Agent {id: $agent_id}), (l:Log {id: $log_id})
                MERGE (a)-[:GENERATED_LOG]->(l)
                """,
                agent_id=agent_id,
                log_id=uid
            )

            # Link to task if provided
            if task_id:
                session.run(
                    """
                    MATCH (t:Task {id: $task_id}), (l:Log {id: $log_id})
                    MERGE (t)-[:HAS_LOG]->(l)
                    """,
                    task_id=task_id,
                    log_id=uid
                )

    except Exception as e:
        logger.warning(f"[Neo4J] Log link failed: {e}")

    return uid




# ---------------------------------------------------------------
# METRICS
# ---------------------------------------------------------------

agent_logs_total = Counter(
    "agent_logs_total",
    "Total logs received per agent",
    ["agent"]
)

agent_errors_total = Counter(
    "agent_errors_total",
    "Total ERROR logs per agent",
    ["agent"]
)

agent_anomaly_score = Gauge(
    "agent_anomaly_score",
    "Current anomaly score per agent",
    ["agent"]
)

log_ingest_latency = Histogram(
    "log_ingest_latency_seconds",
    "Latency of log ingestion"
)


# ---------------------------------------------------------------
# COUCHDB SETUP
# ---------------------------------------------------------------

couch_db: Optional[couchdb.Database] = None

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
# COUCHDB READ HELPERS
# ---------------------------------------------------------------


def _couch_list_by_type(
    type_tag: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
) -> List[Dict[str, Any]]:
    """
    Return documents from CouchDB, optionally filtered by 'type' field.
    Used by read-only endpoints.
    """
    if couch_db is None:
        raise HTTPException(status_code=503, detail="CouchDB not available")

    docs: List[Dict[str, Any]] = []
    index = 0
    for doc_id in couch_db:
        if index < skip:
            index += 1
            continue

        if len(docs) >= limit:
            break

        doc = couch_db[doc_id]
        if type_tag is None or doc.get("type") == type_tag:
            docs.append(doc)
        index += 1

    return docs


# ---------------------------------------------------------------
# WEAVIATE SETUP (text2vec-transformers enabled correctly)
# ---------------------------------------------------------------

client: Optional[weaviate.WeaviateClient] = None

try:
    # Use API key auth if provided
    auth_credentials = weaviate.auth.AuthApiKey(WEAVIATE_API_KEY) if WEAVIATE_API_KEY else None

    client = weaviate.connect_to_local(
        host=WEAVIATE_HOST,
        port=WEAVIATE_PORT,
        auth_credentials=auth_credentials,
    )

    if client.is_ready():
        logger.info("Weaviate connection successful and ready.")
    else:
        logger.warning("Weaviate connected but is not ready.")

    from weaviate.classes.config import (
        Property,
        DataType,
        VectorIndexConfig
    )

    def create_collection_with_vectorizer(name: str, desc: str):
        if client.collections.exists(name):
            logger.info(f"Weaviate collection '{name}' already exists.")
            return

        logger.info(f"Creating Weaviate collection '{name}' WITH vectorizer text2vec-transformers")

        client.collections.create(
            name=name,
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
            vectorizer="text2vec-transformers",            # <--- IMPORTANT
            vector_index_config=VectorIndexConfig.hnsw(    # <--- IMPORTANT
                distance="cosine"
            )
        )

    # Create collections
    create_collection_with_vectorizer(
        WEAVIATE_CLASS_NAME_AGENT, "Stores agent metadata"
    )
    create_collection_with_vectorizer(
        WEAVIATE_CLASS_NAME_TASK, "Stores task metadata"
    )

except Exception as e:
    logger.exception(f"[Weaviate] Connection failed: {e}")
    client = None



# ---------------------------------------------------------------
# WEAVIATE HELPERS
# ---------------------------------------------------------------


def weaviate_insert(record: Dict[str, Any], collection: str) -> None:
    """
    Insert a record into the given Weaviate collection.
    """
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


def _weaviate_list(collection_name: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Return objects from a Weaviate collection (best-effort, read-only).
    """
    if client is None:
        raise HTTPException(status_code=503, detail="Weaviate not available")

    try:
        coll = client.collections.get(collection_name)
    except Exception as e:
        logger.warning(f"Weaviate collection '{collection_name}' read failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Weaviate collection '{collection_name}' not accessible",
        )

    items: List[Dict[str, Any]] = []
    try:
        for i, obj in enumerate(coll.iterator()):
            if i >= limit:
                break
            items.append(
                {
                    "uuid": str(getattr(obj, "uuid", None)),
                    "properties": getattr(obj, "properties", {}),
                }
            )
    except Exception as e:
        logger.warning(f"Weaviate iterator failed for '{collection_name}': {e}")
        raise HTTPException(status_code=500, detail="Weaviate iteration failed")

    return items


def weaviate_find_similar_agents_from_metadata(
    meta: Dict[str, Any],
    threshold: float = AGENT_SIMILARITY_THRESHOLD,
    limit: int = AGENT_SIMILARITY_LIMIT,
) -> List[Dict[str, Any]]:
    if client is None:
        logger.warning("Weaviate client not available; skipping similarity search")
        return []

    text_parts: List[str] = []
    for key in ["role", "goal", "backstory", "description", "expected_output", "agent"]:
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            text_parts.append(val.strip())

    if not text_parts:
        logger.info("No descriptive metadata found; skipping similarity search")
        return []

    search_text = ". ".join(text_parts)
    logger.info(f"[Weaviate] Similarity search for new agent text: {search_text[:200]}")

    try:
        coll = client.collections.use(WEAVIATE_CLASS_NAME_AGENT)
        resp = coll.query.near_text(
            query=search_text,
            limit=limit,
            return_metadata=MetadataQuery(distance=True),
        )
    except Exception as e:
        logger.warning(f"[Weaviate] Similarity search failed: {e}")
        return []

    similar: List[Dict[str, Any]] = []
    for obj in resp.objects:
        dist = getattr(obj.metadata, "distance", None)
        if dist is None:
            continue

        similarity = 1.0 - float(dist)
        if similarity < threshold:
            continue

        props = obj.properties or {}
        similar.append(
            {
                "shortid": props.get("shortid"),
                "similarity": similarity,
                "role": props.get("role"),
                "goal": props.get("goal"),
                "backstory": props.get("backstory"),
                "description": props.get("description"),
                "expected_output": props.get("expected_output"),
            }
        )

    logger.info(f"[Weaviate] Found {len(similar)} agents with similarity >= {threshold}")
    return similar
# ---------------------------------------------------------------
# NEO4J SETUP
# ---------------------------------------------------------------

neo4j_driver: Optional[GraphDatabase.driver] = None

try:
    neo4j_driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))
    # Basic schema: unique shortid for Agent/Task
    with neo4j_driver.session() as session:

        def init_schema(tx):
            tx.run(
                "CREATE CONSTRAINT agent_shortid IF NOT EXISTS "
                "FOR (a:Agent) REQUIRE a.shortid IS UNIQUE"
            )
            tx.run(
                "CREATE CONSTRAINT task_shortid IF NOT EXISTS "
                "FOR (t:Task) REQUIRE t.shortid IS UNIQUE"
            )

        session.execute_write(init_schema)

    logger.info("[Neo4j] Driver initialized and schema ensured")
except Exception as e:
    logger.exception(f"[Neo4j] Connection or schema setup failed: {e}")
    neo4j_driver = None


def neo4j_agent_exists(agent_id: str) -> Optional[bool]:
    """
    Check if an Agent node exists in Neo4j. Returns True/False or None on error.
    """
    if not neo4j_driver:
        return None
    try:
        with neo4j_driver.session() as session:
            result = session.run(
                "MATCH (a:Agent {shortid: $id}) RETURN a LIMIT 1",
                id=agent_id,
            )
            exists = result.single() is not None
            logger.info(f"[Neo4j] Agent '{agent_id}' exists: {exists}")
            return exists
    except Exception as e:
        logger.warning(f"[Neo4j] Agent existence check error: {e}")
        return None


def neo4j_upsert_agent(agent_id: str, meta: Dict[str, Any]) -> None:
    """
    Upsert an Agent node in Neo4j.
    Store metadata as a JSON string (Neo4j properties cannot be dicts).
    """
    if not neo4j_driver:
        logger.error("[Neo4j] Driver is None, cannot upsert Agent")
        return
    try:
        metadata_json = json.dumps(meta or {})
        logger.info(f"[Neo4j] Upserting Agent {agent_id} with metadata={metadata_json}")
        with neo4j_driver.session() as session:
            session.run(
                "MERGE (a:Agent {shortid: $id}) "
                "SET a.metadata = $metadata",
                id=agent_id,
                metadata=metadata_json,
            )
        logger.info(f"[Neo4j] Agent '{agent_id}' upserted")
    except Exception as e:
        logger.exception(f"[Neo4j] Upsert Agent error for id={agent_id}: {e}")


def neo4j_upsert_task(task_id: str, meta: Dict[str, Any]) -> None:
    """
    Upsert a Task node in Neo4j.
    Store metadata as a JSON string.
    """
    if not neo4j_driver:
        logger.error("[Neo4j] Driver is None, cannot upsert Task")
        return
    try:
        metadata_json = json.dumps(meta or {})
        logger.info(f"[Neo4j] Upserting Task {task_id} with metadata={metadata_json}")
        with neo4j_driver.session() as session:
            session.run(
                "MERGE (t:Task {shortid: $id}) "
                "SET t.metadata = $metadata",
                id=task_id,
                metadata=metadata_json,
            )
        logger.info(f"[Neo4j] Task '{task_id}' upserted")
    except Exception as e:
        logger.exception(f"[Neo4j] Upsert Task error for id={task_id}: {e}")


def neo4j_link_task_to_agent(task_id: str, agent_id: str) -> None:
    """
    Link a Task node to an Agent node via BELONGS_TO relationship.
    """
    if not neo4j_driver:
        return
    try:
        with neo4j_driver.session() as session:
            session.run(
                """
                MATCH (t:Task {shortid: $task_id})
                MATCH (a:Agent {shortid: $agent_id})
                MERGE (t)-[r:BELONGS_TO]->(a)
                SET r.created_at = datetime()
                """,
                task_id=task_id,
                agent_id=agent_id,
            )
        logger.info(f"[Neo4j] BELONGS_TO relationship {task_id} -> {agent_id} created/ensured")
    except Exception as e:
        logger.warning(f"[Neo4j] BELONGS_TO relationship error: {e}")


def _neo4j_list_vertices(label: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Return nodes of a given label (Agent/Task) from Neo4j.
    We read shortid and metadata for inspection.
    """
    if not neo4j_driver:
        raise HTTPException(status_code=503, detail="Neo4j not available")

    try:
        with neo4j_driver.session() as session:
            result = session.run(
                f"""
                MATCH (n:{label})
                RETURN n.shortid AS shortid, n.metadata AS metadata
                ORDER BY n.shortid
                LIMIT $limit
                """,
                limit=limit,
            )
            rows: List[Dict[str, Any]] = []
            for record in result:
                rows.append(
                    {
                        "shortid": record.get("shortid"),
                        "metadata": record.get("metadata"),
                    }
                )
            return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[Neo4j] Read error for label {label}: {e}")
        raise HTTPException(status_code=500, detail="Neo4j read failed")


# ---------------------------------------------------------------
# FASTAPI LIFESPAN
# ---------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context to clean up external clients on shutdown.
    """
    start_ts = perf_counter()
    logger.info("Starting FastAPI lifespan")
    try:
        yield
    finally:
        # Close Weaviate client
        if client:
            try:
                client.close()
                logger.info("Weaviate client closed")
            except Exception as e:
                logger.warning(f"Error closing Weaviate client: {e}")

        # Close Neo4j driver
        if neo4j_driver:
            try:
                neo4j_driver.close()
                logger.info("Neo4j driver closed")
            except Exception as e:
                logger.warning(f"Error closing Neo4j driver: {e}")

        elapsed = perf_counter() - start_ts
        logger.info(f"FastAPI lifespan complete in {elapsed:.3f}s")


# ---------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def authenticate_request(x_api_key: str = Header(None)) -> None:
    if x_api_key != RPC_API_KEY:
        logger.warning("Unauthorized request")
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------------------------------------------------------------
# RETRY QUEUE
# ---------------------------------------------------------------

RETRY_FILE = os.path.join(os.path.dirname(__file__), "weaviate_retry_queue.json")


def load_retry_queue() -> List[Dict[str, Any]]:
    if os.path.exists(RETRY_FILE):
        try:
            with open(RETRY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_retry_queue(queue: List[Dict[str, Any]]) -> None:
    with open(RETRY_FILE, "w") as f:
        json.dump(json.loads(json.dumps(queue, default=_json_safe)), f, indent=2)


retry_queue: List[Dict[str, Any]] = load_retry_queue()


# ---------------------------------------------------------------
# RETRY WORKER
# ---------------------------------------------------------------


def retry_worker() -> None:
    """
    Background worker that retries failed Weaviate inserts.
    """
    global retry_queue
    while True:
        if client and retry_queue:
            item = retry_queue.pop(0)
            record = item.get("record", item)
            collection = item.get("collection", WEAVIATE_CLASS_NAME_AGENT)
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

app = FastAPI(title="Agent Registry System", lifespan=lifespan)


# ---------------------------------------------------------------
# JSON-RPC HANDLER
# ---------------------------------------------------------------


async def handle_json_rpc(
    body: BaseModel,
    weaviate_collection: str,
    type_tag: Optional[str] = None,
    is_task: bool = False,
    with_similarity_search: bool = False,
    similarity_threshold: float = AGENT_SIMILARITY_THRESHOLD,
):
    """
    Handle JSON-RPC requests for /agents and /tasks endpoints.
    Currently supports only method=create_id.
    """
    if body.method != "create_id":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "Method not found"},
                "id": body.id,
            }
        )

    params = body.params or {}

    # For agents: optionally compute semantic similarity BEFORE creating the new one
    similar_agents: List[Dict[str, Any]] = []
    if (not is_task) and with_similarity_search:
        try:
            meta_for_search = params.get("metadata") or {}
            similar_agents = weaviate_find_similar_agents_from_metadata(
                meta_for_search,
                threshold=similarity_threshold,
                limit=AGENT_SIMILARITY_LIMIT,
            )
        except Exception as e:
            logger.warning(f"Similarity search failed before agent creation: {e}")
            similar_agents = []


    # For tasks, require agent_id and verify Agent exists in Neo4j
    agent_id: Optional[str] = None
    if is_task:
        agent_id = params.get("agent_id")
        if not agent_id:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32602,
                        "message": "Invalid params: 'agent_id' is required for task creation",
                    },
                    "id": body.id,
                }
            )

        exists = neo4j_agent_exists(agent_id)
        if exists is False:
            logger.warning(f"Task creation rejected: Agent '{agent_id}' does not exist in Neo4j")
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": "Agent not found",
                        "data": {"agent_id": agent_id},
                    },
                    "id": body.id,
                }
            )
        if exists is None:
            logger.error("Neo4j unavailable while checking agent existence")
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": "Internal error: Neo4j unavailable for agent existence check",
                    },
                    "id": body.id,
                }
            )

    try:
        uid = generate_short_id(
            params.get("length", 6),
            params.get("deterministic", False),
            params.get("seed"),
        )
        record: Dict[str, Any] = {
            "id": uid,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": params.get("metadata", {}) or {},
        }

        if type_tag:
            record["type"] = type_tag
        if is_task and agent_id:
            record["agent_id"] = agent_id

        # Store in CouchDB
        if couch_db is None:
            raise RuntimeError("CouchDB not available")
        couch_db.save(record)

        # Store in Weaviate (best effort)
        try:
            weaviate_insert(record, weaviate_collection)
        except Exception as e:
            logger.warning(f"Weaviate insert failed for {uid}: {e}")
            retry_queue.append({"record": record, "collection": weaviate_collection})
            save_retry_queue(retry_queue)

        # Store in Neo4j
        meta = record.get("metadata", {})
        if is_task:
            neo4j_upsert_task(uid, meta)
            if agent_id:
                neo4j_link_task_to_agent(uid, agent_id)
        else:
            neo4j_upsert_agent(uid, meta)

        result_payload: Dict[str, Any] = {
            "status": "ok",
            "id": uid,
            "collection": weaviate_collection,
        }

        # Attach similar_agents only for agent creation calls
        if (not is_task) and with_similarity_search:
            result_payload["similar_agents"] = similar_agents

        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "result": result_payload,
                "id": body.id,
            }
        )


    except Exception as e:
        logger.exception("RPC error")
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": "Internal error", "data": str(e)},
                "id": body.id,
            }
        )


# ---------------------------------------------------------------
# RPC ENDPOINTS
# ---------------------------------------------------------------


@app.post("/agents")
async def rpc_agents(body: AgentRequest, x_api_key: str = Header(...)):
    authenticate_request(x_api_key)
    return await handle_json_rpc(
        body,
        weaviate_collection=WEAVIATE_CLASS_NAME_AGENT,
        type_tag=COUCH_AGENT_COLLECTION,
        is_task=False,
        with_similarity_search=True,          # <--- NEW
        similarity_threshold=AGENT_SIMILARITY_THRESHOLD,
    )


@app.post("/tasks")
async def rpc_tasks(body: TaskRequest, x_api_key: str = Header(...)):
    authenticate_request(x_api_key)
    return await handle_json_rpc(
        body,
        weaviate_collection=WEAVIATE_CLASS_NAME_TASK,
        type_tag=COUCH_TASK_COLLECTION,
        is_task=True,
    )


# ---------------------------------------------------------------
# COUCHDB READ-ONLY ENDPOINTS
# ---------------------------------------------------------------


@app.get("/couch/agents")
async def couch_agents(
    x_api_key: str = Header(...),
    limit: int = 100,
    skip: int = 0,
):
    """
    List agent documents stored in CouchDB.
    """
    authenticate_request(x_api_key)
    docs = _couch_list_by_type(COUCH_AGENT_COLLECTION, limit=limit, skip=skip)
    return {"count": len(docs), "items": docs}


@app.get("/couch/tasks")
async def couch_tasks(
    x_api_key: str = Header(...),
    limit: int = 100,
    skip: int = 0,
):
    """
    List task documents stored in CouchDB.
    """
    authenticate_request(x_api_key)
    docs = _couch_list_by_type(COUCH_TASK_COLLECTION, limit=limit, skip=skip)
    return {"count": len(docs), "items": docs}


@app.get("/couch/all")
async def couch_all(
    x_api_key: str = Header(...),
    limit: int = 100,
    skip: int = 0,
):
    """
    List all documents stored in CouchDB, regardless of type.
    """
    authenticate_request(x_api_key)
    docs = _couch_list_by_type(type_tag=None, limit=limit, skip=skip)
    return {"count": len(docs), "items": docs}


# ---------------------------------------------------------------
# WEAVIATE READ-ONLY ENDPOINTS
# ---------------------------------------------------------------


@app.get("/weaviate/agents")
async def weaviate_agents(
    x_api_key: str = Header(...),
    limit: int = 100,
):
    """
    List agent objects stored in Weaviate.
    """
    authenticate_request(x_api_key)
    items = _weaviate_list(WEAVIATE_CLASS_NAME_AGENT, limit=limit)
    return {"count": len(items), "items": items}


@app.get("/weaviate/tasks")
async def weaviate_tasks(
    x_api_key: str = Header(...),
    limit: int = 100,
):
    """
    List task objects stored in Weaviate.
    """
    authenticate_request(x_api_key)
    items = _weaviate_list(WEAVIATE_CLASS_NAME_TASK, limit=limit)
    return {"count": len(items), "items": items}


# ---------------------------------------------------------------
# NEO4J READ-ONLY ENDPOINTS
# ---------------------------------------------------------------


@app.get("/neo4j/agents")
async def neo4j_agents(
    x_api_key: str = Header(...),
    limit: int = 100,
):
    """
    List Agent nodes from Neo4j (label: Agent).
    """
    authenticate_request(x_api_key)
    items = _neo4j_list_vertices("Agent", limit=limit)
    return {"count": len(items), "items": items}


@app.get("/neo4j/tasks")
async def neo4j_tasks(
    x_api_key: str = Header(...),
    limit: int = 100,
):
    """
    List Task nodes from Neo4j (label: Task).
    """
    authenticate_request(x_api_key)
    items = _neo4j_list_vertices("Task", limit=limit)
    return {"count": len(items), "items": items}


# ---------------------------------------------------------------
# METRICS ENDPOINTS
# ---------------------------------------------------------------

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")


# ---------------------------------------------------------------
# LOGS ENDPOINT
# ---------------------------------------------------------------

@app.post("/logs")
async def create_log(body: LogRequest, x_api_key: str = Header(...)):
    authenticate_request(x_api_key)

    with log_ingest_latency.time():
        try:
            log_id = ingest_log(
                agent_id=body.agent_id,
                message=body.message,
                level=body.level,
                task_id=body.task_id,
                metadata=body.metadata
            )

            # PROMETHEUS METRICS
            agent_logs_total.labels(agent=body.agent_id).inc()

            if body.level.upper() == "ERROR":
                agent_errors_total.labels(agent=body.agent_id).inc()

            return {
                "status": "ok",
                "log_id": log_id,
                "agent_id": body.agent_id,
                "task_id": body.task_id
            }

        except Exception as e:
            logger.exception("Failed to ingest log")
            agent_errors_total.labels(agent=body.agent_id).inc()
            raise HTTPException(status_code=500, detail=f"Error ingesting log: {e}")


# ---------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------


@app.get("/healthz")
async def health():
    """
    Health check for all backing services and retry queue length.
    """
    result: Dict[str, Any] = {
        "status": "ok",
        "retry_queue": len(retry_queue),
    }

    # CouchDB
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

    # Weaviate
    try:
        result["weaviate"] = client is not None and client.is_ready()
    except Exception as e:
        result["weaviate"] = False
        result["weaviate_error"] = str(e)
        logger.warning(f"Weaviate health check failed: {e}")

    # Neo4j
    try:
        if neo4j_driver:
            with neo4j_driver.session() as session:
                rec = session.run("RETURN 1 AS ok").single()
                result["neo4j"] = rec is not None and rec["ok"] == 1
        else:
            result["neo4j"] = False
    except Exception as e:
        result["neo4j"] = False
        result["neo4j_error"] = str(e)
        logger.warning(f"Neo4j health check failed: {e}")

    return result


# ---------------------------------------------------------------
# MAIN ENTRYPOINT
# ---------------------------------------------------------------

if __name__ == "__main__":
    logger.info(f"Starting Agent Registry System on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
