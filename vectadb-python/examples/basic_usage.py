"""Basic VectaDB usage example."""

from vectadb import VectaDB

def main():
    # Initialize client
    client = VectaDB(base_url="http://localhost:8080")

    # Check server health
    health = client.health()
    print(f"Server status: {health.status}")
    print(f"Version: {health.version}")

    # Upload ontology schema
    schema = {
        "namespace": "example",
        "version": "1.0.0",
        "entity_types": [
            {
                "id": "Person",
                "parent_type": None,
                "properties": {
                    "name": {
                        "type": "string",
                        "required": True,
                        "indexed": True
                    },
                    "role": {
                        "type": "string",
                        "required": False,
                        "indexed": True
                    },
                    "email": {
                        "type": "string",
                        "required": False,
                        "indexed": False
                    }
                }
            },
            {
                "id": "Project",
                "parent_type": None,
                "properties": {
                    "name": {
                        "type": "string",
                        "required": True,
                        "indexed": True
                    },
                    "description": {
                        "type": "string",
                        "required": False,
                        "indexed": False
                    }
                }
            }
        ],
        "relation_types": [
            {
                "id": "works_on",
                "source_type": "Person",
                "target_type": "Project",
                "properties": {}
            }
        ]
    }

    print("\n📝 Uploading ontology schema...")
    result = client.ontology.upload_schema(schema)
    print(f"Schema uploaded: {result['message']}")

    # Create entities
    print("\n👤 Creating person entity...")
    person = client.entities.create(
        type="Person",
        properties={
            "name": "Alice Johnson",
            "role": "AI Researcher",
            "email": "alice@example.com"
        }
    )
    print(f"Created person: {person.id} - {person.properties['name']}")

    print("\n📊 Creating project entity...")
    project = client.entities.create(
        type="Project",
        properties={
            "name": "VectaDB SDK",
            "description": "Python SDK for VectaDB"
        }
    )
    print(f"Created project: {project.id} - {project.properties['name']}")

    # Create relation
    print("\n🔗 Creating relation...")
    relation = client.relations.create(
        type="works_on",
        from_entity_id=person.id,
        to_entity_id=project.id,
        properties={}
    )
    print(f"Created relation: {relation.id} ({relation.type})")

    # Query entities
    print("\n🔍 Performing hybrid query...")
    results = client.queries.hybrid(
        vector_query={
            "query_text": "AI research",
            "entity_types": ["Person"],
            "limit": 10
        },
        merge_strategy="vector_only"
    )
    print(f"Found {len(results.results)} results")
    for result in results.results:
        print(f"  - {result.entity.properties.get('name')} (score: {result.score:.3f})")

    # Validate entity
    print("\n✅ Validating entity...")
    validation = client.entities.validate(
        type="Person",
        properties={"name": "Bob Smith", "role": "Developer"}
    )
    print(f"Validation result: {'✓ Valid' if validation.valid else '✗ Invalid'}")
    if not validation.valid:
        for error in validation.errors:
            print(f"  - {error}")

    # Clean up
    print("\n🧹 Cleaning up...")
    client.relations.delete(relation.id)
    print(f"Deleted relation: {relation.id}")
    client.entities.delete(person.id)
    print(f"Deleted person: {person.id}")
    client.entities.delete(project.id)
    print(f"Deleted project: {project.id}")

    print("\n✨ Example completed successfully!")

if __name__ == "__main__":
    main()
