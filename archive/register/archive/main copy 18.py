# main.py
# Agent Registry System using CouchDB, Chroma, and Neo4j
# Provides ID generation, registration via JSON-RPC, semantic similarity search,
# log ingestion, metrics, health checks, and a small admin UI with demo login.
# working

import os
import re
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
import requests

import uvicorn
import couchdb
import chromadb
from sentence_transformers import SentenceTransformer
from fastapi import FastAPI, Header, HTTPException, Depends, Cookie
from fastapi.responses import JSONResponse, Response, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
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

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
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
if not logger.handlers:
    logger.addHandler(handler)


# ---------------------------------------------------------------
# LOAD ENVIRONMENT
# ---------------------------------------------------------------

ENV_PATH = os.path.join(PROJECT_ROOT, "config", ".env")

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    logger.info(f"Loaded environment variables from {ENV_PATH}")
else:
    load_dotenv()
    logger.warning(f".env file not found at {ENV_PATH}, falling back to default .env loading")

# Core API keys
RPC_API_KEY = os.getenv("RPC_API_KEY")
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

# Chroma + embeddings config
CHROMA_PATH = os.getenv("CHROMA_PATH", os.path.join(PROJECT_ROOT, "chroma_data"))
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

logger.info(f"Using CouchDB URL: {COUCH_URL}")
logger.info(f"Target CouchDB DB: {COUCH_DB_NAME}")
logger.info(f"Using Neo4j URL: {NEO4J_URL}")
logger.info(f"Using Chroma path: {CHROMA_PATH}")
logger.info(f"Using embedding model: {EMBEDDING_MODEL_NAME}")

# ---------------------------------------------------------------
# LOG INGESTOR
# ---------------------------------------------------------------

class LogRequest(BaseModel):
    agent_id: str
    task_id: Optional[str] = None
    level: str = "INFO"
    message: str
    metadata: Optional[Dict[str, Any]] = {}


def ingest_log(agent_id: str, message: str, level: str = "INFO", task_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
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
    if couch_db is not None:
        couch_db.save(log_record)
    else:
        logger.warning("CouchDB not available; log not persisted there")

    # 2. Store in Neo4j (best-effort)
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
                MATCH (a:Agent {shortid: $agent_id}), (l:Log {id: $log_id})
                MERGE (a)-[:GENERATED_LOG]->(l)
                """,
                agent_id=agent_id,
                log_id=uid
            )

            # Link to task if provided
            if task_id:
                session.run(
                    """
                    MATCH (t:Task {shortid: $task_id}), (l:Log {id: $log_id})
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
# CHROMA + EMBEDDINGS SETUP
# ---------------------------------------------------------------

embedding_model: Optional[SentenceTransformer] = None
chroma_client: Optional[chromadb.PersistentClient] = None
chroma_agents = None
chroma_tasks = None

try:
    os.makedirs(CHROMA_PATH, exist_ok=True)
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    logger.info(f"Loaded embedding model '{EMBEDDING_MODEL_NAME}'")

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    chroma_agents = chroma_client.get_or_create_collection(
        name="agents",
        metadata={"hnsw:space": "cosine"}
    )
    chroma_tasks = chroma_client.get_or_create_collection(
        name="tasks",
        metadata={"hnsw:space": "cosine"}
    )
    logger.info("Chroma collections 'agents' and 'tasks' ready.")
except Exception as e:
    logger.exception(f"[Chroma] Initialization failed: {e}")
    embedding_model = None
    chroma_client = None
    chroma_agents = None
    chroma_tasks = None


# ---------------------------------------------------------------
# CHROMA HELPERS
# ---------------------------------------------------------------

def build_text_from_metadata(meta: Dict[str, Any]) -> str:
    """
    Construct a text string from agent/task metadata to feed the embedder.
    """
    if not isinstance(meta, dict):
        return ""

    parts: List[str] = []
    for key in ["role", "goal", "backstory", "description", "expected_output", "agent"]:
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())

    # Fallback: any other string metadata
    if not parts:
        for v in meta.values():
            if isinstance(v, str) and v.strip():
                parts.append(v.strip())

    return ". ".join(parts)


def encode_text(text: str) -> Optional[List[float]]:
    """
    Encode a single text into an embedding vector.
    """
    if embedding_model is None:
        logger.warning("Embedding model not initialized")
        return None
    text = (text or "").strip()
    if not text:
        return None

    vec = embedding_model.encode([text])[0]
    try:
        return vec.tolist()
    except Exception:
        return list(vec)


