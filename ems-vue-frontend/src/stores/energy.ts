import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

export const useEnergyStore = defineStore('energy', () => {
  // 能源统计数据
  const stats = reactive({
    totalConsumption: 0,
    carbonEmission: 0,
    cost: 0,
    onlineRate: 0
  })

  // 实时数据
  const realtimeData = ref<any[]>([])

  // 加载仪表盘数据
  const loadDashboardData = async () => {
    // 模拟数据加载
    stats.totalConsumption = 12845.67
    stats.carbonEmission = 8.45
    stats.cost = 9876.54
    stats.onlineRate = 98.5
  }

  // 更新实时数据
  const updateRealtimeData = (data: any) => {
    realtimeData.value.push(data)
    if (realtimeData.value.length > 100) {
      realtimeData.value.shift()
    }
  }

  return {
    stats,
    realtimeData,
    loadDashboardData,
    updateRealtimeData
  }
})