"""Tests for asynchronous VectaDB client."""

import pytest
from vectadb import AsyncVectaDB
from vectadb.exceptions import NotFoundError


@pytest.fixture
async def client():
    """Create test client."""
    async with AsyncVectaDB(base_url="http://localhost:8080") as c:
        yield c


@pytest.fixture
def test_schema():
    """Create test schema."""
    return {
        "namespace": "test_async",
        "version": "1.0.0",
        "entity_types": [
            {
                "id": "TestEntity",
                "parent_type": None,
                "properties": {
                    "name": {
                        "type": "string",
                        "required": True,
                        "indexed": True
                    }
                }
            }
        ],
        "relation_types": []
    }


class TestAsyncHealth:
    """Test async health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test server health check."""
        health = await client.health()
        assert health.status == "healthy"
        assert health.version is not None


class TestAsyncOntology:
    """Test async ontology API."""

    @pytest.mark.asyncio
    async def test_upload_schema(self, client, test_schema):
        """Test schema upload."""
        result = await client.ontology.upload_schema(test_schema)
        assert "message" in result

    @pytest.mark.asyncio
    async def test_get_schema(self, client, test_schema):
        """Test schema retrieval."""
        await client.ontology.upload_schema(test_schema)
        schema = await client.ontology.get_schema()
        assert schema.namespace == "test_async"
        assert schema.version == "1.0.0"


class TestAsyncEntities:
    """Test async entity API."""

    @pytest.mark.asyncio
    async def test_create_entity(self, client, test_schema):
        """Test entity creation."""
        await client.ontology.upload_schema(test_schema)

        entity = await client.entities.create(
            type="TestEntity",
            properties={"name": "Test"}
        )
        assert entity.id is not None
        assert entity.type == "TestEntity"

    @pytest.mark.asyncio
    async def test_get_entity(self, client, test_schema):
        """Test entity retrieval."""
        await client.ontology.upload_schema(test_schema)

        created = await client.entities.create(
            type="TestEntity",
            properties={"name": "Test"}
        )

        entity = await client.entities.get(created.id)
        assert entity.id == created.id

    @pytest.mark.asyncio
    async def test_update_entity(self, client, test_schema):
        """Test entity update."""
        await client.ontology.upload_schema(test_schema)

        created = await client.entities.create(
            type="TestEntity",
            properties={"name": "Original"}
        )

        updated = await client.entities.update(
            created.id,
            properties={"name": "Updated"}
        )
        assert updated.properties["name"] == "Updated"

    @pytest.mark.asyncio
    async def test_delete_entity(self, client, test_schema):
        """Test entity deletion."""
        await client.ontology.upload_schema(test_schema)

        created = await client.entities.create(
            type="TestEntity",
            properties={"name": "Test"}
        )

        result = await client.entities.delete(created.id)
        assert "message" in result

        with pytest.raises(NotFoundError):
            await client.entities.get(created.id)


class TestAsyncQueries:
    """Test async query API."""

    @pytest.mark.asyncio
    async def test_hybrid_query(self, client, test_schema):
        """Test hybrid query."""
        await client.ontology.upload_schema(test_schema)

        await client.entities.create(
            type="TestEntity",
            properties={"name": "Test Entity"}
        )

        results = await client.queries.hybrid(
            vector_query={
                "query_text": "test",
                "entity_types": ["TestEntity"],
                "limit": 10
            },
            merge_strategy="vector_only"
        )
        assert results is not None
        assert isinstance(results.results, list)


class TestAsyncEvents:
    """Test async event ingestion API."""

    @pytest.mark.asyncio
    async def test_ingest_single_event(self, client):
        """Test single event ingestion."""
        from datetime import datetime

        event = {
            "event_type": "test.event",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent_id": "test-agent",
            "metadata": {"test": "data"}
        }

        response = await client.events.ingest(event)
        assert response.event_id is not None
        assert response.status == "accepted"

    @pytest.mark.asyncio
    async def test_ingest_batch(self, client):
        """Test batch event ingestion."""
        from datetime import datetime

        events = [
            {
                "event_type": "test.event",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent_id": "test-agent-1",
                "metadata": {}
            },
            {
                "event_type": "test.event",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent_id": "test-agent-2",
                "metadata": {}
            }
        ]

        response = await client.events.ingest_batch(events)
        assert response.batch_id is not None
        assert response.total == 2
