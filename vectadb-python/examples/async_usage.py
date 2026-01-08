"""Async VectaDB usage example."""

import asyncio
from vectadb import AsyncVectaDB

async def main():
    # Use async context manager
    async with AsyncVectaDB(base_url="http://localhost:8080") as client:
        # Check server health
        health = await client.health()
        print(f"Server status: {health.status}")
        print(f"Version: {health.version}")

        # Upload ontology schema
        schema = {
            "namespace": "async_example",
            "version": "1.0.0",
            "entity_types": [
                {
                    "id": "Agent",
                    "parent_type": None,
                    "properties": {
                        "name": {
                            "type": "string",
                            "required": True,
                            "indexed": True
                        },
                        "model": {
                            "type": "string",
                            "required": True,
                            "indexed": True
                        },
                        "status": {
                            "type": "string",
                            "required": False,
                            "indexed": True
                        }
                    }
                },
                {
                    "id": "Task",
                    "parent_type": None,
                    "properties": {
                        "description": {
                            "type": "string",
                            "required": True,
                            "indexed": False
                        },
                        "status": {
                            "type": "string",
                            "required": True,
                            "indexed": True
                        }
                    }
                }
            ],
            "relation_types": [
                {
                    "id": "executes",
                    "source_type": "Agent",
                    "target_type": "Task",
                    "properties": {}
                }
            ]
        }

        print("\n📝 Uploading ontology schema...")
        result = await client.ontology.upload_schema(schema)
        print(f"Schema uploaded: {result['message']}")

        # Create multiple entities concurrently
        print("\n👥 Creating entities concurrently...")
        agent_task = client.entities.create(
            type="Agent",
            properties={
                "name": "GPT-4 Agent",
                "model": "gpt-4",
                "status": "active"
            }
        )
        task1_task = client.entities.create(
            type="Task",
            properties={
                "description": "Analyze customer data",
                "status": "pending"
            }
        )
        task2_task = client.entities.create(
            type="Task",
            properties={
                "description": "Generate report",
                "status": "pending"
            }
        )

        # Wait for all creations to complete
        agent, task1, task2 = await asyncio.gather(agent_task, task1_task, task2_task)
        print(f"Created agent: {agent.id} - {agent.properties['name']}")
        print(f"Created task 1: {task1.id} - {task1.properties['description']}")
        print(f"Created task 2: {task2.id} - {task2.properties['description']}")

        # Create relations concurrently
        print("\n🔗 Creating relations concurrently...")
        rel1_task = client.relations.create(
            type="executes",
            from_entity_id=agent.id,
            to_entity_id=task1.id
        )
        rel2_task = client.relations.create(
            type="executes",
            from_entity_id=agent.id,
            to_entity_id=task2.id
        )

        rel1, rel2 = await asyncio.gather(rel1_task, rel2_task)
        print(f"Created relation: {rel1.id} ({rel1.type})")
        print(f"Created relation: {rel2.id} ({rel2.type})")

        # Query
        print("\n🔍 Performing hybrid query...")
        results = await client.queries.hybrid(
            vector_query={
                "query_text": "data analysis tasks",
                "entity_types": ["Task"],
                "limit": 10
            },
            merge_strategy="vector_only"
        )
        print(f"Found {len(results.results)} results")
        for result in results.results:
            print(f"  - {result.entity.properties.get('description')} (score: {result.score:.3f})")

        # Update entities concurrently
        print("\n🔄 Updating task statuses...")
        update1_task = client.entities.update(
            task1.id,
            properties={"description": task1.properties["description"], "status": "completed"}
        )
        update2_task = client.entities.update(
            task2.id,
            properties={"description": task2.properties["description"], "status": "in_progress"}
        )

        await asyncio.gather(update1_task, update2_task)
        print("Tasks updated")

        # Clean up concurrently
        print("\n🧹 Cleaning up...")
        await asyncio.gather(
            client.relations.delete(rel1.id),
            client.relations.delete(rel2.id),
            client.entities.delete(agent.id),
            client.entities.delete(task1.id),
            client.entities.delete(task2.id)
        )
        print("Cleanup completed")

        print("\n✨ Async example completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
