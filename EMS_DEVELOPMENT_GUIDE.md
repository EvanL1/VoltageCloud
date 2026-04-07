# 能源管理系统开发指南

## 开发环境配置

### 端口分配
- **9000** - Vue 前端开发服务器
- **3000** - Node.js 后端 API
- **3001** - Grafana 数据可视化
- **9090** - Prometheus 监控
- **8086** - InfluxDB 时序数据库
- **6379** - Redis 缓存

## 快速开始

### 1. 仅前端开发（推荐）
```bash
# 启动 Vue 开发服务器
./ems-dev.sh

# 访问: http://localhost:9000
```

### 2. 前后端联调
```bash
# 同时启动前端和后端
./ems-dev.sh with-backend

# 前端: http://localhost:9000
# 后端: http://localhost:3000
```

### 3. 完整环境
```bash
# 启动所有服务（Docker Compose）
./ems-dev.sh full

# 包含: Vue + Backend + Grafana + Prometheus + InfluxDB + Redis
```

## 开发流程

### 前端开发

1. **启动开发服务器**
   ```bash
   cd ems-vue-frontend
   npm run dev
   ```
   自动在 9000 端口启动，支持热重载

2. **构建生产版本**
   ```bash
   npm run build
   ```

3. **代码检查**
   ```bash
   npm run lint
   npm run format
   ```

### 后端开发

1. **启动开发服务器**
   ```bash
   cd ems-backend
   npm run dev
   ```

2. **环境变量配置**
   创建 `.env` 文件：
   ```env
   PORT=3000
   AWS_REGION=us-east-1
   IOT_ENDPOINT=your-iot-endpoint
   ```

### Grafana 开发

1. **创建新仪表盘**
   - 访问 http://localhost:3001
   - 登录: admin/admin123
   - Create → Dashboard

2. **导出仪表盘**
   ```bash
   # 导出为 JSON
   curl -H "Authorization: Bearer $API_KEY" \
     http://localhost:3001/api/dashboards/uid/energy-overview
   ```

## 项目结构

```
ems-vue-frontend/
├── src/
│   ├── views/          # 页面组件（20个管理页面）
│   ├── components/     # 通用组件
│   │   └── Grafana/   # Grafana 集成组件
│   ├── api/           # API 接口
│   ├── stores/        # Pinia 状态管理
│   └── router/        # 路由配置
└── vite.config.ts     # Vite 配置（端口 9000）

ems-backend/
├── src/
│   ├── controllers/   # 控制器
│   ├── services/      # 业务逻辑
│   │   └── iot.service.ts  # IoT 数据集成
│   └── app.ts        # 应用入口
└── package.json

ems-grafana/
├── provisioning/      # 预配置
│   ├── dashboards/   # 仪表盘定义
│   └── datasources/  # 数据源配置
└── Dockerfile
```

## 开发技巧

### 1. Vue + Grafana 集成

```vue
<!-- 在 Vue 页面中嵌入 Grafana -->
<template>
  <GrafanaEmbed
    :dashboard-uid="'energy-overview'"
    :time-range="'now-6h&to=now'"
    height="600px"
  />
</template>
```

### 2. 实时数据订阅

```typescript
// 使用 WebSocket 订阅 IoT 数据
const { connect, subscribe } = useWebSocket()

onMounted(() => {
  connect()
  subscribe('energy:realtime', (data) => {
    console.log('实时能耗:', data)
  })
})
```

### 3. API 代理配置

Vite 已配置代理，开发时直接使用：
- `/api/*` → `http://localhost:3000`
- `/grafana/*` → `http://localhost:3001`

### 4. Mock 数据

开发时可启用 Mock 模式：
```env
VITE_ENABLE_MOCK=true
```

## 调试技巧

### 前端调试
1. Vue DevTools - 安装浏览器扩展
2. 网络请求 - 查看 Network 面板
3. Grafana 嵌入 - 检查 iframe 加载

### 后端调试
1. 使用 VSCode 调试配置
2. 查看日志: `docker logs ems-backend`
3. API 测试: Postman 或 Thunder Client

### Grafana 调试
1. 查看查询检查器
2. 检查数据源连接
3. 查看 Grafana 日志

## 常见问题

### Q: 端口 9000 被占用？
```bash
# 查找占用端口的进程
lsof -i :9000

# 或修改 vite.config.ts 中的端口
```

### Q: Grafana 无法嵌入？
检查 Grafana 配置：
```ini
[security]
allow_embedding = true
```

### Q: WebSocket 连接失败？
确保后端 WebSocket 服务正常：
```javascript
// 检查后端 Socket.io 配置
const io = new Server(server, {
  cors: {
    origin: "http://localhost:9000",
    credentials: true
  }
})
```

### Q: AWS IoT 数据获取失败？
1. 检查 AWS 凭证配置
2. 确认 IoT 终端节点正确
3. 验证 IAM 权限

## 部署准备

开发完成后，准备部署到 ECS：

1. **构建镜像**
   ```bash
   docker build -t ems-vue-frontend ./ems-vue-frontend
   ```

2. **本地测试**
   ```bash
   docker run -p 9000:80 ems-vue-frontend
   ```

3. **推送到 ECR**
   ```bash
   aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URL
   docker tag ems-vue-frontend:latest $ECR_URL/ems-frontend:latest
   docker push $ECR_URL/ems-frontend:latest
   ```