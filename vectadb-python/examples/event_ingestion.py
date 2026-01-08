"""Event ingestion example for agent observability."""

from datetime import datetime
from vectadb import VectaDB

def main():
    # Initialize client
    client = VectaDB(base_url="http://localhost:8080")

    print("🔍 Agent Observability Event Ingestion Example\n")

    # Ingest a single event
    print("📝 Ingesting single event...")
    event = {
        "event_type": "agent.task.started",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agent_id": "agent-123",
        "metadata": {
            "task_id": "task-456",
            "task_type": "data_analysis",
            "priority": "high"
        },
        "context": {
            "model": "gpt-4",
            "temperature": 0.7
        }
    }

    response = client.events.ingest(event)
    print(f"Event ingested: {response.event_id}")
    print(f"Status: {response.status}")

    # Ingest batch of events
    print("\n📦 Ingesting batch of events...")
    events = [
        {
            "event_type": "agent.llm.call",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent_id": "agent-123",
            "metadata": {
                "model": "gpt-4",
                "prompt_tokens": 150,
                "completion_tokens": 75,
                "total_tokens": 225
            }
        },
        {
            "event_type": "agent.tool.used",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent_id": "agent-123",
            "metadata": {
                "tool_name": "web_search",
                "query": "latest ML research"
            }
        },
        {
            "event_type": "agent.task.completed",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent_id": "agent-123",
            "metadata": {
                "task_id": "task-456",
                "duration_ms": 5432,
                "success": True
            }
        }
    ]

    batch_response = client.events.ingest_batch(events)
    print(f"Batch ingested: {batch_response.batch_id}")
    print(f"Total events: {batch_response.total}")
    print(f"Successful: {batch_response.successful}")
    print(f"Failed: {batch_response.failed}")

    if batch_response.errors:
        print("\n⚠️ Errors:")
        for error in batch_response.errors:
            print(f"  - {error}")

    print("\n✨ Event ingestion completed!")

if __name__ == "__main__":
    main()