def chroma_find_similar_items(
    collection,
    item_id: str,
    threshold: float = 0.85,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Generic similarity search for either agents or tasks.
    Uses stored embeddings from Chroma.
    """
    if collection is None:
        return []

    try:
        # Fetch the stored item (embedding already stored in Chroma)
        item = collection.get(ids=[item_id], include=["embeddings", "metadatas"])
        embeddings = item.get("embeddings", [[]])[0]
        meta = item.get("metadatas", [{}])[0]

        if not embeddings:
            return []

        # Query Chroma for similarities
        res = collection.query(
            query_embeddings=[embeddings],
            n_results=limit,
            include=["metadatas", "distances"]
        )

        ids = res.get("ids", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]

        similar = []
        for id_, m, dist in zip(ids, metas, dists):
            if id_ == item_id:
                continue  # skip self

            sim = 1.0 - float(dist)
            if sim < threshold:
                continue

            similar.append({
                "shortid": id_,
                "similarity": sim,
                "metadata": m,
            })

        return similar

    except Exception as e:
        logger.warning(f"[Chroma] Similarity search failed for {item_id}: {e}")
        return []


def chroma_upsert_agent(agent_id: str, meta: Dict[str, Any]) -> None:
    """
    Upsert an agent vector + metadata into Chroma.
    """
    if chroma_agents is None:
        logger.warning("Chroma agents collection not available; skipping upsert")
        return

    text = build_text_from_metadata(meta)
    emb = encode_text(text)
    if emb is None:
        logger.info(f"[Chroma] No text to embed for agent {agent_id}; skipping")
        return

    try:
        chroma_agents.add(ids=[agent_id], embeddings=[emb], metadatas=[meta])
    except Exception:
        # If already exists, update instead
        try:
            chroma_agents.update(ids=[agent_id], embeddings=[emb], metadatas=[meta])
        except Exception as e:
            logger.warning(f"[Chroma] Failed to upsert agent {agent_id}: {e}")


def chroma_upsert_task(task_id: str, meta: Dict[str, Any]) -> None:
    """
    Upsert a task vector + metadata into Chroma.
    """
    if chroma_tasks is None:
        logger.warning("Chroma tasks collection not available; skipping upsert")
        return

    text = build_text_from_metadata(meta)
    emb = encode_text(text)
    if emb is None:
        logger.info(f"[Chroma] No text to embed for task {task_id}; skipping")
        return

    try:
        chroma_tasks.add(ids=[task_id], embeddings=[emb], metadatas=[meta])
    except Exception:
        try:
            chroma_tasks.update(ids=[task_id], embeddings=[emb], metadatas=[meta])
        except Exception as e:
            logger.warning(f"[Chroma] Failed to upsert task {task_id}: {e}")


def chroma_find_similar_agents_from_metadata(
    meta: Dict[str, Any],
    threshold: float = AGENT_SIMILARITY_THRESHOLD,
    limit: int = AGENT_SIMILARITY_LIMIT,
) -> List[Dict[str, Any]]:
    """
    Given an agent metadata dict, query Chroma for semantically similar agents.
    Uses cosine distance; we convert to similarity = 1 - distance.
    """
    if chroma_agents is None:
        logger.warning("Chroma agents collection not available; skipping similarity search")
        return []

    text = build_text_from_metadata(meta)
    if not text:
        logger.info("No descriptive metadata found; skipping similarity search")
        return []

    emb = encode_text(text)
    if emb is None:
        return []

    try:
        res = chroma_agents.query(
            query_embeddings=[emb],
            n_results=limit,
            include=["metadatas", "distances"],
        )
    except Exception as e:
        logger.warning(f"[Chroma] Similarity search failed: {e}")
        return []

    ids_list = res.get("ids") or []
    metas_list = res.get("metadatas") or []
    dists_list = res.get("distances") or []

    if not ids_list:
        return []

    ids = ids_list[0] if ids_list else []
    metas = metas_list[0] if metas_list else []
    dists = dists_list[0] if dists_list else []

    similar: List[Dict[str, Any]] = []

    for id_, meta_, dist in zip(ids, metas, dists):
        if dist is None:
            continue
        try:
            dist_val = float(dist)
        except Exception:
            continue

        similarity = 1.0 - dist_val
        if similarity < threshold:
            continue

        meta_ = meta_ or {}
        similar.append(
            {
                "shortid": id_,
                "similarity": similarity,
                "role": meta_.get("role"),
                "goal": meta_.get("goal"),
                "backstory": meta_.get("backstory"),
                "description": meta_.get("description"),
                "expected_output": meta_.get("expected_output"),
            }
        )

    logger.info(f"[Chroma] Found {len(similar)} agents with similarity >= {threshold}")
    return similar


def chroma_find_similar_tasks_from_metadata(
    meta: Dict[str, Any],
    threshold: float = AGENT_SIMILARITY_THRESHOLD,
    limit: int = AGENT_SIMILARITY_LIMIT,
) -> List[Dict[str, Any]]:
    """
    Given a task metadata dict, query Chroma for semantically similar tasks.
    Uses cosine distance; we convert to similarity = 1 - distance.
    """
    if chroma_tasks is None:
        logger.warning("Chroma tasks collection not available; skipping similarity search")
        return []

    text = build_text_from_metadata(meta)
    if not text:
        logger.info("No descriptive metadata found; skipping task similarity search")
        return []

    emb = encode_text(text)
    if emb is None:
        return []

    try:
        res = chroma_tasks.query(
            query_embeddings=[emb],
            n_results=limit,
            include=["metadatas", "distances"],
        )
    except Exception as e:
        logger.warning(f"[Chroma] Task similarity search failed: {e}")
        return []

    ids_list = res.get("ids") or []
    metas_list = res.get("metadatas") or []
    dists_list = res.get("distances") or []

    if not ids_list:
        return []

    ids = ids_list[0] if ids_list else []
    metas = metas_list[0] if metas_list else []
    dists = dists_list[0] if dists_list else []

    similar: List[Dict[str, Any]] = []

    for id_, meta_, dist in zip(ids, metas, dists):
        if dist is None:
            continue
        try:
            dist_val = float(dist)
        except Exception:
            continue

        similarity = 1.0 - dist_val
        if similarity < threshold:
            continue

        meta_ = meta_ or {}
        similar.append(
            {
                "shortid": id_,
                "similarity": similarity,
                "role": meta_.get("role"),
                "goal": meta_.get("goal"),
                "backstory": meta_.get("backstory"),
                "description": meta_.get("description"),
                "expected_output": meta_.get("expected_output"),
            }
        )

    logger.info(f"[Chroma] Found {len(similar)} tasks with similarity >= {threshold}")
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


def neo4j_store_thought(
    agent_id: str,
    task_id: Optional[str],
    content: str,
    step_index: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a Thought node in Neo4j and link it to the Agent (and Task if provided).

    Schema:
      (a:Agent {shortid: agent_id})-[:GENERATED_THOUGHT]->(th:Thought {id})
      (task:Task {shortid: task_id})-[:HAS_THOUGHT]->(th)   # optional
    """
    if not neo4j_driver:
        logger.error("[Neo4j] Driver is None, cannot store Thought")
        raise RuntimeError("Neo4j driver not initialized")

    thought_id = generate_short_id(10)
    metadata_json = json.dumps(metadata or {})

    try:
        with neo4j_driver.session() as session:
            # Create the Thought and link to Agent
            session.run(
                """
                MATCH (a:Agent {shortid: $agent_id})
                MERGE (th:Thought {id: $id})
                SET th.content = $content,
                    th.step_index = $step_index,
                    th.metadata = $metadata,
                    th.created_at = datetime()
                MERGE (a)-[:GENERATED_THOUGHT]->(th)
                """,
                agent_id=agent_id,
                id=thought_id,
                content=content,
                step_index=step_index,
                metadata=metadata_json,
            )

            # Optionally link to Task
            if task_id:
                session.run(
                    """
                    MATCH (t:Task {shortid: $task_id}),
                          (th:Thought {id: $id})
                    MERGE (t)-[:HAS_THOUGHT]->(th)
                    """,
                    task_id=task_id,
                    id=thought_id,
                )

        logger.info(f"[Neo4j] Thought '{thought_id}' stored for agent={agent_id}, task={task_id}")
        return thought_id

    except Exception as e:
        logger.exception(f"[Neo4j] Failed to store Thought: {e}")
        raise


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
        # (Chroma + embedding model run in-process; nothing special to close)
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


class EmbedRequest(BaseModel):
    text: str


class ThoughtRequest(BaseModel):
    agent_id: str
    task_id: Optional[str] = None
    content: str
    step_index: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class SimilarAgentDescriptionRequest(BaseModel):
    # Optional “structured” fields you already use in metadata
    role: Optional[str] = None
    goal: Optional[str] = None
    backstory: Optional[str] = None
    description: Optional[str] = None
    expected_output: Optional[str] = None
    agent: Optional[str] = None

    # Optional raw metadata dict (for extra fields / future-proofing)
    metadata: Optional[Dict[str, Any]] = None

    # Similarity can be 0–1 (0.85) or 0–100 (85)
    similarity: Optional[float] = AGENT_SIMILARITY_THRESHOLD
    limit: Optional[int] = AGENT_SIMILARITY_LIMIT


class SimilarTaskDescriptionRequest(BaseModel):
    # Optional “structured” fields you already use in metadata
    role: Optional[str] = None
    goal: Optional[str] = None
    backstory: Optional[str] = None
    description: Optional[str] = None
    expected_output: Optional[str] = None
    agent: Optional[str] = None

    # Optional raw metadata dict (for extra fields / future-proofing)
    metadata: Optional[Dict[str, Any]] = None

    # Similarity can be 0–1 (0.85) or 0–100 (85)
    similarity: Optional[float] = AGENT_SIMILARITY_THRESHOLD
    limit: Optional[int] = AGENT_SIMILARITY_LIMIT


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------
# FASTAPI APP
# ---------------------------------------------------------------

app = FastAPI(title="Agent Registry System", lifespan=lifespan)


# ---------------------------------------------------------------
# SIMPLE UI AUTH (TEST ONLY)
# ---------------------------------------------------------------

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"  # NOTE: hardwired for tests only, DO NOT use in production

SESSION_TTL_SECONDS = 3600  # 1 hour
SESSIONS: Dict[str, Dict[str, Any]] = {}  # in-memory session store


def _create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "username": username,
        "created_at": time.time(),
        "expires_at": time.time() + SESSION_TTL_SECONDS,
    }
    return token


