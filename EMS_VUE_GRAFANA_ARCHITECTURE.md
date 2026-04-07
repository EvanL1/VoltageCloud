# 能源管理系统 Vue + Grafana 架构方案

## 架构概述

```
┌─────────────────────────────────────────────────────────────┐
│                        用户访问层                              │
├─────────────────────────────────────────────────────────────┤
│              CloudFront CDN → ALB 负载均衡                     │
└────────────────────────────┬───────────────────────────────┘
                             │
┌────────────────────────────┴───────────────────────────────┐
│                      ECS Fargate 集群                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Vue App   │  │  Grafana    │  │   Backend   │       │
│  │  (Nginx)    │  │  Service    │  │   API       │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                 │                 │               │
│         └─────────────────┴─────────────────┘               │
└─────────────────────────────────────────────────────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        │                                         │
┌───────▼────────┐  ┌────────────┐  ┌───────────▼────────┐
│  Prometheus    │  │ InfluxDB   │  │  AWS IoT Core      │
│  (Metrics)     │  │ (Time DB)  │  │  (MQTT/WebSocket)  │
└────────────────┘  └────────────┘  └────────────────────┘
        │                  │                    │
┌───────▼────────────────────────────────────────────────┐
│     数据层 (DynamoDB, TimeStream, S3, RDS)              │
└────────────────────────────────────────────────────────┘
```

## 技术栈选择

### 前端技术栈
- **Vue 3** + TypeScript
- **Element Plus** - UI组件库
- **Vue Router 4** - 路由管理
- **Pinia** - 状态管理
- **Vite** - 构建工具
- **Axios** - HTTP请求
- **Socket.io-client** - 实时通信
- **ECharts** - 自定义图表（Grafana未覆盖的部分）

### Grafana 集成
- **Grafana 10.x** - 数据可视化
- **Grafana Embedding** - iframe嵌入
- **Grafana API** - 程序化管理
- **自定义插件** - 特定业务需求

### 数据源配置
- **Prometheus** - 实时指标
- **InfluxDB** - 时序数据
- **CloudWatch** - AWS资源监控
- **MySQL/PostgreSQL** - 业务数据

## Vue 项目结构

```
ems-vue-frontend/
├── public/
│   ├── index.html
│   └── favicon.ico
├── src/
│   ├── api/               # API 接口
│   │   ├── auth.ts
│   │   ├── energy.ts
│   │   ├── station.ts
│   │   ├── device.ts
│   │   └── grafana.ts
│   ├── assets/           # 静态资源
│   ├── components/       # 通用组件
│   │   ├── Layout/
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppSidebar.vue
│   │   │   └── AppFooter.vue
│   │   ├── Charts/       # 自定义图表
│   │   │   ├── EnergyFlow.vue
│   │   │   └── CostAnalysis.vue
│   │   └── Common/
│   │       ├── DataTable.vue
│   │       └── PermissionWrapper.vue
│   ├── views/           # 页面视图
│   │   ├── Overview/
│   │   │   ├── Dashboard.vue      # 嵌入Grafana仪表盘
│   │   │   ├── Analysis.vue
│   │   │   └── Alerts.vue
│   │   ├── Station/
│   │   │   ├── List.vue
│   │   │   ├── Detail.vue
│   │   │   ├── Monitor.vue       # 嵌入Grafana监控
│   │   │   ├── Control.vue
│   │   │   ├── Config.vue
│   │   │   └── Maintenance.vue
│   │   ├── Device/
│   │   │   ├── Assets.vue
│   │   │   ├── Status.vue        # 嵌入Grafana状态
│   │   │   ├── Control.vue
│   │   │   └── Firmware.vue
│   │   ├── Report/
│   │   │   ├── Energy.vue
│   │   │   └── Cost.vue
│   │   ├── System/
│   │   │   ├── Settings.vue
│   │   │   └── Backup.vue
│   │   └── Auth/
│   │       ├── Login.vue
│   │       ├── Users.vue
│   │       ├── Roles.vue
│   │       └── Audit.vue
│   ├── router/          # 路由配置
│   │   └── index.ts
│   ├── stores/          # Pinia状态管理
│   │   ├── auth.ts
│   │   ├── energy.ts
│   │   └── grafana.ts
│   ├── utils/           # 工具函数
│   │   ├── request.ts
│   │   ├── auth.ts
│   │   ├── grafana-embed.ts
│   │   └── websocket.ts
│   ├── types/           # TypeScript类型
│   ├── styles/          # 全局样式
│   ├── App.vue
│   └── main.ts
├── nginx/
│   └── default.conf
├── Dockerfile
├── vite.config.ts
├── tsconfig.json
└── package.json
```

