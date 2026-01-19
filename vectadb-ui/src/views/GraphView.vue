<template>
  <div class="graph-view">
    <div class="card mb-4">
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-2xl font-semibold">Graph Explorer</h2>
        <div class="flex gap-2">
          <button
            class="btn btn-secondary"
            @click="loadGraphData"
            :disabled="loading"
          >
            {{ loading ? 'Loading...' : 'Refresh' }}
          </button>
          <button
            class="btn btn-secondary"
            @click="resetView"
          >
            Reset View
          </button>
          <button
            class="btn btn-secondary"
            @click="showControls = !showControls"
          >
            {{ showControls ? 'Hide' : 'Show' }} Controls
          </button>
        </div>
      </div>

      <!-- Controls Panel -->
      <div v-if="showControls" class="bg-slate-800 p-4 rounded-lg mb-4">
        <h3 class="text-lg font-semibold mb-3">Layout Settings</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label class="block text-sm text-slate-400 mb-1">
              Charge Strength: {{ graphSettings.chargeStrength }}
            </label>
            <input
              type="range"
              v-model.number="graphSettings.chargeStrength"
              min="-1000"
              max="-50"
              step="10"
              class="w-full"
              @change="updateForces"
            />
          </div>
          <div>
            <label class="block text-sm text-slate-400 mb-1">
              Link Distance: {{ graphSettings.linkDistance }}
            </label>
            <input
              type="range"
              v-model.number="graphSettings.linkDistance"
              min="20"
              max="300"
              step="10"
              class="w-full"
              @change="updateForces"
            />
          </div>
          <div>
            <label class="block text-sm text-slate-400 mb-1">
              Collision Radius: {{ graphSettings.collisionRadius }}
            </label>
            <input
              type="range"
              v-model.number="graphSettings.collisionRadius"
              min="10"
              max="100"
              step="5"
              class="w-full"
              @change="updateForces"
            />
          </div>
        </div>
      </div>

      <!-- Stats -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div class="bg-slate-800 p-3 rounded-lg">
          <p class="text-sm text-slate-400">Nodes</p>
          <p class="text-2xl font-semibold">{{ graphData.nodes.length }}</p>
        </div>
        <div class="bg-slate-800 p-3 rounded-lg">
          <p class="text-sm text-slate-400">Edges</p>
          <p class="text-2xl font-semibold">{{ graphData.edges.length }}</p>
        </div>
        <div class="bg-slate-800 p-3 rounded-lg">
          <p class="text-sm text-slate-400">Node Types</p>
          <p class="text-2xl font-semibold">{{ nodeTypes.size }}</p>
        </div>
        <div class="bg-slate-800 p-3 rounded-lg">
          <p class="text-sm text-slate-400">Edge Types</p>
          <p class="text-2xl font-semibold">{{ edgeTypes.size }}</p>
        </div>
      </div>
    </div>

    <!-- Graph Visualization -->
    <div class="card" style="min-height: 600px;">
      <GraphVisualization
        v-if="graphData.nodes.length > 0"
        ref="graphVizRef"
        :data="graphData"
        @node-click="handleNodeClick"
        @node-dbl-click="handleNodeDblClick"
        @edge-click="handleEdgeClick"
      />
      <div v-else-if="!loading" class="flex items-center justify-center h-96">
        <div class="text-center">
          <p class="text-slate-400 mb-4">No graph data available</p>
          <button class="btn btn-primary" @click="loadGraphData">
            Load Data
          </button>
        </div>
      </div>
      <div v-else class="flex items-center justify-center h-96">
        <p class="text-slate-400">Loading graph data...</p>
      </div>
    </div>

    <!-- Selected Node/Edge Details -->
    <div v-if="selectedNode || selectedEdge" class="card mt-4">
      <h3 class="text-xl font-semibold mb-4">
        {{ selectedNode ? 'Node' : 'Edge' }} Details
      </h3>

      <div v-if="selectedNode" class="space-y-2">
        <div class="grid grid-cols-2 gap-2">
          <div class="text-slate-400">ID:</div>
          <div class="font-mono">{{ selectedNode.id }}</div>

          <div class="text-slate-400">Type:</div>
          <div>
            <span class="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-sm">
              {{ selectedNode.type }}
            </span>
          </div>

          <div class="text-slate-400">Label:</div>
          <div>{{ selectedNode.label }}</div>
        </div>

        <div v-if="Object.keys(selectedNode.properties).length > 0">
          <div class="text-slate-400 mt-4 mb-2">Properties:</div>
          <div class="bg-slate-800 p-3 rounded-lg">
            <pre class="text-sm">{{ JSON.stringify(selectedNode.properties, null, 2) }}</pre>
          </div>
        </div>

        <button class="btn btn-secondary mt-4" @click="selectedNode = null">
          Close
        </button>
      </div>

      <div v-if="selectedEdge" class="space-y-2">
        <div class="grid grid-cols-2 gap-2">
          <div class="text-slate-400">ID:</div>
          <div class="font-mono">{{ selectedEdge.id }}</div>

          <div class="text-slate-400">Type:</div>
          <div>
            <span class="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-sm">
              {{ selectedEdge.type }}
            </span>
          </div>

          <div class="text-slate-400">Source:</div>
          <div class="font-mono">{{ selectedEdge.source }}</div>

          <div class="text-slate-400">Target:</div>
          <div class="font-mono">{{ selectedEdge.target }}</div>
        </div>

        <div v-if="Object.keys(selectedEdge.properties).length > 0">
          <div class="text-slate-400 mt-4 mb-2">Properties:</div>
          <div class="bg-slate-800 p-3 rounded-lg">
            <pre class="text-sm">{{ JSON.stringify(selectedEdge.properties, null, 2) }}</pre>
          </div>
        </div>

        <button class="btn btn-secondary mt-4" @click="selectedEdge = null">
          Close
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useVectaDBStore } from '../stores/vectadb'
import GraphVisualization from '../components/GraphVisualization.vue'
import type { GraphData, GraphNode, GraphEdge } from '../types'

