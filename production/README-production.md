# 🏭 生产环境部署指南

## 概述

这是一个企业级的 IoT PoC 生产环境部署方案，完全基于 AWS SDK，无需安装 CLI 工具，支持容器化部署和 CI/CD 集成。

## 🚀 主要特性

### 1. 无 CLI 依赖
- 完全使用 AWS SDK (boto3)
- 编程式资源管理
- 精确的错误处理
- 自动重试机制

### 2. 容器化部署
- Docker 容器化
- Docker Compose 编排
- 安全的非 root 用户
- 健康检查

### 3. 环境配置管理
- 基于环境变量的配置
- 多环境支持 (staging/production)
- 配置验证
- 成本估算

### 4. CI/CD 集成
- GitHub Actions 工作流
- 自动化测试
- 蓝绿部署
- Slack 通知

## 📋 前置要求

### 1. AWS 权限配置
```bash
# 生产环境需要的 IAM 权限
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "lambda:*",
        "iot:*",
        "timestream:*",
        "s3:*",
        "ec2:*",
        "logs:*",
        "iam:*",
        "sts:*"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2. 环境变量设置
```bash
# 必需的环境变量
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=123456789012
export ENVIRONMENT=production
export ALERT_EMAIL=admin@company.com

# 可选的环境变量
export LAMBDA_MEMORY_MB=512
export ENABLE_DETAILED_MONITORING=true
```

## 🛠️ 部署方式

### 方式一：直接 Python 部署

```bash
# 1. 安装依赖
pip install -r requirements.txt
pip install -r production/requirements-prod.txt

# 2. 配置环境变量
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=123456789012
export ENVIRONMENT=production
export ALERT_EMAIL=admin@company.com

# 3. 验证配置
python3 -c "
from production.config import load_production_config
config = load_production_config()
errors = config.validate()
if errors:
    print('配置错误:', errors)
    exit(1)
print('配置验证通过')
"

# 4. 部署基础设施
python production/deployment_manager.py

# 5. 运行测试
python production/test_runner.py
```

### 方式二：Docker 容器部署

```bash
# 1. 构建镜像
docker build -f production/Dockerfile -t iot-poc-prod .

# 2. 准备环境文件
cat > .env.prod << EOF
AWS_REGION=us-west-2
AWS_ACCOUNT_ID=123456789012
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
ENVIRONMENT=production
ALERT_EMAIL=admin@company.com
LAMBDA_MEMORY_MB=512
ENABLE_DETAILED_MONITORING=true
EOF

# 3. 创建 AWS 凭证卷
docker volume create aws-credentials
docker run --rm -v aws-credentials:/aws alpine sh -c "
  mkdir -p /aws && \
  echo '[default]' > /aws/credentials && \
  echo 'aws_access_key_id=${AWS_ACCESS_KEY_ID}' >> /aws/credentials && \
  echo 'aws_secret_access_key=${AWS_SECRET_ACCESS_KEY}' >> /aws/credentials
"

# 4. 使用 Docker Compose 部署
cd production
docker-compose --env-file ../.env.prod up --build
```

### 方式三：CI/CD 自动部署

1. **设置 GitHub Secrets**:
   ```
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_ACCOUNT_ID=123456789012
   ALERT_EMAIL=admin@company.com
   SLACK_WEBHOOK_URL=https://hooks.slack.com/...
   AWS_DEPLOY_ROLE_ARN=arn:aws:iam::123456789012:role/DeployRole
   ```

2. **推送到 main 分支触发自动部署**:
   ```bash
   git add .
   git commit -m "feat(production): deploy to production"
   git push origin main
   ```

3. **手动触发部署**:
   - 去 GitHub Actions 页面
   - 选择 "Production IoT PoC Deployment" 工作流
   - 点击 "Run workflow"
   - 选择环境 (staging/production)

## 🔧 配置管理

### 1. 环境配置
```python
# production/config.py 中的配置项

# 基础配置
ENVIRONMENT=production
STACK_NAME=IotPocStack
PROJECT_NAME=IoT-PoC


# Lambda 配置
LAMBDA_MEMORY_MB=512               # 内存大小
LAMBDA_TIMEOUT_SECONDS=60          # 超时时间
LAMBDA_BATCH_SIZE=100              # 批处理大小

# 安全配置
ENABLE_ENCRYPTION_AT_REST=true     # 静态加密
ENABLE_ENCRYPTION_IN_TRANSIT=true # 传输加密

