<template>
  <div class="min-h-screen bg-slate-900 text-slate-100">
    <!-- Sidebar -->
    <aside class="fixed top-0 left-0 z-40 w-64 h-screen bg-slate-800 border-r border-slate-700">
      <div class="h-full px-3 py-4 overflow-y-auto">
        <!-- Logo -->
        <div class="flex items-center mb-8 px-2">
          <div class="text-2xl font-bold text-primary-400">VectaDB</div>
        </div>

        <!-- Navigation -->
        <ul class="space-y-2 font-medium">
          <li>
            <router-link
              to="/"
              class="flex items-center p-2 rounded-lg hover:bg-slate-700 transition-colors"
              active-class="bg-primary-600 hover:bg-primary-700"
            >
              <span class="ml-3">Dashboard</span>
            </router-link>
          </li>
          <li>
            <router-link
              to="/entities"
              class="flex items-center p-2 rounded-lg hover:bg-slate-700 transition-colors"
              active-class="bg-primary-600 hover:bg-primary-700"
            >
              <span class="ml-3">Entities</span>
            </router-link>
          </li>
          <li>
            <router-link
              to="/relations"
              class="flex items-center p-2 rounded-lg hover:bg-slate-700 transition-colors"
              active-class="bg-primary-600 hover:bg-primary-700"
            >
              <span class="ml-3">Relations</span>
            </router-link>
          </li>
          <li>
            <router-link
              to="/graph"
              class="flex items-center p-2 rounded-lg hover:bg-slate-700 transition-colors"
              active-class="bg-primary-600 hover:bg-primary-700"
            >
              <span class="ml-3">Graph</span>
            </router-link>
          </li>
          <li>
            <router-link
              to="/query"
              class="flex items-center p-2 rounded-lg hover:bg-slate-700 transition-colors"
              active-class="bg-primary-600 hover:bg-primary-700"
            >
              <span class="ml-3">Query</span>
            </router-link>
          </li>
          <li>
            <router-link
              to="/schema"
              class="flex items-center p-2 rounded-lg hover:bg-slate-700 transition-colors"
              active-class="bg-primary-600 hover:bg-primary-700"
            >
              <span class="ml-3">Schema</span>
            </router-link>
          </li>
          <li>
            <router-link
              to="/events"
              class="flex items-center p-2 rounded-lg hover:bg-slate-700 transition-colors"
              active-class="bg-primary-600 hover:bg-primary-700"
            >
              <span class="ml-3">Events</span>
            </router-link>
          </li>
        </ul>
      </div>
    </aside>

    <!-- Main Content -->
    <div class="ml-64">
      <header class="bg-slate-800 border-b border-slate-700 px-6 py-4">
        <h1 class="text-2xl font-semibold">{{ currentRoute }}</h1>
      </header>

      <main class="p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useVectaDBStore } from './stores/vectadb'

const route = useRoute()
const store = useVectaDBStore()

const currentRoute = computed(() => route.meta.title || 'VectaDB Dashboard')

onMounted(async () => {
  await store.checkHealth()
  await store.loadSchema()
})
</script>
