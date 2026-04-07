# EMS Backend API

能源管理系统后端API，与AWS IoT集成，提供设备管理、遥测数据访问、能源分析等功能。

## 功能特性

- 🔌 **AWS IoT集成**: 设备管理、影子状态、MQTT消息
- 📊 **遥测数据**: 从S3数据湖读取历史数据
- ⚡ **能源分析**: 消耗统计、效率分析、成本计算、预测
- 🔄 **实时推送**: WebSocket实时数据流
- 🔐 **认证授权**: JWT认证、角色权限控制
- 💾 **缓存优化**: Redis缓存热点数据
- 📝 **完整API**: RESTful API设计

## 技术栈

- **Node.js** + **TypeScript**
- **Express.js** - Web框架
- **Socket.io** - WebSocket实时通信
- **AWS SDK v3** - AWS服务集成
- **Redis** - 缓存
- **JWT** - 认证
- **Joi** - 数据验证
- **Winston** - 日志

## 快速开始

### 1. 安装依赖

```bash
cd ems-backend
npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入AWS凭证等配置
```

### 3. 启动开发服务器

```bash
npm run dev
```

服务器将在 http://localhost:3000 启动

## API端点

### 认证 `/api/v1/auth`
- `POST /login` - 用户登录
- `POST /refresh` - 刷新令牌
- `GET /me` - 获取当前用户
- `POST /logout` - 登出
- `POST /change-password` - 修改密码

### 设备管理 `/api/v1/devices`
- `GET /` - 获取设备列表
- `GET /stats` - 设备统计
- `GET /:deviceId` - 获取设备详情
- `GET /:deviceId/shadow` - 获取设备影子
- `POST /` - 创建设备
- `PUT /:deviceId` - 更新设备
- `PUT /:deviceId/shadow` - 更新设备影子
- `POST /:deviceId/command` - 发送命令
- `DELETE /:deviceId` - 删除设备

### 遥测数据 `/api/v1/telemetry`
- `GET /:deviceId` - 获取历史数据
- `GET /:deviceId/latest` - 获取最新数据
- `GET /:deviceId/aggregate` - 获取聚合数据
- `GET /:deviceId/export` - 导出数据
- `GET /:deviceId/quality` - 数据质量报告
- `POST /batch` - 批量查询

### 能源管理 `/api/v1/energy`
- `GET /consumption` - 能源消耗
- `GET /efficiency` - 能效分析
- `GET /cost` - 成本分析
- `GET /forecast` - 能源预测
- `GET /devices/:deviceId/optimization` - 优化建议
- `GET /dashboard` - 能源仪表板

### WebSocket事件

连接地址: `ws://localhost:3000/ws`

#### 订阅事件
- `subscribe` - 订阅主题
- `subscribe:device` - 订阅设备
- `unsubscribe` - 取消订阅

#### 接收事件
- `telemetry` - 遥测数据更新
- `device:update` - 设备状态更新
- `energy:alert` - 能源告警

## 认证

### 获取Token

```bash
curl -X POST http://localhost:3000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin123"
  }'
```

### 使用Token

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:3000/api/v1/devices
```

## 测试账号

| 邮箱 | 密码 | 角色 | 权限 |
|-----|------|-----|------|
| admin@example.com | admin123 | ADMIN | 所有权限 |
| operator@example.com | admin123 | OPERATOR | 读写权限 |
| viewer@example.com | admin123 | VIEWER | 只读权限 |

## WebSocket连接示例

```javascript
import { io } from 'socket.io-client';

const socket = io('http://localhost:3000', {
  path: '/ws',
  auth: {
    token: 'YOUR_JWT_TOKEN'
  }
});

// 订阅设备
socket.emit('subscribe:device', { deviceId: 'device-001' });

// 接收实时数据
socket.on('telemetry', (data) => {
  console.log('Received telemetry:', data);
});
```

## 项目结构

```
ems-backend/
├── src/
│   ├── app.ts                 # 应用入口
│   ├── config/                # 配置文件
│   ├── controllers/           # 控制器
│   ├── services/              # 业务服务
│   ├── routes/                # 路由定义
│   ├── middleware/            # 中间件
│   ├── models/                # 数据模型
│   ├── utils/                 # 工具函数
│   └── websocket/             # WebSocket服务
├── logs/                      # 日志文件
├── package.json
└── tsconfig.json
```

## 环境变量说明

查看 `.env.example` 文件了解所有可配置的环境变量。

主要配置项：
- `AWS_REGION` - AWS区域
- `S3_DATA_LAKE_BUCKET` - S3数据湖桶名
- `REDIS_HOST` - Redis主机
- `JWT_SECRET` - JWT密钥

## 开发指南

### 添加新的API端点

1. 在 `models/interfaces/` 创建接口定义
2. 在 `services/` 创建服务类
3. 在 `controllers/` 创建控制器
4. 在 `routes/` 创建路由
5. 在 `middleware/validation.middleware.ts` 添加验证规则

### 错误处理

使用自定义错误类：
```typescript
import { ValidationError, NotFoundError } from './middleware/error.middleware';

throw new ValidationError('Invalid input');
throw new NotFoundError('Device');
```

### 日志记录

```typescript
import { createLogger } from './utils/logger';

const logger = createLogger('MyModule');
logger.info('Information message');
logger.error('Error message', error);
```

## 生产部署

### Docker部署

```bash
docker build -t ems-backend .
docker run -p 3000:3000 --env-file .env ems-backend
```

### PM2部署

```bash
npm run build
pm2 start dist/app.js --name ems-backend
```

## 性能优化

1. **缓存策略**: 使用Redis缓存热点数据
2. **数据分页**: 所有列表API支持分页
3. **连接池**: AWS SDK自动管理连接池
4. **压缩**: 启用gzip压缩响应

## 安全考虑

1. **认证**: JWT token认证
2. **授权**: 基于角色的访问控制
3. **速率限制**: API请求限流
4. **数据验证**: Joi验证输入
5. **安全头**: Helmet设置安全响应头

## 故障排查

### 常见问题

1. **AWS连接失败**: 检查AWS凭证和区域配置
2. **Redis连接失败**: 确保Redis服务运行
3. **端口占用**: 修改PORT环境变量

### 日志位置

- 应用日志: `logs/combined.log`
- 错误日志: `logs/error.log`
- HTTP日志: `logs/http.log`

## 贡献指南

1. Fork项目
2. 创建特性分支
3. 提交变更
4. 推送到分支
5. 创建Pull Request

## 许可证

MIT