def _get_session(token: str) -> Optional[Dict[str, Any]]:
    sess = SESSIONS.get(token)
    if not sess:
        return None
    if sess["expires_at"] < time.time():
        SESSIONS.pop(token, None)
        return None
    return sess


def get_current_user(session_token: Optional[str] = Cookie(default=None)) -> str:
    """
    Dependency for UI endpoints. Uses an HTTP-only cookie-based session.
    """
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sess = _get_session(session_token)
    if not sess:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    return sess["username"]


@app.post("/auth/login")
async def login(body: LoginRequest):
    """
    Very basic username/password login.
    Hardwired admin/admin for testing only.
    """
    if body.username != ADMIN_USERNAME or body.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _create_session(body.username)
    resp = JSONResponse({"status": "ok", "username": body.username})
    resp.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=False,  # set to True when using HTTPS
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return resp


@app.post("/auth/logout")
async def logout(session_token: Optional[str] = Cookie(default=None)):
    if session_token and session_token in SESSIONS:
        SESSIONS.pop(session_token, None)
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie("session_token")
    return resp


@app.get("/auth/me")
async def auth_me(user: str = Depends(get_current_user)):
    """
    Check current UI session.
    """
    return {"username": user}


# ---------------------------------------------------------------
# JSON-RPC HANDLER
# ---------------------------------------------------------------

