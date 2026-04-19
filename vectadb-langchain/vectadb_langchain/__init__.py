"""
vectadb-langchain: VectaDB audit and observability for LangChain.

Quickstart (LCEL chain / agent)::

    from vectadb_langchain import VectaDBTracer

    tracer = VectaDBTracer(vectadb_url="http://localhost:8080")
    with tracer:
        result = chain.invoke(
            {"question": "What is RAG?"},
            config={"callbacks": [tracer.callback_handler]},
        )
    print(tracer.session_id)  # query VectaDB for this session's audit trail

Quickstart (VectorStore in a RAG chain)::

    from vectadb_langchain import VectaDBVectorStore

    store = VectaDBVectorStore(vectadb_url="http://localhost:8080", collection="docs")
    store.add_texts(["VectaDB is an ontology-native vector database..."])
    retriever = store.as_retriever(search_kwargs={"k": 3})

Quickstart (Chat message history)::

    from langchain_core.runnables.history import RunnableWithMessageHistory
    from vectadb_langchain import VectaDBChatMessageHistory

    chain_with_history = RunnableWithMessageHistory(
        chain,
        lambda session_id: VectaDBChatMessageHistory(
            session_id=session_id,
            vectadb_url="http://localhost:8080",
        ),
    )

Quickstart (LangGraph)::

    from langgraph.graph import StateGraph
    from vectadb_langchain import VectaDBLangGraphTracer

    tracer = VectaDBLangGraphTracer(vectadb_url="http://localhost:8080")
    builder = StateGraph(MyState)
    builder.add_node("planner",  tracer.traced_node("planner")(planner_fn))
    builder.add_node("executor", tracer.traced_node("executor")(executor_fn))
    graph = builder.compile()
    graph.invoke({"messages": [...]})
    tracer.flush()
"""

from .tracer import VectaDBTracer, create_tracer_from_env
from .callbacks import VectaDBCallbackHandler
from .vectorstore import VectaDBVectorStore
from .history import VectaDBChatMessageHistory
from .client import VectaDBClient, SyncVectaDBClient, VectaDBClientError
from .models import (
    VectaDBEvent,
    LangChainEventType,
    AgentRunState,
    RunState,
    BulkIngestionResponse,
    HealthResponse,
)

__version__ = "0.1.0"
__author__ = "Roberto Williams Batista"

__all__ = [
    # Main interfaces
    "VectaDBTracer",
    "create_tracer_from_env",
    "VectaDBCallbackHandler",
    "VectaDBVectorStore",
    "VectaDBChatMessageHistory",
    # HTTP clients
    "VectaDBClient",
    "SyncVectaDBClient",
    "VectaDBClientError",
    # Models
    "VectaDBEvent",
    "LangChainEventType",
    "AgentRunState",
    "RunState",
    "BulkIngestionResponse",
    "HealthResponse",
]

# LangGraph tracer is an optional import (requires `pip install vectadb-langchain[langgraph]`)
try:
    from .langgraph import VectaDBLangGraphTracer
    __all__.append("VectaDBLangGraphTracer")
except ImportError:
    pass
