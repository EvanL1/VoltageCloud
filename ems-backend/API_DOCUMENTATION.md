# EMS Backend API 文档

## 基础信息

- **基础URL**: `http://localhost:3000/api/v1`
- **认证方式**: JWT Bearer Token
- **内容类型**: `application/json`

## 认证流程

### 1. 登录获取Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "admin123"
}
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "1",
      "email": "admin@example.com",
      "name": "Admin User",
      "role": "ADMIN"
    },
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expiresIn": "7d"
  }
}
```

### 2. 使用Token访问API

```http
GET /api/v1/devices
Authorization: Bearer YOUR_TOKEN_HERE
```

## API详细说明

### 设备管理

#### 获取设备列表

```http
GET /api/v1/devices?page=1&limit=20&status=ACTIVE&deviceType=sensor
```

**查询参数**:
- `page` (number): 页码，默认1
- `limit` (number): 每页数量，默认20，最大100
- `status` (string): 设备状态过滤 (ACTIVE, INACTIVE, MAINTENANCE, ERROR)
- `deviceType` (string): 设备类型过滤
- `location` (string): 位置过滤

**响应示例**:
```json
{
  "success": true,
  "data": {
    "devices": [
      {
        "deviceId": "device-001",
        "thingName": "sensor-001",
        "thingType": "temperature-sensor",
        "attributes": {
          "deviceType": "sensor",
          "location": "Building A",
          "firmware": "1.0.0"
        },
        "status": "ACTIVE",
        "connectionState": "CONNECTED",
        "lastSeen": "2024-01-10T10:30:00Z",
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-10T10:30:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 50,
      "pages": 3
    },
    "filters": {
      "status": "ACTIVE",
      "deviceType": "sensor",
      "location": null
    }
  }
}
```

#### 创建设备

```http
POST /api/v1/devices
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN

{
  "thingName": "new-sensor-001",
  "attributes": {
    "deviceType": "temperature-sensor",
    "location": "Building B Floor 2",
    "firmware": "1.0.0",
    "serialNumber": "SN123456789"
  },
  "generateCertificate": true
}
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "device": {
      "deviceId": "new-sensor-001",
      "thingName": "new-sensor-001",
      "attributes": {...}
    },
    "certificate": {
      "certificateArn": "arn:aws:iot:us-east-1:123456789:cert/...",
      "certificateId": "abc123...",
      "certificatePem": "-----BEGIN CERTIFICATE-----\n...",
      "privateKey": "-----BEGIN RSA PRIVATE KEY-----\n..."
    }
  }
}
```

### 遥测数据

#### 获取历史数据

```http
GET /api/v1/telemetry/device-001?startTime=2024-01-01T00:00:00Z&endTime=2024-01-02T00:00:00Z&page=1&limit=100&metrics[]=temperature&metrics[]=humidity
```

**查询参数**:
- `startTime` (ISO 8601): 开始时间 (必需)
- `endTime` (ISO 8601): 结束时间 (必需)
- `page` (number): 页码
- `limit` (number): 每页数量
- `metrics[]` (array): 要返回的指标列表

**响应示例**:
```json
{
  "success": true,
  "data": {
    "data": [
      {
        "deviceId": "device-001",
        "timestamp": "2024-01-01T10:00:00Z",
        "metrics": {
          "temperature": 25.5,
          "humidity": 60.2
        },
        "metadata": {}
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 100,
      "total": 1440,
      "pages": 15
    },
    "summary": {
      "deviceId": "device-001",
      "startTime": "2024-01-01T00:00:00Z",
      "endTime": "2024-01-02T00:00:00Z",
      "totalRecords": 1440,
      "metrics": ["temperature", "humidity"]
    }
  }
}
```

#### 获取聚合数据

```http
GET /api/v1/telemetry/device-001/aggregate?startTime=2024-01-01T00:00:00Z&endTime=2024-01-08T00:00:00Z&metric=temperature&period=DAY&function=AVG
```

**查询参数**:
- `startTime` (ISO 8601): 开始时间 (必需)
- `endTime` (ISO 8601): 结束时间 (必需)
- `metric` (string): 指标名称 (必需)
- `period` (string): 聚合周期 (HOUR, DAY, WEEK, MONTH) (必需)
- `function` (string): 聚合函数 (MIN, MAX, AVG, SUM, COUNT)

**响应示例**:
```json
{
  "success": true,
  "data": {
    "deviceId": "device-001",
    "metric": "temperature",
    "period": "DAY",
    "function": "AVG",
    "data": [
      {
        "timestamp": "2024-01-01T00:00:00Z",
        "avg": 24.5,
        "count": 144
      },
      {
        "timestamp": "2024-01-02T00:00:00Z",
        "avg": 25.1,
        "count": 144
      }
    ],
    "summary": {
      "startTime": "2024-01-01T00:00:00Z",
      "endTime": "2024-01-08T00:00:00Z",
      "dataPoints": 1008,
      "aggregatedPoints": 7
    }
  }
}
```

### 能源管理

#### 获取能源消耗

```http
GET /api/v1/energy/consumption?deviceId=device-001&startTime=2024-01-01T00:00:00Z&endTime=2024-01-31T00:00:00Z&period=DAY
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "consumption": [
      {
        "deviceId": "device-001",
        "timestamp": "2024-01-01T00:00:00Z",
        "period": "DAY",
        "consumption": {
          "total": 245.5,
          "peak": 147.3,
          "offPeak": 98.2,
          "average": 10.23
        },
        "cost": {
          "total": 36.83,
          "peak": 29.46,
          "offPeak": 9.82,
          "currency": "USD"
        },
        "unit": "kWh"
      }
    ],
    "summary": {
      "totalConsumption": 7604.5,
      "totalCost": 1140.68,
      "averageConsumption": 245.31,
      "peakConsumption": 312.4,
      "periods": 31
    },
    "parameters": {
      "devices": ["device-001"],
      "period": {
        "start": "2024-01-01T00:00:00Z",
        "end": "2024-01-31T00:00:00Z"
      },
      "aggregation": "DAY",
      "groupBy": null
    }
  }
}
```

#### 获取能效分析

```http
GET /api/v1/energy/efficiency?deviceId=device-001&startTime=2024-01-01T00:00:00Z&endTime=2024-01-31T00:00:00Z&benchmarkType=industry
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "deviceId": "device-001",
    "timestamp": "2024-01-31T23:59:59Z",
    "period": "DAY",
    "metrics": {
      "efficiency": 87.5,
      "powerFactor": 0.92,
      "loadFactor": 0.75,
      "utilizationRate": 0.82
    },
    "benchmarks": {
      "industry": 85,
      "target": 90,
      "improvement": 2.94
    },
    "recommendations": [
      {
        "id": "pf-001",
        "priority": "HIGH",
        "category": "EQUIPMENT",
        "title": "Install Power Factor Correction",
        "description": "Power factor is 0.92. Installing capacitor banks can improve it to 0.95+",
        "potentialSavings": {
          "energy": 5,
          "cost": 800,
          "co2": 200
        },
        "implementationCost": 3000,
        "paybackPeriod": 45,
        "status": "NEW"
      }
    ]
  }
}
```

### WebSocket实时数据

#### 连接示例

```javascript
const socket = io('http://localhost:3000', {
  path: '/ws',
  auth: {
    token: 'YOUR_JWT_TOKEN'
  }
});

