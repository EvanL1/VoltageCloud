import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Overview/Dashboard.vue'),
    meta: { title: '能源概览' }
  },
  {
    path: '/analysis',
    name: 'Analysis',
    component: () => import('@/views/Overview/Analysis.vue'),
    meta: { title: '数据分析' }
  },
  {
    path: '/station',
    name: 'StationList',
    component: () => import('@/views/Station/List.vue'),
    meta: { title: '子站列表' }
  },
  {
    path: '/station/:id',
    name: 'StationDetail',
    component: () => import('@/views/Station/Detail.vue'),
    meta: { title: '子站详情' }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || '能源管理系统'} - EMS`
  next()
})

export default router