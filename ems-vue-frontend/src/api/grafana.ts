import axios from 'axios'

const grafanaApi = axios.create({
  baseURL: '/grafana',
  timeout: 10000
})

export interface GrafanaDashboard {
  uid: string
  title: string
  panels: any[]
}

export default {
  // 获取认证令牌
  getAuthToken: () => {
    // 模拟返回
    return Promise.resolve({
      data: {
        token: 'mock-grafana-token',
        orgId: '1'
      }
    })
  },

  // 获取仪表盘列表
  getDashboards: () => {
    return grafanaApi.get<GrafanaDashboard[]>('/api/search?type=dash-db')
  },

  // 创建仪表盘
  createDashboard: (dashboard: any) => {
    return grafanaApi.post('/api/dashboards/db', dashboard)
  },

  // 导出仪表盘
  exportDashboard: (uid: string) => {
    return grafanaApi.get(`/api/dashboards/uid/${uid}`)
  },

  // 创建快照
  createSnapshot: (dashboardUid: string) => {
    return grafanaApi.post('/api/snapshots', { dashboard: dashboardUid })
  }
}

export { grafanaApi }