"""Tests for synchronous VectaDB client."""

import pytest
from vectadb import VectaDB
from vectadb.exceptions import ConnectionError, NotFoundError, ValidationError


@pytest.fixture
def client():
    """Create test client."""
    return VectaDB(base_url="http://localhost:8080")


@pytest.fixture
def test_schema():
    """Create test schema."""
    return {
        "namespace": "test",
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


class TestHealth:
    """Test health check functionality."""

    def test_health_check(self, client):
        """Test server health check."""
        health = client.health()
        assert health.status == "healthy"
        assert health.version is not None


class TestOntology:
    """Test ontology API."""

    def test_upload_schema(self, client, test_schema):
        """Test schema upload."""
        result = client.ontology.upload_schema(test_schema)
        assert "message" in result

    def test_get_schema(self, client, test_schema):
        """Test schema retrieval."""
        # Upload first
        client.ontology.upload_schema(test_schema)

        # Retrieve
        schema = client.ontology.get_schema()
        assert schema.namespace == "test"
        assert schema.version == "1.0.0"

    def test_get_entity_type(self, client, test_schema):
        """Test entity type retrieval."""
        client.ontology.upload_schema(test_schema)

        entity_type = client.ontology.get_entity_type("TestEntity")
        assert entity_type.id == "TestEntity"
        assert "name" in entity_type.properties


class TestEntities:
    """Test entity API."""

    def test_create_entity(self, client, test_schema):
        """Test entity creation."""
        client.ontology.upload_schema(test_schema)

        entity = client.entities.create(
            type="TestEntity",
            properties={"name": "Test"}
        )
        assert entity.id is not None
        assert entity.type == "TestEntity"
        assert entity.properties["name"] == "Test"

    def test_get_entity(self, client, test_schema):
        """Test entity retrieval."""
        client.ontology.upload_schema(test_schema)

        # Create entity
        created = client.entities.create(
            type="TestEntity",
            properties={"name": "Test"}
        )

        # Retrieve entity
        entity = client.entities.get(created.id)
        assert entity.id == created.id
        assert entity.properties["name"] == "Test"

    def test_update_entity(self, client, test_schema):
        """Test entity update."""
        client.ontology.upload_schema(test_schema)

        # Create entity
        created = client.entities.create(
            type="TestEntity",
            properties={"name": "Original"}
        )

        # Update entity
        updated = client.entities.update(
            created.id,
            properties={"name": "Updated"}
        )
        assert updated.properties["name"] == "Updated"

    def test_delete_entity(self, client, test_schema):
        """Test entity deletion."""
        client.ontology.upload_schema(test_schema)

        # Create entity
        created = client.entities.create(
            type="TestEntity",
            properties={"name": "Test"}
        )

        # Delete entity
        result = client.entities.delete(created.id)
        assert "message" in result

        # Verify deletion
        with pytest.raises(NotFoundError):
            client.entities.get(created.id)

    def test_validate_entity(self, client, test_schema):
        """Test entity validation."""
        client.ontology.upload_schema(test_schema)

        # Valid entity
        validation = client.entities.validate(
            type="TestEntity",
            properties={"name": "Valid"}
        )
        assert validation.valid is True

        # Invalid entity (missing required field)
        validation = client.entities.validate(
            type="TestEntity",
            properties={}
        )
        assert validation.valid is False


class TestRelations:
    """Test relation API."""

    def test_create_relation(self, client):
        """Test relation creation."""
        # Need to set up schema and entities first
        schema = {
            "namespace": "test",
            "version": "1.0.0",
            "entity_types": [
                {
                    "id": "Person",
                    "parent_type": None,
                    "properties": {"name": {"type": "string", "required": True, "indexed": True}}
                }
            ],
            "relation_types": [
                {
                    "id": "knows",
                    "source_type": "Person",
                    "target_type": "Person",
                    "properties": {}
                }
            ]
        }
        client.ontology.upload_schema(schema)

        # Create entities
        person1 = client.entities.create(type="Person", properties={"name": "Alice"})
        person2 = client.entities.create(type="Person", properties={"name": "Bob"})

        # Create relation
        relation = client.relations.create(
            type="knows",
            from_entity_id=person1.id,
            to_entity_id=person2.id
        )
        assert relation.id is not None
        assert relation.type == "knows"

    def test_get_relation(self, client):
        """Test relation retrieval."""
        # Setup
        schema = {
            "namespace": "test",
            "version": "1.0.0",
            "entity_types": [
                {
                    "id": "Person",
                    "parent_type": None,
                    "properties": {"name": {"type": "string", "required": True, "indexed": True}}
                }
            ],
            "relation_types": [
                {
                    "id": "knows",
                    "source_type": "Person",
                    "target_type": "Person",
                    "properties": {}
                }
            ]
        }
        client.ontology.upload_schema(schema)

        person1 = client.entities.create(type="Person", properties={"name": "Alice"})
        person2 = client.entities.create(type="Person", properties={"name": "Bob"})
        created = client.relations.create(
            type="knows",
            from_entity_id=person1.id,
            to_entity_id=person2.id
        )

        # Get relation
        relation = client.relations.get(created.id)
        assert relation.id == created.id

    def test_delete_relation(self, client):
        """Test relation deletion."""
        # Setup
        schema = {
            "namespace": "test",
            "version": "1.0.0",
            "entity_types": [
                {
                    "id": "Person",
                    "parent_type": None,
                    "properties": {"name": {"type": "string", "required": True, "indexed": True}}
                }
            ],
            "relation_types": [
                {
                    "id": "knows",
                    "source_type": "Person",
                    "target_type": "Person",
                    "properties": {}
                }
            ]
        }
        client.ontology.upload_schema(schema)

        person1 = client.entities.create(type="Person", properties={"name": "Alice"})
        person2 = client.entities.create(type="Person", properties={"name": "Bob"})
        created = client.relations.create(
            type="knows",
            from_entity_id=person1.id,
            to_entity_id=person2.id
        )

        # Delete relation
        result = client.relations.delete(created.id)
        assert "message" in result


class TestQueries:
    """Test query API."""

    def test_hybrid_query(self, client, test_schema):
        """Test hybrid query."""
        client.ontology.upload_schema(test_schema)

        # Create test entity
        client.entities.create(
            type="TestEntity",
            properties={"name": "Test Entity"}
        )

        # Execute hybrid query
        results = client.queries.hybrid(
            vector_query={
                "query_text": "test",
                "entity_types": ["TestEntity"],
                "limit": 10
            },
            merge_strategy="vector_only"
        )
        assert results is not None
        assert isinstance(results.results, list)

    def test_expand_types(self, client):
        """Test type expansion."""
        # This test requires a schema with type hierarchy
        schema = {
            "namespace": "test",
            "version": "1.0.0",
            "entity_types": [
                {
                    "id": "Animal",
                    "parent_type": None,
                    "properties": {}
                },
                {
                    "id": "Dog",
                    "parent_type": "Animal",
                    "properties": {}
                }
            ],
            "relation_types": []
        }
        client.ontology.upload_schema(schema)

        expanded = client.queries.expand_types(["Animal"])
        assert "Animal" in expanded


class TestEvents:
    """Test event ingestion API."""

    def test_ingest_single_event(self, client):
        """Test single event ingestion."""
        from datetime import datetime

        event = {
            "event_type": "test.event",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent_id": "test-agent",
            "metadata": {"test": "data"}
        }

        response = client.events.ingest(event)
        assert response.event_id is not None
        assert response.status == "accepted"

    def test_ingest_batch(self, client):
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

        response = client.events.ingest_batch(events)
        assert response.batch_id is not None
        assert response.total == 2
        assert response.successful >= 0
