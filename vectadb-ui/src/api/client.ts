import axios, { type AxiosInstance } from 'axios'
import type {
  Entity,
  Relation,
  OntologySchema,
  EntityType,
  CreateEntityRequest,
  UpdateEntityRequest,
  CreateRelationRequest,
  HybridQueryRequest,
  HybridQueryResponse,
  Event,
  EventResponse,
  HealthResponse,
  ValidationResponse,
} from '../types'

class VectaDBClient {
  private client: AxiosInstance

  constructor(baseURL: string = 'http://localhost:8080') {
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    })
  }

  // Health
  async health(): Promise<HealthResponse> {
    const { data } = await this.client.get('/health')
    return data
  }

  // Ontology
  async uploadSchema(schema: OntologySchema): Promise<{ message: string }> {
    const { data } = await this.client.post('/api/v1/ontology/schema', schema)
    return data
  }

  async getSchema(): Promise<OntologySchema> {
    const { data } = await this.client.get('/api/v1/ontology/schema')
    return data
  }

  async getEntityType(typeId: string): Promise<EntityType> {
    const { data } = await this.client.get(`/api/v1/ontology/types/${typeId}`)
    return data
  }

  async getSubtypes(typeId: string): Promise<string[]> {
    const { data } = await this.client.get(`/api/v1/ontology/types/${typeId}/subtypes`)
    return data.subtypes || []
  }

  // Entities
  async createEntity(request: CreateEntityRequest): Promise<Entity> {
    const { data } = await this.client.post('/api/v1/entities', request)
    return data
  }

  async getEntity(entityId: string): Promise<Entity> {
    const { data } = await this.client.get(`/api/v1/entities/${entityId}`)
    return data
  }

  async updateEntity(entityId: string, request: UpdateEntityRequest): Promise<Entity> {
    const { data } = await this.client.put(`/api/v1/entities/${entityId}`, request)
    return data
  }

  async deleteEntity(entityId: string): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/api/v1/entities/${entityId}`)
    return data
  }

  async validateEntity(type: string, properties: Record<string, any>): Promise<ValidationResponse> {
    const { data } = await this.client.post('/api/v1/validate/entity', { type, properties })
    return data
  }

  // Relations
  async createRelation(request: CreateRelationRequest): Promise<Relation> {
    const { data } = await this.client.post('/api/v1/relations', request)
    return data
  }

  async getRelation(relationId: string): Promise<Relation> {
    const { data } = await this.client.get(`/api/v1/relations/${relationId}`)
    return data
  }

  async deleteRelation(relationId: string): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/api/v1/relations/${relationId}`)
    return data
  }

  // Queries
  async hybridQuery(request: HybridQueryRequest): Promise<HybridQueryResponse> {
    const { data} = await this.client.post('/api/v1/query/hybrid', request)
    return data
  }

  async expandTypes(entityTypes: string[]): Promise<string[]> {
    const { data } = await this.client.post('/api/v1/query/expand', { entity_types: entityTypes })
    return data.expanded_types || []
  }

  // Events
  async ingestEvent(event: Event): Promise<EventResponse> {
    const { data } = await this.client.post('/api/v1/events', event)
    return data
  }

  async ingestEventBatch(events: Event[]): Promise<{ batch_id: string; total: number; successful: number; failed: number }> {
    const { data } = await this.client.post('/api/v1/events/batch', { events })
    return data
  }
}

export const vectadbClient = new VectaDBClient()
export default VectaDBClient
