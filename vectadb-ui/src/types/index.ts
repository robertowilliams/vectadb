// VectaDB TypeScript Types

export interface Entity {
  id: string
  type: string
  properties: Record<string, any>
  embedding?: number[]
  created_at?: string
  updated_at?: string
}

export interface Relation {
  id: string
  type: string
  from_entity_id: string
  to_entity_id: string
  properties: Record<string, any>
  created_at?: string
}

export interface PropertyDefinition {
  type: 'string' | 'number' | 'boolean' | 'array' | 'object'
  required: boolean
  indexed: boolean
  description?: string
}

export interface EntityType {
  id: string
  parent_type?: string
  properties: Record<string, PropertyDefinition>
  description?: string
}

export interface RelationType {
  id: string
  source_type: string
  target_type: string
  properties: Record<string, PropertyDefinition>
  description?: string
}

export interface OntologySchema {
  namespace: string
  version: string
  entity_types: EntityType[]
  relation_types: RelationType[]
}

export interface QueryResult {
  entity: Entity
  score: number
  source: 'vector' | 'graph' | 'hybrid'
}

export interface HybridQueryResponse {
  results: QueryResult[]
  total: number
  query_time_ms: number
}

export interface Event {
  event_type: string
  timestamp: string
  agent_id: string
  metadata?: Record<string, any>
  context?: Record<string, any>
}

export interface EventResponse {
  event_id: string
  status: 'accepted' | 'rejected'
  message?: string
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  version: string
  uptime_seconds?: number
}

export interface ValidationError {
  field: string
  message: string
}

export interface ValidationResponse {
  valid: boolean
  errors: ValidationError[]
}

// API Request/Response types
export interface CreateEntityRequest {
  type: string
  properties: Record<string, any>
}

export interface UpdateEntityRequest {
  properties: Record<string, any>
}

export interface CreateRelationRequest {
  type: string
  from_entity_id: string
  to_entity_id: string
  properties?: Record<string, any>
}

export interface VectorQuery {
  query_text: string
  entity_types?: string[]
  limit?: number
  score_threshold?: number
}

export interface GraphQuery {
  start_entity_id: string
  relation_types?: string[]
  max_depth?: number
  limit?: number
}

export interface HybridQueryRequest {
  vector_query?: VectorQuery
  graph_query?: GraphQuery
  merge_strategy: 'vector_only' | 'graph_only' | 'union' | 'intersection' | 'vector_prioritized' | 'graph_prioritized'
}

// Dashboard-specific types
export interface Stats {
  total_entities: number
  total_relations: number
  total_events: number
  entity_types_count: number
}

export interface RecentActivity {
  id: string
  type: 'entity_created' | 'entity_updated' | 'entity_deleted' | 'relation_created' | 'relation_deleted' | 'event_ingested'
  description: string
  timestamp: string
}

export interface GraphNode {
  id: string
  label: string
  type: string
  properties: Record<string, any>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  properties: Record<string, any>
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}
