# 能源管理系统 ECS 部署架构

## 整体架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        用户访问层                              │
├─────────────────────────────────────────────────────────────┤
│            CloudFront (CDN)  →  ALB (负载均衡)               │
└────────────────────────────┬───────────────────────────────┘
                             │
┌────────────────────────────┴───────────────────────────────┐
│                      ECS Fargate 集群                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  Frontend   │  │  Frontend   │  │  Frontend   │       │
│  │  Service    │  │  Service    │  │  Service    │       │
│  │  (React)    │  │  (React)    │  │  (React)    │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                 │                 │               │
│         └─────────────────┴─────────────────┘               │
│                           │                                 │
│                     内部 ALB                                │
│                           │                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Backend   │  │   Backend   │  │   Backend   │       │
│  │   Service   │  │   Service   │  │   Service   │       │
│  │  (Node.js)  │  │  (Node.js)  │  │  (Node.js)  │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
└─────────┴──────────────────┴───────────────┴───────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        │                                         │
┌───────▼────────┐  ┌────────────┐  ┌───────────▼────────┐
│  API Gateway   │  │   Lambda   │  │  AWS IoT Core      │
│                │  │ Functions  │  │  (MQTT/WebSocket)  │
└────────────────┘  └────────────┘  └────────────────────┘
        │                  │                    │
┌───────▼────────────────────────────────────────────────┐
│            数据层 (DynamoDB, TimeStream, S3)            │
└────────────────────────────────────────────────────────┘
```

## VPC 网络设计

```yaml
VPC CIDR: 10.0.0.0/16

Public Subnets (跨3个AZ):
  - 10.0.1.0/24 (AZ-1a) - ALB, NAT Gateway
  - 10.0.2.0/24 (AZ-1b) - ALB, NAT Gateway
  - 10.0.3.0/24 (AZ-1c) - ALB, NAT Gateway

Private Subnets (跨3个AZ):
  - 10.0.11.0/24 (AZ-1a) - ECS Tasks
  - 10.0.12.0/24 (AZ-1b) - ECS Tasks
  - 10.0.13.0/24 (AZ-1c) - ECS Tasks

Database Subnets (跨3个AZ):
  - 10.0.21.0/24 (AZ-1a) - RDS (如需要)
  - 10.0.22.0/24 (AZ-1b) - RDS (如需要)
  - 10.0.23.0/24 (AZ-1c) - RDS (如需要)
```

## 前端项目结构

```
ems-frontend/
├── public/
│   └── index.html
├── src/
│   ├── api/               # API 接口定义
│   │   ├── energy.ts
│   │   ├── station.ts
│   │   ├── device.ts
│   │   └── auth.ts
│   ├── components/        # 通用组件
│   │   ├── Charts/
│   │   ├── Layout/
│   │   └── Common/
│   ├── pages/            # 页面组件（20个页面）
│   │   ├── Overview/
│   │   ├── Station/
│   │   ├── Device/
│   │   ├── Report/
│   │   ├── System/
│   │   └── Auth/
│   ├── store/            # Redux store
│   │   ├── slices/
│   │   └── index.ts
│   ├── utils/            # 工具函数
│   │   ├── request.ts
│   │   ├── auth.ts
│   │   └── websocket.ts
│   ├── hooks/            # 自定义hooks
│   │   ├── useRealtime.ts
│   │   └── usePermission.ts
│   ├── config/           # 配置文件
│   │   └── index.ts
│   ├── App.tsx
│   └── index.tsx
├── nginx/
│   └── default.conf      # Nginx配置
├── Dockerfile            # 多阶段构建
├── docker-compose.yml
├── .env.production
└── package.json
```

## 后端 API 架构

```
ems-backend/
├── src/
│   ├── controllers/      # 控制器层
│   │   ├── energy.controller.ts
│   │   ├── station.controller.ts
│   │   ├── device.controller.ts
│   │   └── auth.controller.ts
│   ├── services/         # 业务逻辑层
│   │   ├── iot.service.ts      # IoT数据接入
│   │   ├── realtime.service.ts  # 实时数据处理
│   │   └── analytics.service.ts # 数据分析
│   ├── models/           # 数据模型
│   ├── middleware/       # 中间件
│   │   ├── auth.ts
│   │   └── errorHandler.ts
│   ├── routes/           # 路由定义
│   ├── utils/            # 工具类
│   │   ├── aws-iot.ts   # AWS IoT SDK封装
│   │   └── cache.ts     # Redis缓存
│   ├── config/           # 配置
│   └── app.ts           # 应用入口
├── Dockerfile
└── package.json
```

## Dockerfile - 前端

```dockerfile
# ems-frontend/Dockerfile
# 构建阶段
FROM node:18-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY package*.json ./
RUN npm ci --only=production

