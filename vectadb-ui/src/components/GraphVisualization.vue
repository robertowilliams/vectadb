<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import type { GraphData, GraphNode, GraphEdge } from '../types'

interface Props {
  data: GraphData
  width?: number
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  width: 800,
  height: 600
})

const svgRef = ref<SVGSVGElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
let simulation: d3.Simulation<GraphNode, undefined> | null = null

// Graph visualization settings
const settings = ref({
  chargeStrength: -300,
  linkDistance: 100,
  collisionRadius: 30
})

const emit = defineEmits<{
  nodeClick: [node: GraphNode]
  nodeDblClick: [node: GraphNode]
  edgeClick: [edge: GraphEdge]
}>()

// Node color mapping based on type
const getNodeColor = (type: string | undefined): string => {
  if (!type) return '#6b7280'
  const colorMap: Record<string, string> = {
    person: '#3b82f6',      // blue
    organization: '#10b981', // green
    location: '#f59e0b',    // orange
    event: '#ef4444',       // red
    document: '#8b5cf6',    // purple
  }
  return colorMap[type.toLowerCase()] ?? '#6b7280'
}

// Initialize or update the graph
const initGraph = () => {
  if (!svgRef.value || !containerRef.value) return
  if (!props.data.nodes.length) return

  // Clear previous content
  d3.select(svgRef.value).selectAll('*').remove()

  const container = containerRef.value
  const width = container.clientWidth
  const height = container.clientHeight

  // Create SVG
  const svg = d3.select(svgRef.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', [0, 0, width, height])

  // Add zoom behavior
  const g = svg.append('g')

  const zoom = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
    })

  svg.call(zoom)

  // Create arrow markers for directed edges
  svg.append('defs').selectAll('marker')
    .data(['end'])
    .join('marker')
    .attr('id', 'arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', '20')
    .attr('refY', '0')
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#64748b')

  // Create force simulation
  simulation = d3.forceSimulation(props.data.nodes)
    .force('link', d3.forceLink(props.data.edges)
      .id((d: any) => d.id)
      .distance(settings.value.linkDistance))
    .force('charge', d3.forceManyBody().strength(settings.value.chargeStrength))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(settings.value.collisionRadius)) as d3.Simulation<GraphNode, undefined>

  // Create links
  const link = g.append('g')
    .attr('class', 'links')
    .selectAll('line')
    .data(props.data.edges)
    .join('line')
    .attr('stroke', '#64748b')
    .attr('stroke-opacity', 0.6)
    .attr('stroke-width', 2)
    .attr('marker-end', 'url(#arrow)')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      emit('edgeClick', d)
    })

  // Create link labels
  const linkLabels = g.append('g')
    .attr('class', 'link-labels')
    .selectAll('text')
    .data(props.data.edges)
    .join('text')
    .attr('class', 'link-label')
    .attr('font-size', 10)
    .attr('fill', '#94a3b8')
    .text(d => d.type)

  // Create nodes
  const node = g.append('g')
    .attr('class', 'nodes')
    .selectAll('g')
    .data(props.data.nodes)
    .join('g')
    .style('cursor', 'pointer')
    .call(d3.drag<any, GraphNode>()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended) as any)

  // Add circles to nodes
  node.append('circle')
    .attr('r', 12)
    .attr('fill', d => getNodeColor(d.type))
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)

  // Add labels to nodes
  node.append('text')
    .attr('dx', 15)
    .attr('dy', 4)
    .attr('font-size', 12)
    .attr('fill', '#e2e8f0')
    .text(d => d.label || d.id)

  // Add click handlers
  node.on('click', (event, d) => {
    event.stopPropagation()
    emit('nodeClick', d)
  })
  .on('dblclick', (event, d) => {
    event.stopPropagation()
    emit('nodeDblClick', d)
  })

  // Update positions on simulation tick
  simulation.on('tick', () => {
    link
      .attr('x1', (d: any) => d.source.x)
      .attr('y1', (d: any) => d.source.y)
      .attr('x2', (d: any) => d.target.x)
      .attr('y2', (d: any) => d.target.y)

    linkLabels
      .attr('x', (d: any) => (d.source.x + d.target.x) / 2)
      .attr('y', (d: any) => (d.source.y + d.target.y) / 2)

    node.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
  })
}

// Drag functions
function dragstarted(event: any, d: any) {
  if (!event.active) simulation?.alphaTarget(0.3).restart()
  d.fx = d.x
  d.fy = d.y
}

function dragged(event: any, d: any) {
  d.fx = event.x
  d.fy = event.y
}

function dragended(event: any, d: any) {
  if (!event.active) simulation?.alphaTarget(0)
  d.fx = null
  d.fy = null
}

// Reset zoom
const resetZoom = () => {
  if (!svgRef.value) return
  d3.select(svgRef.value)
    .transition()
    .duration(750)
    .call(
      d3.zoom<SVGSVGElement, unknown>().transform as any,
      d3.zoomIdentity
    )
}

// Update simulation forces
const updateForces = () => {
  if (!simulation) return

  simulation
    .force('charge', d3.forceManyBody().strength(settings.value.chargeStrength))
    .force('link', d3.forceLink(props.data.edges)
      .id((d: any) => d.id)
      .distance(settings.value.linkDistance))
    .force('collision', d3.forceCollide().radius(settings.value.collisionRadius))
    .alpha(1)
    .restart()
}

// Handle window resize
const handleResize = () => {
  nextTick(() => {
    initGraph()
  })
}

// Lifecycle
onMounted(() => {
  initGraph()
  window.addEventListener('resize', handleResize)
})

// Watch for data changes
watch(() => props.data, () => {
  nextTick(() => {
    initGraph()
  })
}, { deep: true })

// Expose methods
defineExpose({
  resetZoom,
  updateForces,
  settings
})
</script>

<template>
  <div ref="containerRef" class="graph-container">
    <svg ref="svgRef" class="graph-svg"></svg>
  </div>
</template>

<style scoped>
.graph-container {
  width: 100%;
  height: 100%;
  min-height: 500px;
  background-color: #0f172a;
  border-radius: 0.5rem;
  overflow: hidden;
}

.graph-svg {
  display: block;
  width: 100%;
  height: 100%;
}

.link-label {
  pointer-events: none;
  user-select: none;
}
</style>
