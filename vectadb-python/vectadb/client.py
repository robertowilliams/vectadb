"""VectaDB synchronous client."""

from typing import Any, Dict, List, Optional
import httpx

from vectadb.exceptions import (
    VectaDBError,
    ConnectionError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    ServerError,
    RateLimitError,
)
from vectadb.models import (
    Entity,
    Relation,
    OntologySchema,
    EntityType,
    ValidationResponse,
    HybridQueryRequest,
    HybridQueryResponse,
    Event,
    EventBatch,
    EventResponse,
    EventBatchResponse,
    HealthResponse,
)


class BaseAPI:
    """Base API class with common functionality."""

    def __init__(self, client: httpx.Client, base_url: str) -> None:
        """Initialize base API.

        Args:
            client: HTTP client
            base_url: Base URL for the API
        """
        self.client = client
        self.base_url = base_url

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle HTTP response and raise appropriate exceptions.

        Args:
            response: HTTP response

        Returns:
            Response JSON data

        Raises:
            Various VectaDB exceptions based on status code
        """
        if response.status_code == 200 or response.status_code == 201:
            return response.json()

        # Handle errors
        try:
            error_data = response.json()
            message = error_data.get("error", {}).get("message", response.text)
            details = error_data.get("error", {}).get("details")
        except Exception:
            message = response.text
            details = None

        if response.status_code == 401 or response.status_code == 403:
            raise AuthenticationError(message, response.status_code, details)
        elif response.status_code == 404:
            raise NotFoundError(message, response.status_code, details)
        elif response.status_code == 422:
            raise ValidationError(message, response.status_code, details)
        elif response.status_code == 429:
            raise RateLimitError(message, response.status_code, details)
        elif response.status_code >= 500:
            raise ServerError(message, response.status_code, details)
        else:
            raise VectaDBError(message, response.status_code, details)


class OntologyAPI(BaseAPI):
    """Ontology management API."""

    def upload_schema(self, schema: Dict[str, Any] | OntologySchema) -> Dict[str, Any]:
        """Upload an ontology schema.

        Args:
            schema: Ontology schema (dict or OntologySchema model)

        Returns:
            Response dictionary

        Raises:
            ValidationError: If schema validation fails
        """
        if isinstance(schema, OntologySchema):
            schema = schema.model_dump(exclude_none=True)

        response = self.client.post(f"{self.base_url}/api/v1/ontology/schema", json=schema)
        return self._handle_response(response)

    def get_schema(self) -> OntologySchema:
        """Get the current ontology schema.

        Returns:
            Ontology schema

        Raises:
            NotFoundError: If no schema is loaded
        """
        response = self.client.get(f"{self.base_url}/api/v1/ontology/schema")
        data = self._handle_response(response)
        return OntologySchema(**data)

    def get_entity_type(self, type_id: str) -> EntityType:
        """Get details about an entity type.

        Args:
            type_id: Entity type identifier

        Returns:
            Entity type definition

        Raises:
            NotFoundError: If type not found
        """
        response = self.client.get(f"{self.base_url}/api/v1/ontology/types/{type_id}")
        data = self._handle_response(response)
        return EntityType(**data)

    def get_subtypes(self, type_id: str) -> List[str]:
        """Get all subtypes of an entity type.

        Args:
            type_id: Entity type identifier

        Returns:
            List of subtype IDs

        Raises:
            NotFoundError: If type not found
        """
        response = self.client.get(f"{self.base_url}/api/v1/ontology/types/{type_id}/subtypes")
        data = self._handle_response(response)
        return data.get("subtypes", [])


class EntityAPI(BaseAPI):
    """Entity management API."""

    def create(self, type: str, properties: Dict[str, Any]) -> Entity:
        """Create a new entity.

        Args:
            type: Entity type
            properties: Entity properties

        Returns:
            Created entity

        Raises:
            ValidationError: If validation fails
        """
        payload = {"type": type, "properties": properties}
        response = self.client.post(f"{self.base_url}/api/v1/entities", json=payload)
        data = self._handle_response(response)
        return Entity(**data)

    def get(self, entity_id: str) -> Entity:
        """Get an entity by ID.

        Args:
            entity_id: Entity identifier

        Returns:
            Entity

        Raises:
            NotFoundError: If entity not found
        """
        response = self.client.get(f"{self.base_url}/api/v1/entities/{entity_id}")
        data = self._handle_response(response)
        return Entity(**data)

    def update(self, entity_id: str, properties: Dict[str, Any]) -> Entity:
        """Update an entity.

        Args:
            entity_id: Entity identifier
            properties: Updated properties

        Returns:
            Updated entity

        Raises:
            NotFoundError: If entity not found
            ValidationError: If validation fails
        """
        payload = {"properties": properties}
        response = self.client.put(f"{self.base_url}/api/v1/entities/{entity_id}", json=payload)
        data = self._handle_response(response)
        return Entity(**data)

    def delete(self, entity_id: str) -> Dict[str, Any]:
        """Delete an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            Deletion confirmation

        Raises:
            NotFoundError: If entity not found
        """
        response = self.client.delete(f"{self.base_url}/api/v1/entities/{entity_id}")
        return self._handle_response(response)

    def validate(self, type: str, properties: Dict[str, Any]) -> ValidationResponse:
        """Validate an entity against the schema.

        Args:
            type: Entity type
            properties: Entity properties

        Returns:
            Validation result
        """
        payload = {"type": type, "properties": properties}
        response = self.client.post(f"{self.base_url}/api/v1/validate/entity", json=payload)
        data = self._handle_response(response)
        return ValidationResponse(**data)


class RelationAPI(BaseAPI):
    """Relation management API."""

    def create(
        self, type: str, from_entity_id: str, to_entity_id: str, properties: Optional[Dict[str, Any]] = None
    ) -> Relation:
        """Create a new relation.

        Args:
            type: Relation type
            from_entity_id: Source entity ID
            to_entity_id: Target entity ID
            properties: Optional relation properties

        Returns:
            Created relation

        Raises:
            ValidationError: If validation fails
        """
        payload = {
            "type": type,
            "from_entity_id": from_entity_id,
            "to_entity_id": to_entity_id,
            "properties": properties or {},
        }
        response = self.client.post(f"{self.base_url}/api/v1/relations", json=payload)
        data = self._handle_response(response)
        return Relation(**data)

    def get(self, relation_id: str) -> Relation:
        """Get a relation by ID.

        Args:
            relation_id: Relation identifier

        Returns:
            Relation

        Raises:
            NotFoundError: If relation not found
        """
        response = self.client.get(f"{self.base_url}/api/v1/relations/{relation_id}")
        data = self._handle_response(response)
        return Relation(**data)

    def delete(self, relation_id: str) -> Dict[str, Any]:
        """Delete a relation.

        Args:
            relation_id: Relation identifier

        Returns:
            Deletion confirmation

        Raises:
            NotFoundError: If relation not found
        """
        response = self.client.delete(f"{self.base_url}/api/v1/relations/{relation_id}")
        return self._handle_response(response)


class QueryAPI(BaseAPI):
    """Query API for hybrid searches."""

    def hybrid(
        self,
        vector_query: Optional[Dict[str, Any]] = None,
        graph_query: Optional[Dict[str, Any]] = None,
        merge_strategy: str = "union",
    ) -> HybridQueryResponse:
        """Execute a hybrid query.

        Args:
            vector_query: Vector similarity query parameters
            graph_query: Graph traversal query parameters
            merge_strategy: Strategy for merging results

        Returns:
            Query results
        """
        request = HybridQueryRequest(
            vector_query=vector_query,
            graph_query=graph_query,
            merge_strategy=merge_strategy,
        )
        payload = request.model_dump(exclude_none=True)
        response = self.client.post(f"{self.base_url}/api/v1/query/hybrid", json=payload)
        data = self._handle_response(response)
        return HybridQueryResponse(**data)

    def expand_types(self, entity_types: List[str]) -> List[str]:
        """Expand entity types using ontology hierarchy.

        Args:
            entity_types: Entity types to expand

        Returns:
            Expanded list of entity types
        """
        payload = {"entity_types": entity_types}
        response = self.client.post(f"{self.base_url}/api/v1/query/expand", json=payload)
        data = self._handle_response(response)
        return data.get("expanded_types", [])


class EventAPI(BaseAPI):
    """Event ingestion API for observability."""

    def ingest(self, event: Event | Dict[str, Any]) -> EventResponse:
        """Ingest a single event.

        Args:
            event: Event to ingest

        Returns:
            Event response
        """
        if isinstance(event, Event):
            payload = event.model_dump(exclude_none=True)
        else:
            payload = event

        response = self.client.post(f"{self.base_url}/api/v1/events", json=payload)
        data = self._handle_response(response)
        return EventResponse(**data)

    def ingest_batch(self, events: List[Event] | List[Dict[str, Any]]) -> EventBatchResponse:
        """Ingest multiple events in batch.

        Args:
            events: List of events to ingest

        Returns:
            Batch response
        """
        if events and isinstance(events[0], Event):
            event_dicts = [e.model_dump(exclude_none=True) for e in events]
        else:
            event_dicts = events

        payload = {"events": event_dicts}
        response = self.client.post(f"{self.base_url}/api/v1/events/batch", json=payload)
        data = self._handle_response(response)
        return EventBatchResponse(**data)


class VectaDB:
    """VectaDB synchronous client.

    Example:
        >>> client = VectaDB(base_url="http://localhost:8080")
        >>> schema = {...}
        >>> client.ontology.upload_schema(schema)
        >>> entity = client.entities.create(type="Person", properties={"name": "Alice"})
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize VectaDB client.

        Args:
            base_url: Base URL of the VectaDB server
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
        )
        self.base_url = base_url

        # Initialize API modules
        self.ontology = OntologyAPI(self._client, base_url)
        self.entities = EntityAPI(self._client, base_url)
        self.relations = RelationAPI(self._client, base_url)
        self.queries = QueryAPI(self._client, base_url)
        self.events = EventAPI(self._client, base_url)

    def health(self) -> HealthResponse:
        """Check server health.

        Returns:
            Health status
        """
        try:
            response = self._client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                return HealthResponse(**data)
            else:
                raise ConnectionError(f"Health check failed: {response.status_code}")
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to VectaDB: {e}")

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "VectaDB":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
