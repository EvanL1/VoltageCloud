# IoT 数据湖访问指南

本指南详细说明如何在 IoT 平台架构中访问和使用数据湖功能。

## 📊 数据湖架构概览

### 分层存储架构

```
数据湖架构
├── Raw Layer (原始层)
│   ├── 直接从 IoT 设备收集的原始数据
│   ├── JSON 格式存储
│   └── 按日期分区 (year/month/day)
├── Processed Layer (处理层)  
│   ├── 经过清洗和转换的数据
│   ├── Parquet 格式，支持高效查询
│   └── 包含衍生字段和分类
├── Curated Layer (精选层)
│   ├── 针对特定业务场景的数据集
│   ├── 高度优化的数据结构
│   └── 预计算的聚合指标
└── Analytics Layer (分析层)
    ├── 查询结果缓存
    ├── 报表和仪表板数据
    └── ML 模型训练数据
```

### 核心组件

- **S3 存储桶**: 多层数据存储
- **AWS Glue**: 数据目录和 ETL 处理
- **Amazon Athena**: 无服务器查询引擎
- **Step Functions**: 数据处理工作流
- **API Gateway + Lambda**: 数据访问接口

## 🚀 访问方式

### 1. RESTful API 访问

#### API 端点概览

```bash
https://your-api-gateway-url/stage/
├── query/
│   ├── sql (POST)          # 执行 SQL 查询
│   └── tables (GET)        # 列出所有表
├── data/
│   ├── raw (GET)           # 查询原始数据
│   ├── processed (GET)     # 查询处理后数据
│   └── curated (GET)       # 查询精选数据
└── analytics/
    ├── dashboards (GET)    # 列出仪表板
    └── reports (GET)       # 生成报表
```

#### SQL 查询示例

```bash
# 执行自定义 SQL 查询
curl -X POST "https://your-api-gateway-url/stage/query/sql" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT device_id, AVG(temperature) as avg_temp FROM iot_data_lake.raw_iot_data WHERE year='\''2024'\'' GROUP BY device_id"
  }'
```

#### 数据层查询示例

```bash
# 查询特定设备的原始数据
curl -X GET "https://your-api-gateway-url/stage/data/raw?device_id=device001&start_date=2024-01-01&end_date=2024-01-31&limit=100"

# 查询处理后的小时聚合数据
curl -X GET "https://your-api-gateway-url/stage/data/processed?start_date=2024-01-01&limit=50"

# 生成设备分析报表
curl -X GET "https://your-api-gateway-url/stage/analytics/reports?type=device_analysis&start_date=2024-01-01&end_date=2024-01-31"
```

### 2. AWS Console 访问

#### Amazon Athena 查询

1. 登录 AWS Console
2. 导航到 Amazon Athena
3. 选择工作组 `iot-analytics`
4. 执行查询示例：

```sql
-- 查看所有可用表
SHOW TABLES IN iot_data_lake;

-- 查询设备数据概览
SELECT 
    device_id,
    COUNT(*) as total_readings,
    AVG(temperature) as avg_temperature,
    AVG(humidity) as avg_humidity
FROM iot_data_lake.raw_iot_data 
WHERE year = '2024' AND month = '01'
GROUP BY device_id
ORDER BY total_readings DESC;

-- 查询小时趋势
SELECT 
    hour_timestamp,
    device_id,
    avg_temperature,
    reading_count
FROM iot_data_lake.processed_iot_data_hourly
WHERE year = '2024' AND month = '01' AND day = '15'
ORDER BY hour_timestamp;
```

#### AWS Glue 数据目录

1. 导航到 AWS Glue Console
2. 选择 "Databases" → `iot_data_lake`
3. 浏览表结构和元数据：
   - `raw_iot_data`: 原始传感器数据
   - `processed_iot_data_detailed`: 处理后的详细数据
   - `processed_iot_data_hourly`: 小时聚合数据
   - `processed_device_statistics`: 设备统计信息

### 3. AWS SDK 编程访问

#### Python 示例