## Grafana 嵌入方案

### 1. Grafana 配置
```yaml
# grafana.ini
[security]
allow_embedding = true
cookie_samesite = none
cookie_secure = true

[auth.anonymous]
enabled = true
org_role = Viewer

[auth.jwt]
enabled = true
header_name = X-JWT-Assertion
jwk_set_url = https://your-auth-server/.well-known/jwks.json
```

### 2. Vue 组件嵌入 Grafana
```vue
<!-- GrafanaPanel.vue -->
<template>
  <div class="grafana-panel">
    <iframe
      :src="panelUrl"
      :width="width"
      :height="height"
      frameborder="0"
      @load="onIframeLoad"
    ></iframe>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useGrafanaStore } from '@/stores/grafana'

interface Props {
  dashboardUid: string
  panelId: number
  timeRange?: string
  variables?: Record<string, string>
  width?: string
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  timeRange: 'now-1h',
  width: '100%',
  height: '400px'
})

const grafanaStore = useGrafanaStore()

const panelUrl = computed(() => {
  const baseUrl = import.meta.env.VITE_GRAFANA_URL
  const params = new URLSearchParams({
    orgId: '1',
    from: props.timeRange.split('&')[0],
    to: props.timeRange.split('&')[1] || 'now',
    'var-station': props.variables?.station || '',
    kiosk: 'tv',
    theme: 'light'
  })
  
  return `${baseUrl}/d-solo/${props.dashboardUid}?panelId=${props.panelId}&${params}`
})

const onIframeLoad = () => {
  // 注入认证token
  const iframe = document.querySelector('iframe')
  if (iframe?.contentWindow) {
    iframe.contentWindow.postMessage({
      type: 'auth',
      token: grafanaStore.authToken
    }, '*')
  }
}

onMounted(() => {
  grafanaStore.ensureAuthenticated()
})
</script>
```

### 3. Grafana API 集成
```typescript
// api/grafana.ts
import request from '@/utils/request'

export interface GrafanaDashboard {
  uid: string
  title: string
  panels: GrafanaPanel[]
}

export interface GrafanaPanel {
  id: number
  title: string
  type: string
}

export const grafanaApi = {
  // 获取仪表盘列表
  getDashboards: () => 
    request.get<GrafanaDashboard[]>('/api/grafana/dashboards'),
  
  // 创建仪表盘
  createDashboard: (dashboard: any) =>
    request.post('/api/grafana/dashboards', dashboard),
  
  // 创建数据源
  createDataSource: (config: any) =>
    request.post('/api/grafana/datasources', config),
  
  // 导出仪表盘
  exportDashboard: (uid: string) =>
    request.get(`/api/grafana/dashboards/${uid}/export`),
  
  // 创建快照
  createSnapshot: (dashboardUid: string) =>
    request.post(`/api/grafana/snapshots`, { dashboard: dashboardUid })
}
```

## 页面与 Grafana 映射

| 页面 | Grafana 集成方式 | 说明 |
|------|----------------|------|
| 能源概览仪表盘 | 完整嵌入仪表盘 | 使用Grafana预配置的能源总览dashboard |
| 数据分析中心 | 嵌入多个面板 | 趋势图、对比图等分析面板 |
| 子站实时监控 | 嵌入监控仪表盘 | 实时数据流、仪表、状态图 |
| 设备状态监测 | 嵌入状态面板 | 设备健康度、性能指标 |
| 能耗统计报表 | API导出 + 展示 | 使用Grafana API生成报表 |
| 告警监控中心 | 集成Alert面板 | Grafana告警 + 自定义告警 |

## Grafana 仪表盘预配置

