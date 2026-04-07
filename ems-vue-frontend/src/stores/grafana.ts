import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import grafanaApi from '@/api/grafana'

export const useGrafanaStore = defineStore('grafana', () => {
  // 状态
  const authToken = ref<string>('')
  const orgId = ref<string>('1')
  const dashboards = ref<any[]>([])
  const isAuthenticated = ref(false)

  // 计算属性
  const grafanaUrl = computed(() => {
    return import.meta.env.VITE_GRAFANA_URL || 'http://localhost:3001'
  })

  // 方法
  const authenticate = async () => {
    try {
      // 从后端获取 Grafana 访问令牌
      const response = await grafanaApi.getAuthToken()
      authToken.value = response.data.token
      orgId.value = response.data.orgId
      isAuthenticated.value = true
      
      // 存储到 sessionStorage
      sessionStorage.setItem('grafana_token', authToken.value)
      sessionStorage.setItem('grafana_org', orgId.value)
      
      return true
    } catch (error) {
      ElMessage.error('Grafana 认证失败')
      console.error('Grafana auth error:', error)
      return false
    }
  }

  const ensureAuthenticated = async () => {
    // 检查是否已有令牌
    const storedToken = sessionStorage.getItem('grafana_token')
    const storedOrg = sessionStorage.getItem('grafana_org')
    
    if (storedToken && storedOrg) {
      authToken.value = storedToken
      orgId.value = storedOrg
      isAuthenticated.value = true
      return true
    }
    
    // 否则进行认证
    return await authenticate()
  }

  const loadDashboards = async () => {
    try {
      const response = await grafanaApi.getDashboards()
      dashboards.value = response.data
      return dashboards.value
    } catch (error) {
      ElMessage.error('加载 Grafana 仪表盘失败')
      console.error('Load dashboards error:', error)
      return []
    }
  }

  const createDashboard = async (config: any) => {
    try {
      const response = await grafanaApi.createDashboard(config)
      ElMessage.success('仪表盘创建成功')
      await loadDashboards() // 刷新列表
      return response.data
    } catch (error) {
      ElMessage.error('创建仪表盘失败')
      console.error('Create dashboard error:', error)
      throw error
    }
  }

  const exportDashboard = async (uid: string) => {
    try {
      const response = await grafanaApi.exportDashboard(uid)
      return response.data
    } catch (error) {
      ElMessage.error('导出仪表盘失败')
      console.error('Export dashboard error:', error)
      throw error
    }
  }

  const createSnapshot = async (dashboardUid: string) => {
    try {
      const response = await grafanaApi.createSnapshot(dashboardUid)
      ElMessage.success('快照创建成功')
      return response.data
    } catch (error) {
      ElMessage.error('创建快照失败')
      console.error('Create snapshot error:', error)
      throw error
    }
  }

  const logout = () => {
    authToken.value = ''
    orgId.value = '1'
    isAuthenticated.value = false
    dashboards.value = []
    
    sessionStorage.removeItem('grafana_token')
    sessionStorage.removeItem('grafana_org')
  }

  return {
    // 状态
    authToken,
    orgId,
    dashboards,
    isAuthenticated,
    grafanaUrl,
    
    // 方法
    authenticate,
    ensureAuthenticated,
    loadDashboards,
    createDashboard,
    exportDashboard,
    createSnapshot,
    logout
  }
})