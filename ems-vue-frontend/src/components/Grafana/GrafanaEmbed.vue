<template>
  <div ref="containerRef" class="grafana-embed-container">
    <div v-if="loading" class="loading-overlay">
      <el-icon class="is-loading" :size="32">
        <Loading />
      </el-icon>
      <p>加载中...</p>
    </div>
    
    <iframe
      v-show="!loading"
      ref="iframeRef"
      :src="embedUrl"
      :width="width"
      :height="height"
      frameborder="0"
      scrolling="no"
      @load="onIframeLoad"
      @error="onIframeError"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { useGrafanaStore } from '@/stores/grafana'
import { ElMessage } from 'element-plus'

interface Props {
  dashboardUid: string
  panelId?: number
  timeRange?: string
  variables?: Record<string, string>
  width?: string
  height?: string
  theme?: 'light' | 'dark'
  refresh?: string
}

const props = withDefaults(defineProps<Props>(), {
  timeRange: 'now-1h&to=now',
  width: '100%',
  height: '600px',
  theme: 'light',
  refresh: '10s'
})

const emit = defineEmits<{
  loaded: []
  error: [error: Error]
}>()

// 响应式数据
const containerRef = ref<HTMLDivElement>()
const iframeRef = ref<HTMLIFrameElement>()
const loading = ref(true)

// Store
const grafanaStore = useGrafanaStore()

// 计算属性
const embedUrl = computed(() => {
  const baseUrl = import.meta.env.VITE_GRAFANA_URL || 'http://localhost:3001'
  const orgId = grafanaStore.orgId || '1'
  
  // 构建查询参数
  const params = new URLSearchParams({
    orgId,
    from: props.timeRange.split('&to=')[0],
    to: props.timeRange.split('&to=')[1] || 'now',
    theme: props.theme,
    refresh: props.refresh,
    kiosk: 'tv' // 隐藏Grafana UI
  })
  
  // 添加变量参数
  if (props.variables) {
    Object.entries(props.variables).forEach(([key, value]) => {
      params.append(`var-${key}`, value)
    })
  }
  
  // 构建URL
  if (props.panelId) {
    // 单个面板
    return `${baseUrl}/d-solo/${props.dashboardUid}?panelId=${props.panelId}&${params}`
  } else {
    // 完整仪表盘
    return `${baseUrl}/d/${props.dashboardUid}?${params}`
  }
})

// 方法
const onIframeLoad = () => {
  loading.value = false
  
  // 注入认证信息
  if (iframeRef.value?.contentWindow) {
    // 发送认证token
    iframeRef.value.contentWindow.postMessage({
      type: 'grafana-auth',
      token: grafanaStore.authToken,
      orgId: grafanaStore.orgId
    }, '*')
  }
  
  emit('loaded')
}

const onIframeError = (event: Event) => {
  loading.value = false
  const error = new Error('Grafana加载失败')
  ElMessage.error('Grafana仪表盘加载失败，请检查配置')
  emit('error', error)
}

// 监听来自Grafana的消息
const handleMessage = (event: MessageEvent) => {
  if (event.origin !== import.meta.env.VITE_GRAFANA_URL) {
    return
  }
  
  if (event.data.type === 'grafana-ready') {
    // Grafana已准备就绪
    console.log('Grafana is ready')
  }
}

// 监听属性变化，刷新iframe
watch(() => [props.timeRange, props.variables], () => {
  if (iframeRef.value) {
    loading.value = true
    iframeRef.value.src = embedUrl.value
  }
}, { deep: true })

// 生命周期
onMounted(() => {
  // 确保已认证
  grafanaStore.ensureAuthenticated()
  
  // 监听消息
  window.addEventListener('message', handleMessage)
})

onUnmounted(() => {
  window.removeEventListener('message', handleMessage)
})

// 暴露方法
defineExpose({
  refresh: () => {
    if (iframeRef.value) {
      loading.value = true
      iframeRef.value.src = embedUrl.value
    }
  }
})
</script>

<style lang="scss" scoped>
.grafana-embed-container {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #f5f5f5;
  
  iframe {
    border: none;
    display: block;
  }
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: rgba(255, 255, 255, 0.9);
  z-index: 10;
  
  p {
    margin-top: 10px;
    color: #909399;
    font-size: 14px;
  }
}

.is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>