```python
import boto3
import json

# 初始化客户端
athena_client = boto3.client('athena')
s3_client = boto3.client('s3')

# 执行 Athena 查询
def query_iot_data(sql_query):
    response = athena_client.start_query_execution(
        QueryString=sql_query,
        QueryExecutionContext={'Database': 'iot_data_lake'},
        WorkGroup='iot-analytics'
    )
    
    query_execution_id = response['QueryExecutionId']
    
    # 等待查询完成
    while True:
        result = athena_client.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        status = result['QueryExecution']['Status']['State']
        
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(2)
    
    if status == 'SUCCEEDED':
        return athena_client.get_query_results(
            QueryExecutionId=query_execution_id
        )
    else:
        raise Exception(f"Query failed with status: {status}")

# 使用示例
result = query_iot_data("""
    SELECT device_id, temperature, humidity, from_unixtime(timestamp) as reading_time
    FROM iot_data_lake.raw_iot_data 
    WHERE device_id = 'device001' 
    ORDER BY timestamp DESC 
    LIMIT 10
""")
```

#### JavaScript/Node.js 示例

```javascript
const AWS = require('aws-sdk');
const athena = new AWS.Athena({region: 'us-east-1'});

async function queryIoTData(sqlQuery) {
    const params = {
        QueryString: sqlQuery,
        QueryExecutionContext: {
            Database: 'iot_data_lake'
        },
        WorkGroup: 'iot-analytics'
    };
    
    const execution = await athena.startQueryExecution(params).promise();
    const executionId = execution.QueryExecutionId;
    
    // 等待查询完成
    let status = 'RUNNING';
    while (status === 'RUNNING' || status === 'QUEUED') {
        const result = await athena.getQueryExecution({
            QueryExecutionId: executionId
        }).promise();
        
        status = result.QueryExecution.Status.State;
        if (status === 'RUNNING' || status === 'QUEUED') {
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
    }
    
    if (status === 'SUCCEEDED') {
        return await athena.getQueryResults({
            QueryExecutionId: executionId
        }).promise();
    } else {
        throw new Error(`Query failed with status: ${status}`);
    }
}

// 使用示例
queryIoTData(`
    SELECT device_id, AVG(temperature) as avg_temp 
    FROM iot_data_lake.processed_iot_data_hourly 
    WHERE year = '2024' 
    GROUP BY device_id
`).then(result => {
    console.log(JSON.stringify(result, null, 2));
}).catch(err => {
    console.error('Error:', err);
});
```

## 📈 常用查询示例

### 设备监控查询

```sql
-- 1. 实时设备状态
SELECT 
    device_id,
    MAX(from_unixtime(timestamp)) as last_seen,
    AVG(temperature) as current_avg_temp,
    AVG(humidity) as current_avg_humidity
FROM iot_data_lake.raw_iot_data 
WHERE from_unixtime(timestamp) >= current_timestamp - interval '1' hour
GROUP BY device_id;

-- 2. 异常温度检测
SELECT 
    device_id,
    temperature,
    humidity,
    from_unixtime(timestamp) as reading_time
FROM iot_data_lake.raw_iot_data 
WHERE temperature > 40 OR temperature < -10
ORDER BY timestamp DESC;

-- 3. 设备活跃度分析
SELECT 
    device_id,
    COUNT(*) as daily_readings,
    AVG(temperature) as avg_temp,
    MIN(temperature) as min_temp,
    MAX(temperature) as max_temp
FROM iot_data_lake.raw_iot_data 
WHERE year = '2024' AND month = '01' AND day = '15'
GROUP BY device_id
HAVING COUNT(*) > 100;
```

### 趋势分析查询

```sql
-- 1. 小时温度趋势
SELECT 
    hour_timestamp,
    AVG(avg_temperature) as overall_avg_temp,
    MIN(min_temperature) as overall_min_temp,
    MAX(max_temperature) as overall_max_temp,
    SUM(reading_count) as total_readings
FROM iot_data_lake.processed_iot_data_hourly 
WHERE year = '2024' AND month = '01'
GROUP BY hour_timestamp
ORDER BY hour_timestamp;

-- 2. 设备舒适度指数分析
SELECT 
    comfort_index,
    COUNT(*) as reading_count,
    COUNT(DISTINCT device_id) as device_count,
    AVG(temperature) as avg_temp,
    AVG(humidity) as avg_humidity
FROM iot_data_lake.processed_iot_data_detailed
WHERE year = '2024' AND month = '01'
GROUP BY comfort_index;

-- 3. 周模式分析
SELECT 
    day_of_week,
    hour_of_day,
    AVG(temperature) as avg_temperature,
    AVG(humidity) as avg_humidity,
    COUNT(*) as reading_count
FROM iot_data_lake.processed_iot_data_detailed
WHERE year = '2024' AND month = '01'
GROUP BY day_of_week, hour_of_day
ORDER BY day_of_week, hour_of_day;
```

