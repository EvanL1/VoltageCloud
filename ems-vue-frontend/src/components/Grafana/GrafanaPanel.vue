<template>
  <div class="grafana-panel">
    <GrafanaEmbed
      :dashboard-uid="dashboardUid"
      :panel-id="panelId"
      :time-range="timeRange"
      :variables="variables"
      :width="width"
      :height="height"
      :theme="theme"
      @loaded="$emit('loaded')"
      @error="$emit('error', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import GrafanaEmbed from './GrafanaEmbed.vue'

interface Props {
  dashboardUid: string
  panelId: number
  timeRange?: string
  variables?: Record<string, string>
  width?: string
  height?: string
  theme?: 'light' | 'dark'
}

withDefaults(defineProps<Props>(), {
  timeRange: 'now-1h&to=now',
  width: '100%',
  height: '400px',
  theme: 'light'
})

defineEmits<{
  loaded: []
  error: [error: Error]
}>()
</script>

<style scoped>
.grafana-panel {
  width: 100%;
  height: 100%;
}
</style>