// 连接成功
socket.on('connected', (data) => {
  console.log('Connected:', data);
  
  // 订阅设备
  socket.emit('subscribe:device', { deviceId: 'device-001' });
});

// 接收遥测数据
socket.on('telemetry', (data) => {
  console.log('Telemetry update:', data);
  // data = {
  //   topic: 'device/device-001/telemetry',
  //   deviceId: 'device-001',
  //   timestamp: '2024-01-10T10:30:00Z',
  //   data: { temperature: 25.5, humidity: 60.2 }
  // }
});

// 订阅所有设备
socket.emit('subscribe', { topics: ['telemetry:all'] });

// 断开连接
socket.disconnect();
```

## 错误响应

所有错误响应遵循统一格式：

```json
{
  "success": false,
  "error": {
    "message": "错误描述",
    "code": "ERROR_CODE",
    "details": {} // 可选的详细信息
  },
  "requestId": "req_1234567890_abcdefghi" // 请求ID用于追踪
}
```

### 常见错误码

| HTTP状态码 | 错误码 | 说明 |
|-----------|-------|------|
| 400 | VALIDATION_ERROR | 请求参数验证失败 |
| 401 | AUTHENTICATION_ERROR | 认证失败或Token无效 |
| 403 | AUTHORIZATION_ERROR | 权限不足 |
| 404 | NOT_FOUND | 资源不存在 |
| 409 | CONFLICT_ERROR | 资源冲突（如重复创建） |
| 429 | RATE_LIMIT_ERROR | 请求频率超限 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |
| 503 | EXTERNAL_SERVICE_ERROR | 外部服务（如AWS）错误 |

## 分页说明

所有列表类API都支持分页，使用统一的分页参数：

- `page`: 页码，从1开始
- `limit`: 每页数量，默认20，最大100

响应中包含分页信息：

```json
{
  "pagination": {
    "page": 1,      // 当前页
    "limit": 20,    // 每页数量
    "total": 100,   // 总记录数
    "pages": 5      // 总页数
  }
}
```

## 速率限制

- 默认限制：每15分钟100个请求
- 认证用户：每15分钟1000个请求
- 超出限制返回429错误

响应头包含限制信息：
- `X-RateLimit-Limit`: 限制数量
- `X-RateLimit-Remaining`: 剩余请求数
- `X-RateLimit-Reset`: 重置时间

## 数据格式

### 时间格式
所有时间使用ISO 8601格式：`YYYY-MM-DDTHH:mm:ss.sssZ`

### 数值精度
- 温度：保留1位小数
- 湿度：保留1位小数
- 功率：保留2位小数
- 能耗：保留2位小数
- 成本：保留2位小数

## 批量操作

某些API支持批量操作，通过POST请求体传递多个项目：

```http
POST /api/v1/devices/batch/update
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN

{
  "deviceIds": ["device-001", "device-002", "device-003"],
  "attributes": {
    "firmware": "2.0.0"
  }
}
```