# 监控配置
ENABLE_DETAILED_MONITORING=true   # 详细监控
ENABLE_X_RAY_TRACING=true         # X-Ray 追踪
LOG_RETENTION_DAYS=30             # 日志保留天数
```

### 2. 成本优化
```python
# 不同环境的配置建议

# Staging 环境 (成本优化)
LAMBDA_MEMORY_MB=256
ENABLE_DETAILED_MONITORING=false

# Production 环境 (性能优化)
LAMBDA_MEMORY_MB=512
ENABLE_DETAILED_MONITORING=true
```

## 🧪 测试和验证

### 1. 基础设施健康检查
```bash
# 运行全面测试
python production/test_runner.py

```

### 2. 端到端测试
```bash
# 发送测试消息
python3 -c "
from production.deployment_manager import DeploymentManager, DeploymentConfig
import time
manager = DeploymentManager(DeploymentConfig())

message = {
    'ts': int(time.time() * 1000),
    'temp': 25.5,
    'humidity': 60.0,
    'device_id': 'test-device-001'
}

success = manager.send_test_iot_message('devices/test-device-001/data', message)
print(f'消息发送: {\"成功\" if success else \"失败\"}')
"

# 查询 TimeStream 数据
python3 -c "
from production.deployment_manager import DeploymentManager, DeploymentConfig
manager = DeploymentManager(DeploymentConfig())

query = 'SELECT COUNT(*) as count FROM iot_poc.metrics WHERE time > ago(1h)'
results = manager.query_timestream(query)
print(f'最近1小时记录数: {results[0][\"count\"] if results else 0}')
"
```

## 📊 监控和告警

### 1. CloudWatch 指标
- Lambda 执行时长和错误率
- TimeStream 写入吞吐量
- S3 存储使用量

### 2. 自定义告警
```python
# 在 deployment_manager.py 中配置的告警
- Lambda 错误率 > 5%
- TimeStream 写入失败
- S3 上传失败
```

### 3. 日志聚合
```bash
# 查看应用日志
docker logs iot-poc-deployer

# 查看测试日志
docker logs iot-poc-tester

# 查看 CloudWatch 日志
aws logs tail /aws/lambda/IoTProcessorFunction --follow
```

## 🔐 安全最佳实践

### 1. IAM 权限最小化
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:DescribeStacks",
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack"
      ],
      "Resource": "arn:aws:cloudformation:*:*:stack/IotPocStack*/*"
    }
  ]
}
```

### 2. 数据加密
- 静态加密：所有存储服务启用 KMS 加密
- 传输加密：所有网络传输使用 TLS
- 密钥管理：使用 AWS KMS 管理加密密钥

### 3. 网络安全
- VPC 隔离：核心资源部署在私有子网
- 安全组：最小权限原则
- NAT 网关：Lambda 函数通过 NAT 访问互联网

## 💰 成本估算


```

## 🚨 故障排除

### 1. 常见问题

**部署失败**:
```bash
# 检查配置
python3 -c "
from production.config import load_production_config
config = load_production_config()
errors = config.validate()
print('配置错误:', errors if errors else '无')
"

# 检查 AWS 权限
aws sts get-caller-identity
aws cloudformation describe-stacks --stack-name IotPocStack
```


**Lambda 函数错误**:
```bash
# 查看 Lambda 日志
aws logs tail /aws/lambda/IoTProcessorFunction --follow

# 手动测试 Lambda
python3 -c "
from production.deployment_manager import DeploymentManager, DeploymentConfig
manager = DeploymentManager(DeploymentConfig())
outputs = manager.get_stack_outputs()
result = manager.test_lambda_function(
    outputs['LambdaFunctionName'], 
    {'test': 'data'}
)
print('Lambda测试结果:', result)
"
```

### 2. 紧急恢复程序

```bash
# 1. 快速回滚到上一个版本
git revert HEAD
git push origin main

# 2. 手动删除问题资源
python3 -c "
from production.deployment_manager import DeploymentManager, DeploymentConfig
manager = DeploymentManager(DeploymentConfig())
manager.cleanup_stack()
"

# 3. 重新部署
python production/deployment_manager.py
```

## 📞 支持和联系

- **技术支持**: platform-team@company.com
- **Slack 频道**: #iot-poc-support
- **文档**: https://wiki.company.com/iot-poc
- **监控面板**: https://grafana.company.com/iot-poc

## 🔄 版本更新

```bash
# 更新到最新版本
git pull origin main
pip install -r requirements.txt -U
pip install -r production/requirements-prod.txt -U

# 重新部署
python production/deployment_manager.py
```

---

🎉 **恭喜！你现在拥有了一个企业级的 IoT PoC 生产环境部署方案！** 