### 性能和成本优化查询

```sql
-- 1. 数据量统计
SELECT 
    year, month, day,
    COUNT(*) as daily_records,
    COUNT(DISTINCT device_id) as active_devices,
    ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT device_id), 2) as avg_readings_per_device
FROM iot_data_lake.raw_iot_data 
GROUP BY year, month, day
ORDER BY year, month, day;

-- 2. 存储使用情况分析
SELECT 
    year, month,
    COUNT(*) as monthly_records,
    COUNT(DISTINCT device_id) as unique_devices,
    ROUND(COUNT(*) / 1000000.0, 2) as millions_of_records
FROM iot_data_lake.raw_iot_data 
GROUP BY year, month
ORDER BY year, month;
```

## 🔒 访问权限和安全

### IAM 权限要求

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "athena:StartQueryExecution",
                "athena:GetQueryExecution",
                "athena:GetQueryResults",
                "athena:ListQueryExecutions"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::iot-datalake-*",
                "arn:aws:s3:::iot-datalake-*/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "glue:GetTable",
                "glue:GetTables",
                "glue:GetDatabase",
                "glue:GetDatabases"
            ],
            "Resource": "*"
        }
    ]
}
```

### 数据安全最佳实践

1. **加密存储**: 所有 S3 存储桶启用服务端加密
2. **访问控制**: 使用 IAM 角色和策略控制访问权限
3. **VPC 端点**: 通过 VPC 端点访问 S3 和 Glue 服务
4. **审计日志**: 启用 CloudTrail 记录数据访问日志
5. **数据分类**: 根据敏感度对数据进行分类和标记

## 📊 监控和告警

### CloudWatch 指标

- **Athena 查询性能**: 查询执行时间、数据扫描量
- **S3 存储使用量**: 各层数据存储大小和增长趋势
- **Glue Job 执行**: ETL 任务成功率和执行时间
- **API Gateway 使用**: 请求量、错误率、延迟

### 告警配置示例

```bash
# 创建高数据扫描量告警
aws cloudwatch put-metric-alarm \
  --alarm-name "HighAthenaDataScanned" \
  --alarm-description "Athena query scanning too much data" \
  --metric-name "DataScannedInBytes" \
  --namespace "AWS/Athena" \
  --statistic "Sum" \
  --period 3600 \
  --threshold 10737418240 \
  --comparison-operator "GreaterThanThreshold" \
  --evaluation-periods 1
```

## 🚀 部署和配置

### 部署数据湖栈

```bash
# 部署完整的数据湖基础设施
cdk deploy DataLakeStack

# 上传 Glue ETL 脚本
aws s3 cp lambda/glue_etl_scripts/raw_to_processed.py \
  s3://your-analytics-bucket/scripts/raw_to_processed.py

# 触发初始 ETL 处理
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:region:account:stateMachine:iot-data-processing" \
  --input '{}'
```

### 配置自动化处理

ETL 管道将自动每 6 小时运行一次，处理新的原始数据并更新处理层。你也可以手动触发：

```bash
# 手动触发数据处理工作流
aws stepfunctions start-execution \
  --state-machine-arn $(aws cloudformation describe-stacks \
    --stack-name DataLakeStack \
    --query 'Stacks[0].Outputs[?OutputKey==`DataProcessingWorkflowArn`].OutputValue' \
    --output text) \
  --input '{}'
```

## 🔧 故障排除

### 常见问题

1. **查询超时**: 增加查询超时时间或优化查询性能
2. **权限错误**: 检查 IAM 角色和策略配置
3. **分区问题**: 确保数据正确分区并更新表分区
4. **成本过高**: 使用列式存储格式和数据压缩

### 性能优化建议

1. **使用分区**: 按时间分区减少扫描数据量
2. **列式存储**: 使用 Parquet 格式提高查询性能
3. **数据压缩**: 启用压缩减少存储成本
4. **查询优化**: 使用 WHERE 子句限制扫描范围
5. **结果缓存**: 缓存频繁查询的结果

## 📝 最佳实践

1. **数据治理**: 建立数据质量检查和清洗流程
2. **成本控制**: 监控数据扫描量和存储使用情况
3. **性能监控**: 定期检查查询性能和优化建议
4. **备份策略**: 实施数据备份和恢复策略
5. **文档维护**: 保持数据字典和查询示例的更新

---

通过这个综合的数据湖解决方案，您可以高效地存储、处理和分析 IoT 数据，获得有价值的业务洞察。 