# 复制源代码
COPY . .

# 构建应用
RUN npm run build

# 运行阶段
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/build /usr/share/nginx/html

# 复制nginx配置
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]
```

## Dockerfile - 后端

```dockerfile
# ems-backend/Dockerfile
FROM node:18-alpine

WORKDIR /app

# 安装依赖
COPY package*.json ./
RUN npm ci --only=production

# 复制源代码
COPY . .

# 构建TypeScript
RUN npm run build

# 暴露端口
EXPOSE 3000

# 启动应用
CMD ["node", "dist/app.js"]
```

## ECS 任务定义

```json
{
  "family": "ems-frontend-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "ems-frontend",
      "image": "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/ems-frontend:latest",
      "portMappings": [
        {
          "containerPort": 80,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "environment": [
        {
          "name": "REACT_APP_API_URL",
          "value": "https://api.ems.example.com"
        },
        {
          "name": "REACT_APP_WS_URL",
          "value": "wss://ws.ems.example.com"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ems-frontend",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

## 部署脚本

```bash
#!/bin/bash
# deploy-to-ecs.sh

# 设置变量
AWS_ACCOUNT_ID="your-account-id"
AWS_REGION="us-east-1"
ECR_REPO_FRONTEND="ems-frontend"
ECR_REPO_BACKEND="ems-backend"
ECS_CLUSTER="ems-cluster"
ECS_SERVICE_FRONTEND="ems-frontend-service"
ECS_SERVICE_BACKEND="ems-backend-service"

# 登录到 ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# 构建和推送前端镜像
echo "Building frontend image..."
cd ems-frontend
docker build -t $ECR_REPO_FRONTEND:latest .
docker tag $ECR_REPO_FRONTEND:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_FRONTEND:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_FRONTEND:latest

# 构建和推送后端镜像
echo "Building backend image..."
cd ../ems-backend
docker build -t $ECR_REPO_BACKEND:latest .
docker tag $ECR_REPO_BACKEND:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_BACKEND:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_BACKEND:latest

# 更新 ECS 服务
echo "Updating ECS services..."
aws ecs update-service --cluster $ECS_CLUSTER --service $ECS_SERVICE_FRONTEND --force-new-deployment
aws ecs update-service --cluster $ECS_CLUSTER --service $ECS_SERVICE_BACKEND --force-new-deployment

echo "Deployment completed!"
```

## AWS IoT 数据集成

```typescript
// src/services/iot.service.ts
import { IoTClient, ListThingsCommand } from "@aws-sdk/client-iot";
import { IoTDataPlaneClient, GetThingShadowCommand } from "@aws-sdk/client-iot-data-plane";
import { TimestreamQueryClient, QueryCommand } from "@aws-sdk/client-timestream-query";

export class IoTService {
  private iotClient: IoTClient;
  private iotDataClient: IoTDataPlaneClient;
  private timestreamClient: TimestreamQueryClient;

  constructor() {
    this.iotClient = new IoTClient({ region: process.env.AWS_REGION });
    this.iotDataClient = new IoTDataPlaneClient({ 
      region: process.env.AWS_REGION,
      endpoint: process.env.IOT_ENDPOINT 
    });
    this.timestreamClient = new TimestreamQueryClient({ 
      region: process.env.AWS_REGION 
    });
  }

  // 获取设备列表
  async getDevices() {
    const command = new ListThingsCommand({
      thingTypeName: "iot-demo-device-type"
    });
    const response = await this.iotClient.send(command);
    return response.things;
  }

  // 获取设备影子数据
  async getDeviceShadow(thingName: string) {
    const command = new GetThingShadowCommand({
      thingName: thingName
    });
    const response = await this.iotDataClient.send(command);
    const payload = JSON.parse(new TextDecoder().decode(response.payload));
    return payload;
  }

  // 查询时序数据
  async queryTimeSeriesData(deviceId: string, startTime: Date, endTime: Date) {
    const query = `
      SELECT time, measure_value::double as value
      FROM "iot-demo-timestream-db"."iot-demo-metrics-table"
      WHERE device_id = '${deviceId}'
        AND time between '${startTime.toISOString()}' and '${endTime.toISOString()}'
      ORDER BY time DESC
    `;
    
    const command = new QueryCommand({ QueryString: query });
    const response = await this.timestreamClient.send(command);
    return response.Rows;
  }

  // 订阅实时数据
  subscribeToDeviceData(deviceId: string, callback: (data: any) => void) {
    // 使用 AWS IoT SDK 的 MQTT 连接
    const topic = `device/${deviceId}/telemetry`;
    // 实现 MQTT 订阅逻辑
  }
}
```

## 实时数据推送

```typescript
// src/utils/websocket.ts
import { io, Socket } from "socket.io-client";

class WebSocketService {
  private socket: Socket | null = null;

  connect(url: string, token: string) {
    this.socket = io(url, {
      auth: { token },
      transports: ['websocket']
    });

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
    });

    this.socket.on('energy-data', (data) => {
      // 处理实时能源数据
      store.dispatch(updateEnergyData(data));
    });

    this.socket.on('device-status', (data) => {
      // 处理设备状态更新
      store.dispatch(updateDeviceStatus(data));
    });
  }

  subscribeToStation(stationId: string) {
    if (this.socket) {
      this.socket.emit('subscribe-station', { stationId });
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
    }
  }
}

export default new WebSocketService();
```

## 环境变量配置

```bash
# .env.production
# 前端环境变量
REACT_APP_API_URL=https://api.ems.example.com
REACT_APP_WS_URL=wss://ws.ems.example.com
REACT_APP_AWS_REGION=us-east-1
REACT_APP_COGNITO_USER_POOL_ID=us-east-1_xxxxx
REACT_APP_COGNITO_CLIENT_ID=xxxxx

# 后端环境变量
NODE_ENV=production
PORT=3000
AWS_REGION=us-east-1
IOT_ENDPOINT=xxxxx.iot.us-east-1.amazonaws.com
TIMESTREAM_DB=iot-demo-timestream-db
DYNAMODB_TABLE_PREFIX=ems-
REDIS_URL=redis://ems-redis.xxxxx.cache.amazonaws.com:6379
JWT_SECRET=your-secret-key
```

## CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy to ECS

on:
  push:
    branches: [main]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY_FRONTEND: ems-frontend
  ECR_REPOSITORY_BACKEND: ems-backend
  ECS_CLUSTER: ems-cluster
  ECS_SERVICE_FRONTEND: ems-frontend-service
  ECS_SERVICE_BACKEND: ems-backend-service

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v2

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v1
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}

    - name: Login to Amazon ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v1

    - name: Build and push frontend image
      env:
        ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
      run: |
        cd ems-frontend
        docker build -t $ECR_REGISTRY/$ECR_REPOSITORY_FRONTEND:latest .
        docker push $ECR_REGISTRY/$ECR_REPOSITORY_FRONTEND:latest

    - name: Build and push backend image
      env:
        ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
      run: |
        cd ems-backend
        docker build -t $ECR_REGISTRY/$ECR_REPOSITORY_BACKEND:latest .
        docker push $ECR_REGISTRY/$ECR_REPOSITORY_BACKEND:latest

    - name: Update ECS services
      run: |
        aws ecs update-service --cluster $ECS_CLUSTER --service $ECS_SERVICE_FRONTEND --force-new-deployment
        aws ecs update-service --cluster $ECS_CLUSTER --service $ECS_SERVICE_BACKEND --force-new-deployment
```

## 监控和日志

```yaml
# CloudWatch Dashboard 配置
Metrics:
  - ECS Task CPU/Memory Usage
  - ALB Request Count/Response Time
  - API Gateway 4XX/5XX Errors
  - Lambda Function Errors/Duration
  - IoT Core Message Count

Alarms:
  - High CPU Usage (> 80%)
  - High Memory Usage (> 80%)
  - API Error Rate (> 5%)
  - Task Health Check Failures

Logs:
  - /ecs/ems-frontend
  - /ecs/ems-backend
  - /aws/lambda/iot-data-processor
```

## 安全配置

```yaml
Security Groups:
  - ALB Security Group:
      - Inbound: 80/443 from 0.0.0.0/0
      - Outbound: All traffic
  
  - ECS Tasks Security Group:
      - Inbound: 80/3000 from ALB Security Group
      - Outbound: All traffic
  
  - RDS Security Group (如需要):
      - Inbound: 3306 from ECS Tasks Security Group
      - Outbound: None

IAM Roles:
  - ECS Task Role:
      - AmazonECSTaskExecutionRolePolicy
      - CloudWatchLogsFullAccess
      - AmazonDynamoDBReadOnlyAccess
      - AmazonTimestreamReadOnlyAccess
      - IoTDataAccess (自定义)
  
  - ECS Service Role:
      - AmazonEC2ContainerServiceRole
```

## 成本优化建议

1. **使用 Fargate Spot**
   - 对于非关键服务，使用 Fargate Spot 可节省高达 70% 的成本

2. **自动扩缩容**
   ```yaml
   Auto Scaling:
     - Target CPU: 70%
     - Min Tasks: 2
     - Max Tasks: 10
   ```

3. **CloudFront 缓存**
   - 静态资源缓存时间设置为 1 年
   - API 响应根据业务需求设置缓存

4. **预留实例**
   - 对于稳定的工作负载，购买 Reserved Instances