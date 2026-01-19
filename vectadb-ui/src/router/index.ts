import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue'),
      meta: { title: 'Dashboard' },
    },
    {
      path: '/entities',
      name: 'entities',
      component: () => import('../views/EntitiesView.vue'),
      meta: { title: 'Entities' },
    },
    {
      path: '/relations',
      name: 'relations',
      component: () => import('../views/RelationsView.vue'),
      meta: { title: 'Relations' },
    },
    {
      path: '/graph',
      name: 'graph',
      component: () => import('../views/GraphView.vue'),
      meta: { title: 'Graph Explorer' },
    },
    {
      path: '/query',
      name: 'query',
      component: () => import('../views/QueryView.vue'),
      meta: { title: 'Query Builder' },
    },
    {
      path: '/schema',
      name: 'schema',
      component: () => import('../views/SchemaView.vue'),
      meta: { title: 'Schema Management' },
    },
    {
      path: '/events',
      name: 'events',
      component: () => import('../views/EventsView.vue'),
      meta: { title: 'Events & Monitoring' },
    },
  ],
})

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'VectaDB'} | VectaDB Dashboard`
  next()
})

export default router