const store = useVectaDBStore()
const graphVizRef = ref<InstanceType<typeof GraphVisualization> | null>(null)

// State
const loading = ref(false)
const showControls = ref(false)
const selectedNode = ref<GraphNode | null>(null)
const selectedEdge = ref<GraphEdge | null>(null)
const graphData = ref<GraphData>({
  nodes: [],
  edges: []
})

// Graph settings
const graphSettings = ref({
  chargeStrength: -300,
  linkDistance: 100,
  collisionRadius: 30
})

// Computed stats
const nodeTypes = computed(() => {
  return new Set(graphData.value.nodes.map(n => n.type))
})

const edgeTypes = computed(() => {
  return new Set(graphData.value.edges.map(e => e.type))
})

// Load graph data from entities and relations
const loadGraphData = async () => {
  loading.value = true
  try {
    // Fetch entities and relations from store
    await store.loadSchema()
    await Promise.all([
      store.fetchEntities(),
      store.fetchRelations()
    ])

    // Convert entities to nodes
    const nodes: GraphNode[] = store.entities.map(entity => ({
      id: entity.id,
      label: entity.properties.name || entity.properties.title || entity.id.substring(0, 8),
      type: entity.type,
      properties: entity.properties
    }))

    // Convert relations to edges
    const edges: GraphEdge[] = store.relations.map(relation => ({
      id: relation.id,
      source: relation.from_entity_id,
      target: relation.to_entity_id,
      type: relation.type,
      properties: relation.properties
    }))

    graphData.value = { nodes, edges }
  } catch (error) {
    console.error('Failed to load graph data:', error)
    store.error = error instanceof Error ? error.message : 'Failed to load graph data'
  } finally {
    loading.value = false
  }
}

// Event handlers
const handleNodeClick = (node: GraphNode) => {
  selectedNode.value = node
  selectedEdge.value = null
}

const handleNodeDblClick = (node: GraphNode) => {
  console.log('Double-clicked node:', node)
  // Could expand node, show neighbors, etc.
}

const handleEdgeClick = (edge: GraphEdge) => {
  selectedEdge.value = edge
  selectedNode.value = null
}

const resetView = () => {
  graphVizRef.value?.resetZoom()
}

const updateForces = () => {
  if (graphVizRef.value) {
    graphVizRef.value.settings.chargeStrength = graphSettings.value.chargeStrength
    graphVizRef.value.settings.linkDistance = graphSettings.value.linkDistance
    graphVizRef.value.settings.collisionRadius = graphSettings.value.collisionRadius
    graphVizRef.value.updateForces()
  }
}

// Initialize
onMounted(() => {
  loadGraphData()
})
</script>

<style scoped>
.graph-view {
  width: 100%;
}

input[type="range"] {
  accent-color: #3b82f6;
}
</style>