```yaml
# provisioning/dashboards/energy-overview.json
{
  "dashboard": {
    "title": "能源管理总览",
    "panels": [
      {
        "id": 1,
        "title": "总能耗趋势",
        "type": "graph",
        "datasource": "Prometheus",
        "targets": [{
          "expr": "sum(energy_consumption_kwh)"
        }]
      },
      {
        "id": 2,
        "title": "能源类型分布",
        "type": "piechart",
        "datasource": "InfluxDB",
        "targets": [{
          "query": "SELECT sum(value) FROM energy GROUP BY type"
        }]
      },
      {
        "id": 3,
        "title": "实时功率",
        "type": "gauge",
        "datasource": "Prometheus",
        "targets": [{
          "expr": "sum(power_kw)"
        }]
      },
      {
        "id": 4,
        "title": "碳排放",
        "type": "stat",
        "datasource": "Prometheus",
        "targets": [{
          "expr": "sum(carbon_emission_kg)"
        }]
      }
    ]
  }
}
```

## Docker 部署配置

### Vue 应用 Dockerfile
```dockerfile
# ems-vue-frontend/Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Grafana Dockerfile
```dockerfile
# ems-grafana/Dockerfile
FROM grafana/grafana:10.2.0

USER root
RUN apk add --no-cache git

USER grafana

# 复制预配置
COPY provisioning /etc/grafana/provisioning
COPY dashboards /var/lib/grafana/dashboards

# 安装插件
RUN grafana-cli plugins install grafana-piechart-panel && \
    grafana-cli plugins install grafana-worldmap-panel && \
    grafana-cli plugins install alexanderzobnin-zabbix-app

ENV GF_SECURITY_ALLOW_EMBEDDING=true
ENV GF_AUTH_ANONYMOUS_ENABLED=true
ENV GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
```

### Docker Compose
```yaml
version: '3.8'

services:
  vue-app:
    build: ./ems-vue-frontend
    ports:
      - "80:80"
    environment:
      - VITE_API_URL=http://backend:3000
      - VITE_GRAFANA_URL=http://grafana:3000
    depends_on:
      - backend
      - grafana

  grafana:
    build: ./ems-grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_INSTALL_PLUGINS=redis-datasource
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus
      - influxdb

  backend:
    build: ./ems-backend
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - AWS_REGION=us-east-1
    
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    
  influxdb:
    image: influxdb:2.7
    ports:
      - "8086:8086"
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=password123
      - DOCKER_INFLUXDB_INIT_ORG=ems
      - DOCKER_INFLUXDB_INIT_BUCKET=energy
    volumes:
      - influxdb-data:/var/lib/influxdb2

volumes:
  grafana-data:
  prometheus-data:
  influxdb-data:
```

## package.json (Vue)

```json
{
  "name": "ems-vue-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --fix",
    "format": "prettier --write src/"
  },
  "dependencies": {
    "@element-plus/icons-vue": "^2.3.1",
    "axios": "^1.6.5",
    "dayjs": "^1.11.10",
    "echarts": "^5.4.3",
    "element-plus": "^2.4.4",
    "pinia": "^2.1.7",
    "socket.io-client": "^4.7.4",
    "vue": "^3.4.5",
    "vue-echarts": "^6.6.8",
    "vue-router": "^4.2.5"
  },
  "devDependencies": {
    "@rushstack/eslint-patch": "^1.6.1",
    "@tsconfig/node20": "^20.1.2",
    "@types/node": "^20.10.7",
    "@vitejs/plugin-vue": "^5.0.2",
    "@vue/eslint-config-prettier": "^9.0.0",
    "@vue/eslint-config-typescript": "^12.0.0",
    "@vue/tsconfig": "^0.5.1",
    "eslint": "^8.56.0",
    "eslint-plugin-vue": "^9.20.0",
    "prettier": "^3.1.1",
    "sass": "^1.69.7",
    "typescript": "~5.3.3",
    "unplugin-auto-import": "^0.17.3",
    "unplugin-vue-components": "^0.26.0",
    "vite": "^5.0.11",
    "vue-tsc": "^1.8.27"
  }
}
```

## 集成优势

1. **专业的数据可视化**
   - Grafana 提供丰富的图表类型
   - 支持多数据源查询
   - 内置告警和通知

2. **降低开发成本**
   - 复用 Grafana 成熟的可视化能力
   - 减少自定义图表开发工作
   - 快速创建监控面板

3. **灵活的架构**
   - Vue 负责业务逻辑和交互
   - Grafana 专注数据展示
   - 两者通过 iframe 和 API 集成

4. **统一的用户体验**
   - 通过 Vue 包装统一界面风格
   - JWT 单点登录
   - 权限统一管理