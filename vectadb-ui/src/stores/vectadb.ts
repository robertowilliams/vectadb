import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { vectadbClient } from '../api/client'
import type {
  Entity,
  Relation,
  OntologySchema,
  HealthResponse,
  Stats,
  RecentActivity,
} from '../types'

export const useVectaDBStore = defineStore('vectadb', () => {
  // State
  const health = ref<HealthResponse | null>(null)
  const schema = ref<OntologySchema | null>(null)
  const entities = ref<Entity[]>([])
  const relations = ref<Relation[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const recentActivities = ref<RecentActivity[]>([])

  // Computed
  const isHealthy = computed(() => health.value?.status === 'healthy')

  const stats = computed<Stats>(() => ({
    total_entities: entities.value.length,
    total_relations: relations.value.length,
    total_events: 0, // TODO: Track events
    entity_types_count: schema.value?.entity_types.length || 0,
  }))

  const entityTypeOptions = computed(() =>
    schema.value?.entity_types.map(t => ({
      value: t.id,
      label: t.id,
    })) || []
  )

  // Actions
  async function checkHealth() {
    try {
      loading.value = true
      error.value = null
      health.value = await vectadbClient.health()
    } catch (e: any) {
      error.value = e.message || 'Failed to check health'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function loadSchema() {
    try {
      loading.value = true
      error.value = null
      schema.value = await vectadbClient.getSchema()
    } catch (e: any) {
      error.value = e.message || 'Failed to load schema'
      // Schema might not be uploaded yet
      if (e.response?.status !== 404) {
        throw e
      }
    } finally {
      loading.value = false
    }
  }

  async function uploadSchema(newSchema: OntologySchema) {
    try {
      loading.value = true
      error.value = null
      await vectadbClient.uploadSchema(newSchema)
      schema.value = newSchema
      addActivity({
        id: Date.now().toString(),
        type: 'entity_created',
        description: `Schema uploaded: ${newSchema.namespace}`,
        timestamp: new Date().toISOString(),
      })
    } catch (e: any) {
      error.value = e.message || 'Failed to upload schema'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function createEntity(type: string, properties: Record<string, any>) {
    try {
      loading.value = true
      error.value = null
      const entity = await vectadbClient.createEntity({ type, properties })
      entities.value.unshift(entity)
      addActivity({
        id: Date.now().toString(),
        type: 'entity_created',
        description: `Created ${type}: ${properties.name || entity.id}`,
        timestamp: new Date().toISOString(),
      })
      return entity
    } catch (e: any) {
      error.value = e.message || 'Failed to create entity'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateEntity(entityId: string, properties: Record<string, any>) {
    try {
      loading.value = true
      error.value = null
      const entity = await vectadbClient.updateEntity(entityId, { properties })
      const index = entities.value.findIndex(e => e.id === entityId)
      if (index !== -1) {
        entities.value[index] = entity
      }
      addActivity({
        id: Date.now().toString(),
        type: 'entity_updated',
        description: `Updated entity: ${entityId}`,
        timestamp: new Date().toISOString(),
      })
      return entity
    } catch (e: any) {
      error.value = e.message || 'Failed to update entity'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteEntity(entityId: string) {
    try {
      loading.value = true
      error.value = null
      await vectadbClient.deleteEntity(entityId)
      entities.value = entities.value.filter(e => e.id !== entityId)
      addActivity({
        id: Date.now().toString(),
        type: 'entity_deleted',
        description: `Deleted entity: ${entityId}`,
        timestamp: new Date().toISOString(),
      })
    } catch (e: any) {
      error.value = e.message || 'Failed to delete entity'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchEntities(limit?: number) {
    try {
      loading.value = true
      error.value = null
      entities.value = await vectadbClient.listEntities(limit)
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch entities'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function createRelation(type: string, fromEntityId: string, toEntityId: string, properties?: Record<string, any>) {
    try {
      loading.value = true
      error.value = null
      const relation = await vectadbClient.createRelation({
        type,
        from_entity_id: fromEntityId,
        to_entity_id: toEntityId,
        properties,
      })
      relations.value.unshift(relation)
      addActivity({
        id: Date.now().toString(),
        type: 'relation_created',
        description: `Created relation: ${type}`,
        timestamp: new Date().toISOString(),
      })
      return relation
    } catch (e: any) {
      error.value = e.message || 'Failed to create relation'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteRelation(relationId: string) {
    try {
      loading.value = true
      error.value = null
      await vectadbClient.deleteRelation(relationId)
      relations.value = relations.value.filter(r => r.id !== relationId)
      addActivity({
        id: Date.now().toString(),
        type: 'relation_deleted',
        description: `Deleted relation: ${relationId}`,
        timestamp: new Date().toISOString(),
      })
    } catch (e: any) {
      error.value = e.message || 'Failed to delete relation'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchRelations(limit?: number) {
    try {
      loading.value = true
      error.value = null
      relations.value = await vectadbClient.listRelations(limit)
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch relations'
      throw e
    } finally {
      loading.value = false
    }
  }

  function addActivity(activity: RecentActivity) {
    recentActivities.value.unshift(activity)
    // Keep only last 50 activities
    if (recentActivities.value.length > 50) {
      recentActivities.value = recentActivities.value.slice(0, 50)
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    // State
    health,
    schema,
    entities,
    relations,
    loading,
    error,
    recentActivities,
    // Computed
    isHealthy,
    stats,
    entityTypeOptions,
    // Actions
    checkHealth,
    loadSchema,
    uploadSchema,
    createEntity,
    updateEntity,
    deleteEntity,
    fetchEntities,
    createRelation,
    deleteRelation,
    fetchRelations,
    clearError,
  }
})
