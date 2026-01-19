<template>
  <div class="space-y-6">
    <!-- Stats Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div class="card">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-400">Total Entities</p>
            <p class="text-3xl font-bold">{{ store.stats.total_entities }}</p>
          </div>
          <div class="bg-primary-600 p-3 rounded-lg">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-400">Total Relations</p>
            <p class="text-3xl font-bold">{{ store.stats.total_relations }}</p>
          </div>
          <div class="bg-green-600 p-3 rounded-lg">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-400">Entity Types</p>
            <p class="text-3xl font-bold">{{ store.stats.entity_types_count }}</p>
          </div>
          <div class="bg-purple-600 p-3 rounded-lg">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
            </svg>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-400">Events</p>
            <p class="text-3xl font-bold">{{ store.stats.total_events }}</p>
          </div>
          <div class="bg-orange-600 p-3 rounded-lg">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent Activity -->
    <div class="card">
      <h2 class="text-xl font-semibold mb-4">Recent Activity</h2>
      <div v-if="store.recentActivities.length === 0" class="text-center py-8 text-slate-400">
        No recent activity
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="activity in store.recentActivities.slice(0, 10)"
          :key="activity.id"
          class="flex items-start space-x-3 p-3 bg-slate-700 rounded-lg"
        >
          <div class="flex-shrink-0 mt-1">
            <div :class="[
              'w-2 h-2 rounded-full',
              getActivityColor(activity.type)
            ]"></div>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium">{{ activity.description }}</p>
            <p class="text-xs text-slate-400">{{ formatTimestamp(activity.timestamp) }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="card">
      <h2 class="text-xl font-semibold mb-4">Quick Actions</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <router-link to="/entities" class="btn-primary text-center">
          Create Entity
        </router-link>
        <router-link to="/schema" class="btn-secondary text-center">
          Manage Schema
        </router-link>
        <router-link to="/query" class="btn-secondary text-center">
          Query Data
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useVectaDBStore } from '../stores/vectadb'

const store = useVectaDBStore()

function getActivityColor(type: string): string {
  const colors: Record<string, string> = {
    entity_created: 'bg-green-500',
    entity_updated: 'bg-blue-500',
    entity_deleted: 'bg-red-500',
    relation_created: 'bg-purple-500',
    relation_deleted: 'bg-orange-500',
    event_ingested: 'bg-yellow-500',
  }
  return colors[type] || 'bg-gray-500'
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (seconds < 60) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${days}d ago`
}
</script>