async def handle_json_rpc(
    body: BaseModel,
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
            similar_agents = chroma_find_similar_agents_from_metadata(
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

        # Store in Chroma (best effort)
        meta = record.get("metadata", {}) or {}
        if is_task:
            chroma_upsert_task(uid, meta)
        else:
            chroma_upsert_agent(uid, meta)

        # Store in Neo4j
        if is_task:
            neo4j_upsert_task(uid, meta)
            if agent_id:
                neo4j_link_task_to_agent(uid, agent_id)
        else:
            neo4j_upsert_agent(uid, meta)

        result_payload: Dict[str, Any] = {
            "status": "ok",
            "id": uid,
            "collection": "tasks" if is_task else "agents",
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
# UI PROXY ENDPOINTS (SESSION-BASED AUTH)
# ---------------------------------------------------------------

@app.get("/ui/couch/agents")
async def ui_couch_agents(
    user: str = Depends(get_current_user),
    limit: int = 100,
    skip: int = 0,
):
    """
    List agent documents for the UI (session auth).
    """
    docs = _couch_list_by_type(COUCH_AGENT_COLLECTION, limit=limit, skip=skip)
    return {"count": len(docs), "items": docs}


@app.get("/ui/couch/tasks")
async def ui_couch_tasks(
    user: str = Depends(get_current_user),
    limit: int = 100,
    skip: int = 0,
):
    """
    List task documents for the UI (session auth).
    """
    docs = _couch_list_by_type(COUCH_TASK_COLLECTION, limit=limit, skip=skip)
    return {"count": len(docs), "items": docs}


@app.post("/ui/agents")
async def ui_create_agent(
    body: AgentRequest,
    user: str = Depends(get_current_user),
):
    """
    Create an agent via JSON-RPC for the UI (session-authenticated).
    """
    return await handle_json_rpc(
        body,
        type_tag=COUCH_AGENT_COLLECTION,
        is_task=False,
        with_similarity_search=True,
        similarity_threshold=AGENT_SIMILARITY_THRESHOLD,
    )


@app.post("/ui/tasks")
async def ui_create_task(
    body: TaskRequest,
    user: str = Depends(get_current_user),
):
    """
    Create a task via JSON-RPC for the UI (session-authenticated).
    """
    return await handle_json_rpc(
        body,
        type_tag=COUCH_TASK_COLLECTION,
        is_task=True,
    )


# ---------------------------------------------------------------
# RPC ENDPOINTS (API KEY AUTH)
# ---------------------------------------------------------------

@app.post("/agents")
async def rpc_agents(body: AgentRequest, x_api_key: str = Header(...)):
    authenticate_request(x_api_key)
    return await handle_json_rpc(
        body,
        type_tag=COUCH_AGENT_COLLECTION,
        is_task=False,
        with_similarity_search=True,
        similarity_threshold=AGENT_SIMILARITY_THRESHOLD,
    )


@app.post("/tasks")
async def rpc_tasks(body: TaskRequest, x_api_key: str = Header(...)):
    authenticate_request(x_api_key)
    return await handle_json_rpc(
        body,
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
# CHROMA READ-ONLY ENDPOINTS
# ---------------------------------------------------------------

@app.get("/chroma/agents")
async def chroma_agents_list(
    x_api_key: str = Header(...),
    limit: int = 100,
):
    """
    List agent vectors stored in Chroma (ids + metadata).
    """
    authenticate_request(x_api_key)
    if chroma_agents is None:
        raise HTTPException(status_code=503, detail="Chroma agents collection not available")

    try:
        res = chroma_agents.get(include=["metadatas"], limit=limit)
        ids = res.get("ids", [])
        metas = res.get("metadatas", [])
        items: List[Dict[str, Any]] = []
        for id_, meta in zip(ids, metas):
            items.append({"id": id_, "metadata": meta})
        return {"count": len(items), "items": items}
    except Exception as e:
        logger.warning(f"[Chroma] Agents list failed: {e}")
        raise HTTPException(status_code=500, detail="Chroma agents list failed")


@app.get("/chroma/tasks")
async def chroma_tasks_list(
    x_api_key: str = Header(...),
    limit: int = 100,
):
    """
    List task vectors stored in Chroma (ids + metadata).
    """
    authenticate_request(x_api_key)
    if chroma_tasks is None:
        raise HTTPException(status_code=503, detail="Chroma tasks collection not available")

    try:
        res = chroma_tasks.get(include=["metadatas"], limit=limit)
        ids = res.get("ids", [])
        metas = res.get("metadatas", [])
        items: List[Dict[str, Any]] = []
        for id_, meta in zip(ids, metas):
            items.append({"id": id_, "metadata": meta})
        return {"count": len(items), "items": items}
    except Exception as e:
        logger.warning(f"[Chroma] Tasks list failed: {e}")
        raise HTTPException(status_code=500, detail="Chroma tasks list failed")


# ---------------------------------------------------------------
# NEW: SIMILARITY SEARCH ENDPOINTS
# ---------------------------------------------------------------

@app.get("/similar/tasks")
async def similar_tasks(
    task_id: str,
    x_api_key: str = Header(...),
    threshold: float = 0.85,
    limit: int = 10,
):
    authenticate_request(x_api_key)

    if chroma_tasks is None:
        raise HTTPException(status_code=503, detail="Chroma tasks collection unavailable")

    similar = chroma_find_similar_items(
        chroma_tasks, task_id, threshold, limit
    )

    return {
        "task_id": task_id,
        "count": len(similar),
        "threshold": threshold,
        "items": similar,
    }


@app.get("/similar/agents")
async def similar_agents(
    agent_id: str,
    x_api_key: str = Header(...),
    threshold: float = 0.85,
    limit: int = 10,
):
    authenticate_request(x_api_key)

    if chroma_agents is None:
        raise HTTPException(status_code=503, detail="Chroma agents collection unavailable")

    similar = chroma_find_similar_items(
        chroma_agents, agent_id, threshold, limit
    )

    return {
        "agent_id": agent_id,
        "count": len(similar),
        "threshold": threshold,
        "items": similar,
    }


# ---------------------------------------------------------------
# EMBEDDING ENDPOINT
# ---------------------------------------------------------------

@app.post("/embed")
async def embed_text(req: EmbedRequest, x_api_key: str = Header(...)):
    """
    Produce a text embedding using the local SentenceTransformers model.
    Requires: {"text": "your text here"}
    """
    authenticate_request(x_api_key)

    if embedding_model is None:
        raise HTTPException(status_code=503, detail="Embedding model not initialized")

    try:
        vec = encode_text(req.text)
        if vec is None:
            raise RuntimeError("Could not produce embedding")

        return {
            "status": "ok",
            "text": req.text,
            "embedding_dim": len(vec),
            "embedding": vec,
        }

    except Exception as e:
        logger.exception(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e}")


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


@app.post("/thoughts")
async def create_thought(body: ThoughtRequest, x_api_key: str = Header(...)):
    """
    Store a chain-of-thought snippet in Neo4j as a Thought node.
    """
    authenticate_request(x_api_key)

    try:
        thought_id = neo4j_store_thought(
            agent_id=body.agent_id,
            task_id=body.task_id,
            content=body.content,
            step_index=body.step_index,
            metadata=body.metadata,
        )

        return {
            "status": "ok",
            "thought_id": thought_id,
            "agent_id": body.agent_id,
            "task_id": body.task_id,
        }

    except Exception as e:
        logger.exception("Failed to store thought")
        raise HTTPException(status_code=500, detail=f"Error storing thought: {e}")


# ---------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------

@app.post("/similar/agents/description")
async def similar_agents_by_description(
    body: SimilarAgentDescriptionRequest,
    x_api_key: str = Header(...),
):
    """
    Given agent metadata-ish fields and a similarity threshold, return similar agents
    from Chroma. 'similarity' can be 0–1 (0.85) or 0–100 (85).
    """
    authenticate_request(x_api_key)

    if chroma_agents is None:
        raise HTTPException(status_code=503, detail="Chroma agents collection unavailable")

    if embedding_model is None:
        raise HTTPException(status_code=503, detail="Embedding model not initialized")

    # Normalize similarity: accept 0–1 or 0–100
    raw_sim = body.similarity if body.similarity is not None else AGENT_SIMILARITY_THRESHOLD
    if raw_sim <= 0:
        effective_threshold = 0.0
    else:
        effective_threshold = raw_sim if raw_sim <= 1.0 else raw_sim / 100.0

    # Build a metadata dict consistent with what we store in Couch/Chroma
    meta: Dict[str, Any] = {}

    # Start from raw metadata if provided
    if body.metadata:
        meta.update(body.metadata)

    # Overlay structured fields (so explicit top-level fields win)
    for field_name in ["role", "goal", "backstory", "description", "expected_output", "agent"]:
        val = getattr(body, field_name)
        if val is not None:
            meta[field_name] = val

    if not meta:
        raise HTTPException(
            status_code=400,
            detail="At least one of role, goal, backstory, description, expected_output, agent, or metadata must be provided",
        )

    # Reuse the same helper used during /agents creation
    items = chroma_find_similar_agents_from_metadata(
        meta,
        threshold=effective_threshold,
        limit=body.limit or AGENT_SIMILARITY_LIMIT,
    )

    return {
        "count": len(items),
        "threshold": effective_threshold,
        "similarity_input": raw_sim,
        "items": items,
    }


@app.post("/similar/tasks/description")
async def similar_tasks_by_description(
    body: SimilarTaskDescriptionRequest,
    x_api_key: str = Header(...),
):
    """
    Given task metadata-ish fields and a similarity threshold, return similar tasks
    from Chroma. 'similarity' can be 0–1 (0.85) or 0–100 (85).
    """
    authenticate_request(x_api_key)

    if chroma_tasks is None:
        raise HTTPException(status_code=503, detail="Chroma tasks collection unavailable")

    if embedding_model is None:
        raise HTTPException(status_code=503, detail="Embedding model not initialized")

    # Normalize similarity: accept 0–1 or 0–100
    raw_sim = body.similarity if body.similarity is not None else AGENT_SIMILARITY_THRESHOLD
    if raw_sim <= 0:
        effective_threshold = 0.0
    else:
        effective_threshold = raw_sim if raw_sim <= 1.0 else raw_sim / 100.0

    # Build a metadata dict consistent with what we store in Couch/Chroma
    meta: Dict[str, Any] = {}

    # Start from raw metadata if provided
    if body.metadata:
        meta.update(body.metadata)

    # Overlay structured fields (so explicit top-level fields win)
    for field_name in ["role", "goal", "backstory", "description", "expected_output", "agent"]:
        val = getattr(body, field_name)
        if val is not None:
            meta[field_name] = val

    if not meta:
        raise HTTPException(
            status_code=400,
            detail="At least one of role, goal, backstory, description, expected_output, agent, or metadata must be provided",
        )

    # Reuse the same pattern as /similar/agents/description but for tasks
    items = chroma_find_similar_tasks_from_metadata(
        meta,
        threshold=effective_threshold,
        limit=body.limit or AGENT_SIMILARITY_LIMIT,
    )

    return {
        "count": len(items),
        "threshold": effective_threshold,
        "similarity_input": raw_sim,
        "items": items,
    }


# ---------------------------------------------------------------
# METRICS ENDPOINT
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

    # Chroma
    try:
        if chroma_client:
            hb = chroma_client.heartbeat()
            result["chroma"] = True
            result["chroma_heartbeat"] = hb
        else:
            result["chroma"] = False
    except Exception as e:
        result["chroma"] = False
        result["chroma_error"] = str(e)
        logger.warning(f"Chroma health check failed: {e}")

    # Embedding model
    result["embedding_model"] = embedding_model is not None

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
# SIMPLE MODERN UI (TAILWIND + VANILLA JS)
# ---------------------------------------------------------------

INDEX_HTML = INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Agent Registry Admin</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
  <div class="min-h-screen flex flex-col">
    <!-- Top Bar -->
    <header class="border-b border-slate-800 bg-slate-900/70 backdrop-blur">
      <div class="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="h-8 w-8 rounded-xl bg-indigo-500 flex items-center justify-center text-xs font-bold">
            AR
          </div>
          <div>
            <h1 class="text-lg font-semibold">Agent Registry Admin</h1>
            <p class="text-xs text-slate-400">CouchDB · Chroma · Neo4j</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <span id="userLabel" class="text-sm text-slate-400 hidden"></span>
          <button id="logoutBtn" class="hidden px-3 py-1.5 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700">
            Logout
          </button>
        </div>
      </div>
    </header>

    <!-- Main -->
    <main class="flex-1 mx-auto max-w-6xl w-full px-4 py-6">
      <!-- Login Card -->
      <section id="loginSection" class="flex justify-center items-center min-h-[60vh]">
        <div class="w-full max-w-sm bg-slate-900/70 border border-slate-800 rounded-2xl p-6 shadow-xl shadow-black/40">
          <h2 class="text-xl font-semibold mb-1">Sign in</h2>
          <p class="text-sm text-slate-400 mb-4">Use <span class="font-mono text-slate-200">admin / admin</span> (demo only).</p>

          <form id="loginForm" class="space-y-3">
            <div>
              <label class="block text-xs font-medium text-slate-300 mb-1" for="username">Username</label>
              <input id="username" name="username" type="text" autocomplete="username"
                     class="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-300 mb-1" for="password">Password</label>
              <input id="password" name="password" type="password" autocomplete="current-password"
                     class="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <button type="submit"
                    class="w-full mt-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-3 py-2 text-sm font-medium">
              Sign in
            </button>
          </form>

          <p id="loginError" class="mt-3 text-xs text-red-400 hidden"></p>
        </div>
      </section>

      <!-- Dashboard -->
      <section id="dashboardSection" class="hidden space-y-6">
        <!-- Status + Create Forms -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Health -->
          <div class="col-span-1 md:col-span-2 bg-slate-900/70 border border-slate-800 rounded-2xl p-4">
            <div class="flex items-center justify-between mb-2">
              <h2 class="text-sm font-semibold text-slate-100">System Health</h2>
              <button id="refreshHealthBtn"
                      class="px-3 py-1.5 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700">
                Refresh
              </button>
            </div>
            <pre id="healthOutput" class="text-xs text-slate-300 bg-slate-950/70 rounded-lg p-3 overflow-x-auto max-h-40"></pre>
          </div>

          <!-- Create Agent / Task -->
          <div class="space-y-4">
            <!-- Create Agent -->
            <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 space-y-3">
              <div>
                <h2 class="text-sm font-semibold text-slate-100 mb-1">Create Agent</h2>
                <p class="text-xs text-slate-400">Quickly spin up a new agent record.</p>
              </div>
              <form id="createAgentForm" class="space-y-2">
                <input name="role" placeholder="Role (e.g. Researcher)" class="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs" />
                <input name="goal" placeholder="Goal" class="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs" />
                <input name="backstory" placeholder="Backstory" class="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs" />
                <input name="description" placeholder="Description" class="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs" />
                <button type="submit"
                        class="w-full mt-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 text-xs font-medium">
                  Create Agent
                </button>
              </form>
              <p id="createAgentResult" class="text-xs text-slate-300"></p>
            </div>

            <!-- Create Task -->
            <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 space-y-3">
              <div>
                <h2 class="text-sm font-semibold text-slate-100 mb-1">Create Task</h2>
                <p class="text-xs text-slate-400">
                  Link a task to an existing agent (Neo4j must contain the agent).
                </p>
              </div>
              <form id="createTaskForm" class="space-y-2">
                <input name="agent_id" placeholder="Agent ID (shortid)" class="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs" />
                <input name="role" placeholder="Role / type" class="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs" />
                <input name="goal" placeholder="Goal" class="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs" />
                <input name="description" placeholder="Description" class="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs" />
                <button type="submit"
                        class="w-full mt-1 rounded-lg bg-sky-600 hover:bg-sky-500 px-3 py-1.5 text-xs font-medium">
                  Create Task
                </button>
              </form>
              <p id="createTaskResult" class="text-xs text-slate-300"></p>
            </div>
          </div>
        </div>

        <!-- Agents + Tasks Tables -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <!-- Agents Table -->
          <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-4">
            <div class="flex items-center justify-between mb-3">
              <div>
                <h2 class="text-sm font-semibold text-slate-100">Agents</h2>
                <p class="text-xs text-slate-400">Listing from CouchDB (UI proxy).</p>
              </div>
              <button id="refreshAgentsBtn"
                      class="px-3 py-1.5 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700">
                Refresh
              </button>
            </div>
            <div class="overflow-x-auto">
              <table class="min-w-full text-xs border-collapse">
                <thead class="bg-slate-950/80">
                  <tr>
                    <th class="px-3 py-2 text-left font-medium text-slate-300 border-b border-slate-800">ID</th>
                    <th class="px-3 py-2 text-left font-medium text-slate-300 border-b border-slate-800">Role</th>
                    <th class="px-3 py-2 text-left font-medium text-slate-300 border-b border-slate-800">Goal</th>
                    <th class="px-3 py-2 text-left font-medium text-slate-300 border-b border-slate-800">Description</th>
                    <th class="px-3 py-2 text-left font-medium text-slate-300 border-b border-slate-800">Created</th>
                  </tr>
                </thead>
                <tbody id="agentsTableBody" class="divide-y divide-slate-800">
                </tbody>
              </table>
            </div>
          </div>

          <!-- Tasks Table -->
          <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-4">
            <div class="flex items-center justify-between mb-3">
              <div>
                <h2 class="text-sm font-semibold text-slate-100">Tasks</h2>
                <p class="text-xs text-slate-400">Listing from CouchDB (UI proxy).</p>
              </div>
              <button id="refreshTasksBtn"
                      class="px-3 py-1.5 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700">
                Refresh
              </button>
            </div>
            <div class="overflow-x-auto">
              <table class="min-w-full text-xs border-collapse">
                <thead class="bg-slate-950/80">
                  <tr>
                    <th class="px-3 py-2 text-left font-medium text-slate-300 border-b border-slate-800">ID</th>
                    <th class="px-3 py-2 text-left font-medium text-slate-300 border-b border-slate-800">Agent ID</th>
                    <th class="px-3 py-2 text-left font-medium text-slate-300 border-b border-slate-800">Role / Type</th>
                    <th class="px-3 py-2 text-left font-medium text-slate-300 border-b border-slate-800">Goal</th>
                    <th class="px-3 py-2 text-left font-medium text-slate-300 border-b border-slate-800">Created</th>
                  </tr>
                </thead>
                <tbody id="tasksTableBody" class="divide-y divide-slate-800">
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>

  <script>
    const loginSection = document.getElementById("loginSection");
    const dashboardSection = document.getElementById("dashboardSection");
    const loginForm = document.getElementById("loginForm");
    const loginError = document.getElementById("loginError");
    const userLabel = document.getElementById("userLabel");
    const logoutBtn = document.getElementById("logoutBtn");
    const healthOutput = document.getElementById("healthOutput");
    const refreshHealthBtn = document.getElementById("refreshHealthBtn");
    const createAgentForm = document.getElementById("createAgentForm");
    const createAgentResult = document.getElementById("createAgentResult");
    const createTaskForm = document.getElementById("createTaskForm");
    const createTaskResult = document.getElementById("createTaskResult");
    const refreshAgentsBtn = document.getElementById("refreshAgentsBtn");
    const agentsTableBody = document.getElementById("agentsTableBody");
    const refreshTasksBtn = document.getElementById("refreshTasksBtn");
    const tasksTableBody = document.getElementById("tasksTableBody");

    function showLogin() {
      loginSection.classList.remove("hidden");
      dashboardSection.classList.add("hidden");
      logoutBtn.classList.add("hidden");
      userLabel.classList.add("hidden");
      loginError.classList.add("hidden");
      loginError.textContent = "";
    }

    function showDashboard(username) {
      loginSection.classList.add("hidden");
      dashboardSection.classList.remove("hidden");
      logoutBtn.classList.remove("hidden");
      userLabel.classList.remove("hidden");
      userLabel.textContent = "Logged in as " + username;
      fetchHealth();
      fetchAgents();
      fetchTasks();
    }

    async function checkSession() {
      try {
        const res = await fetch("/auth/me", {
          method: "GET",
          credentials: "include",
        });
        if (res.ok) {
          const data = await res.json();
          showDashboard(data.username);
        } else {
          showLogin();
        }
      } catch (e) {
        console.error(e);
        showLogin();
      }
    }

    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      loginError.classList.add("hidden");
      loginError.textContent = "";

      const formData = new FormData(loginForm);
      const username = formData.get("username") || "";
      const password = formData.get("password") || "";

      try {
        const res = await fetch("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ username, password }),
        });

        if (!res.ok) {
          loginError.textContent = "Invalid credentials.";
          loginError.classList.remove("hidden");
          return;
        }

        const data = await res.json();
        showDashboard(data.username);
      } catch (err) {
        console.error(err);
        loginError.textContent = "Login failed. See console for details.";
        loginError.classList.remove("hidden");
      }
    });

    logoutBtn.addEventListener("click", async () => {
      try {
        await fetch("/auth/logout", {
          method: "POST",
          credentials: "include",
        });
      } catch (e) {
        console.error(e);
      }
      showLogin();
    });

    async function fetchHealth() {
      healthOutput.textContent = "Loading...";
      try {
        const res = await fetch("/healthz", {
          method: "GET",
          credentials: "include",
        });
        const data = await res.json();
        healthOutput.textContent = JSON.stringify(data, null, 2);
      } catch (e) {
        console.error(e);
        healthOutput.textContent = "Failed to load health info.";
      }
    }

    refreshHealthBtn.addEventListener("click", fetchHealth);

    async function fetchAgents() {
      agentsTableBody.innerHTML = "";
      try {
        const res = await fetch("/ui/couch/agents?limit=100", {
          method: "GET",
          credentials: "include",
        });
        if (!res.ok) {
          agentsTableBody.innerHTML = "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>Failed to load agents.</td></tr>";
          return;
        }
        const data = await res.json();
        if (!data.items || data.items.length === 0) {
          agentsTableBody.innerHTML = "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>No agents yet.</td></tr>";
          return;
        }
        for (const doc of data.items) {
          const tr = document.createElement("tr");
          const metadata = doc.metadata || {};
          const createdAt = doc.created_at || doc._id || "";
          const idVal = (doc.id || doc._id || "").toString();
          const role = (metadata.role || "").toString();
          const goal = (metadata.goal || "").toString();
          const description = (metadata.description || "").toString();
          tr.innerHTML = `
            <td class="px-3 py-2 font-mono text-[11px] text-slate-200">${idVal}</td>
            <td class="px-3 py-2 text-slate-200">${role}</td>
            <td class="px-3 py-2 text-slate-200">${goal}</td>
            <td class="px-3 py-2 text-slate-200 max-w-xs truncate" title="${description}">${description}</td>
            <td class="px-3 py-2 text-slate-400 text-[11px]">${createdAt}</td>
          `;
          agentsTableBody.appendChild(tr);
        }
      } catch (e) {
        console.error(e);
        agentsTableBody.innerHTML = "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>Error loading agents.</td></tr>";
      }
    }

    refreshAgentsBtn.addEventListener("click", fetchAgents);

    async function fetchTasks() {
      tasksTableBody.innerHTML = "";
      try {
        const res = await fetch("/ui/couch/tasks?limit=100", {
          method: "GET",
          credentials: "include",
        });
        if (!res.ok) {
          tasksTableBody.innerHTML = "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>Failed to load tasks.</td></tr>";
          return;
        }
        const data = await res.json();
        if (!data.items || data.items.length === 0) {
          tasksTableBody.innerHTML = "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>No tasks yet.</td></tr>";
          return;
        }
        for (const doc of data.items) {
          const tr = document.createElement("tr");
          const metadata = doc.metadata || {};
          const createdAt = doc.created_at || doc._id || "";
          const idVal = (doc.id || doc._id || "").toString();
          const agentId = (doc.agent_id || "").toString();
          const role = (metadata.role || "").toString();
          const goal = (metadata.goal || "").toString();
          tr.innerHTML = `
            <td class="px-3 py-2 font-mono text-[11px] text-slate-200">${idVal}</td>
            <td class="px-3 py-2 font-mono text-[11px] text-slate-300">${agentId}</td>
            <td class="px-3 py-2 text-slate-200">${role}</td>
            <td class="px-3 py-2 text-slate-200 max-w-xs truncate" title="${goal}">${goal}</td>
            <td class="px-3 py-2 text-slate-400 text-[11px]">${createdAt}</td>
          `;
          tasksTableBody.appendChild(tr);
        }
      } catch (e) {
        console.error(e);
        tasksTableBody.innerHTML = "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>Error loading tasks.</td></tr>";
      }
    }

    refreshTasksBtn.addEventListener("click", fetchTasks);

    createAgentForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      createAgentResult.textContent = "";
      const formData = new FormData(createAgentForm);
      const metadata = {
        role: formData.get("role") || "",
        goal: formData.get("goal") || "",
        backstory: formData.get("backstory") || "",
        description: formData.get("description") || "",
      };

      try {
        const body = {
          method: "create_id",
          params: { metadata },
          id: "ui",
        };
        const res = await fetch("/ui/agents", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          createAgentResult.textContent = "Failed to create agent.";
          return;
        }
        const data = await res.json();
        const newId = (data.result && data.result.id) || "unknown";
        createAgentResult.textContent = "Created agent ID: " + newId;
        createAgentForm.reset();
        fetchAgents();
      } catch (e) {
        console.error(e);
        createAgentResult.textContent = "Error creating agent.";
      }
    });

    createTaskForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      createTaskResult.textContent = "";
      const formData = new FormData(createTaskForm);
      const agent_id = (formData.get("agent_id") || "").toString().trim();
      const metadata = {
        role: formData.get("role") || "",
        goal: formData.get("goal") || "",
        description: formData.get("description") || "",
      };

      if (!agent_id) {
        createTaskResult.textContent = "Agent ID is required.";
        return;
      }

      try {
        const body = {
          method: "create_id",
          params: { agent_id, metadata },
          id: "ui-task",
        };
        const res = await fetch("/ui/tasks", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!res.ok || data.error) {
          const message =
            (data.error && data.error.message) ||
            "Failed to create task.";
          createTaskResult.textContent = message;
          return;
        }
        const newId = (data.result && data.result.id) || "unknown";
        createTaskResult.textContent = "Created task ID: " + newId;
        createTaskForm.reset();
        fetchTasks();
      } catch (e) {
        console.error(e);
        createTaskResult.textContent = "Error creating task.";
      }
    });

    // init
    checkSession();
  </script>
</body>
</html>
"""



@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(INDEX_HTML)


# ---------------------------------------------------------------
# MAIN ENTRYPOINT
# ---------------------------------------------------------------

if __name__ == "__main__":
    logger.info(f"Starting Agent Registry System on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
