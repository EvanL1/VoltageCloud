# 🔧 环境变量配置指南

## 概述

为了快速实现完整测试，您需要配置以下环境变量。这些变量分为必需、推荐和可选三个级别。

## 🔴 必需的环境变量

### AWS 基础配置

```bash
# AWS 基本配置
export AWS_REGION=us-east-1                    # AWS 区域
export AWS_ACCOUNT_ID=123456789012              # 您的 AWS 账户 ID

# AWS 凭证（如果不使用 AWS CLI 配置）
export AWS_ACCESS_KEY_ID=AKIA...               # AWS 访问密钥 ID
export AWS_SECRET_ACCESS_KEY=...               # AWS 密钥访问密钥
```

### 项目配置

```bash
# 项目基础信息
export ENVIRONMENT=testing                      # 环境名称 (testing/staging/production)
export STACK_NAME=IotPocStack                   # CloudFormation 堆栈名称
export PROJECT_NAME=IoT-PoC                     # 项目名称
```

## 🟡 推荐的环境变量

### 测试配置

```bash
# 测试环境配置
export PYTEST_TIMEOUT=300                      # pytest 超时时间（秒）
export TEST_COVERAGE_THRESHOLD=80               # 代码覆盖率阈值
export ENABLE_INTEGRATION_TESTS=true           # 启用集成测试
```

### 资源配置

```bash
# Lambda 配置
export LAMBDA_MEMORY_MB=512                    # Lambda 内存大小
export LAMBDA_TIMEOUT_SECONDS=60               # Lambda 超时时间

# 监控配置
export ENABLE_DETAILED_MONITORING=true         # 启用详细监控
export ENABLE_X_RAY_TRACING=true              # 启用 X-Ray 追踪
```

### 通知配置

```bash
# 告警和通知
export ALERT_EMAIL=admin@company.com           # 告警邮箱
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...  # Slack 通知 URL
```

## 🟢 可选的环境变量

### 高级测试配置

```bash
# 测试并行度
export PYTEST_WORKERS=4                        # 并行测试进程数
export MAX_TEST_DURATION=1800                  # 最大测试运行时间（秒）

# 测试数据
export TEST_DEVICE_COUNT=10                    # 测试设备数量
export TEST_MESSAGE_COUNT=100                  # 测试消息数量
```

### 安全配置

```bash
# 加密配置
export ENABLE_ENCRYPTION_AT_REST=true          # 启用静态加密
export ENABLE_ENCRYPTION_IN_TRANSIT=true      # 启用传输加密
export KMS_KEY_ID=arn:aws:kms:...             # KMS 密钥 ID
```

### 成本控制

```bash
# 资源限制
export MAX_SQS_MESSAGES=1000                   # SQS 最大消息数
export S3_LIFECYCLE_DAYS=30                    # S3 生命周期天数
export TIMESTREAM_RETENTION_DAYS=7             # TimeStream 保留天数
```

### CI/CD 配置

```bash
# 部署配置
export AWS_DEPLOY_ROLE_ARN=arn:aws:iam::...   # 部署角色 ARN
export DEPLOY_TIMEOUT=1800                     # 部署超时时间
export ENABLE_BLUE_GREEN_DEPLOY=false          # 启用蓝绿部署
```

## 📋 快速配置模板

### 本地开发环境

创建 `.env.local` 文件：

```bash
# === AWS 基础配置 ===
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=your-account-id

# === 项目配置 ===
ENVIRONMENT=development
STACK_NAME=IotPocStack-Dev
PROJECT_NAME=IoT-PoC

# === 测试配置 ===
ENABLE_INTEGRATION_TESTS=true
TEST_COVERAGE_THRESHOLD=75
PYTEST_TIMEOUT=300

# === Lambda 配置 ===
LAMBDA_MEMORY_MB=256
LAMBDA_TIMEOUT_SECONDS=30

# === 监控配置 ===
ENABLE_DETAILED_MONITORING=false
ENABLE_X_RAY_TRACING=false

# === 通知配置（可选）===
# ALERT_EMAIL=your-email@company.com
# SLACK_WEBHOOK_URL=your-slack-webhook
```

### 测试环境

创建 `.env.testing` 文件：

```bash
# === AWS 基础配置 ===
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=your-account-id

# === 项目配置 ===
ENVIRONMENT=testing
STACK_NAME=IotPocStack-Test
PROJECT_NAME=IoT-PoC

# === 测试配置 ===
ENABLE_INTEGRATION_TESTS=true
TEST_COVERAGE_THRESHOLD=80
PYTEST_TIMEOUT=600
PYTEST_WORKERS=4

# === Lambda 配置 ===
LAMBDA_MEMORY_MB=512
LAMBDA_TIMEOUT_SECONDS=60

# === 监控配置 ===
ENABLE_DETAILED_MONITORING=true
ENABLE_X_RAY_TRACING=true

# === 安全配置 ===
ENABLE_ENCRYPTION_AT_REST=true
ENABLE_ENCRYPTION_IN_TRANSIT=true

# === 通知配置 ===
ALERT_EMAIL=test-alerts@company.com
```

### 生产环境

创建 `.env.production` 文件：

```bash
# === AWS 基础配置 ===
AWS_REGION=us-west-2
AWS_ACCOUNT_ID=your-production-account-id

# === 项目配置 ===
ENVIRONMENT=production
STACK_NAME=IotPocStack
PROJECT_NAME=IoT-PoC

# === Lambda 配置 ===
LAMBDA_MEMORY_MB=1024
LAMBDA_TIMEOUT_SECONDS=300

# === 监控配置 ===
ENABLE_DETAILED_MONITORING=true
ENABLE_X_RAY_TRACING=true

# === 安全配置 ===
ENABLE_ENCRYPTION_AT_REST=true
ENABLE_ENCRYPTION_IN_TRANSIT=true

# === 成本控制 ===
S3_LIFECYCLE_DAYS=90
TIMESTREAM_RETENTION_DAYS=30

# === 通知配置 ===
ALERT_EMAIL=production-alerts@company.com
SLACK_WEBHOOK_URL=your-production-slack-webhook

# === 资源标记 ===
RESOURCE_OWNER=platform-team
COST_CENTER=engineering
```

## 🚀 快速启动命令

### 1. 设置环境变量

```bash
# 方法 1: 直接导出（临时）
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ENVIRONMENT=testing

# 方法 2: 从文件加载（推荐）
source .env.testing

# 方法 3: 使用 direnv（自动化）
echo "source_env .env.testing" > .envrc
direnv allow
```

### 2. 验证配置

```bash
# 验证 AWS 配置
python3 -c "
import os
import boto3
print('AWS Region:', os.environ.get('AWS_REGION'))
print('AWS Account:', boto3.client('sts').get_caller_identity()['Account'])
print('Environment:', os.environ.get('ENVIRONMENT'))
"
```

### 3. 运行完整测试

```bash
# 激活 conda 环境
conda activate iot-testing

# 运行所有测试
./run_tests_conda.sh all -v -r

# 或者运行特定测试
./run_tests_conda.sh unit integration -v
```

## 🔍 环境变量检查脚本

创建 `check_env.py` 脚本来验证配置：

```python
#!/usr/bin/env python3
"""检查环境变量配置"""

import os
import boto3
from typing import List, Tuple

def check_required_vars() -> List[Tuple[str, bool, str]]:
    """检查必需的环境变量"""
    required_vars = [
        ('AWS_REGION', 'AWS 区域'),
        ('ENVIRONMENT', '环境名称'),
    ]
    
    results = []
    for var, desc in required_vars:
        value = os.environ.get(var)
        results.append((var, bool(value), desc))
    
    return results

def check_aws_credentials() -> bool:
    """检查 AWS 凭证"""
    try:
        sts = boto3.client('sts')
        sts.get_caller_identity()
        return True
    except Exception:
        return False

def main():
    print("🔍 环境变量配置检查")
    print("=" * 50)
    
    # 检查必需变量
    print("\n📋 必需的环境变量:")
    required_results = check_required_vars()
    for var, exists, desc in required_results:
        status = "✅" if exists else "❌"
        value = os.environ.get(var, "未设置")
        print(f"  {status} {var}: {value} ({desc})")
    
    # 检查 AWS 凭证
    print("\n🔐 AWS 凭证检查:")
    if check_aws_credentials():
        print("  ✅ AWS 凭证配置正确")
        try:
            identity = boto3.client('sts').get_caller_identity()
            print(f"     账户: {identity['Account']}")
            print(f"     用户: {identity.get('UserId', 'N/A')}")
        except Exception as e:
            print(f"  ⚠️  无法获取身份信息: {e}")
    else:
        print("  ❌ AWS 凭证配置错误")
    
    print("\n🎯 推荐的环境变量:")
    recommended_vars = [
        'LAMBDA_MEMORY_MB',
        'ENABLE_DETAILED_MONITORING',
        'ALERT_EMAIL'
    ]
    
    for var in recommended_vars:
        value = os.environ.get(var, "未设置")
        status = "✅" if value != "未设置" else "⚠️"
        print(f"  {status} {var}: {value}")

if __name__ == "__main__":
    main()
```

运行检查：

```bash
python3 check_env.py
```

## 📚 相关文档

- [AWS CLI 配置指南](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)
- [Conda 环境管理](environment-testing.yml)
- [测试运行指南](TESTING_GUIDE.md)
- [生产部署指南](production/README-production.md)

## 🆘 常见问题

### Q: AWS 凭证配置失败？
```bash
# 检查 AWS CLI 配置
aws configure list
aws sts get-caller-identity

# 或者直接设置环境变量
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
```

### Q: 测试环境依赖安装失败？
```bash
# 重建 conda 环境
conda env remove -n iot-testing
conda env create -f environment-testing.yml
conda activate iot-testing
```

### Q: 权限不足错误？
确保您的 AWS 用户/角色具有以下权限：
- CloudFormation 完全访问
- Lambda 完全访问
- IoT Core 完全访问
- TimeStream 完全访问
- S3 完全访问
- SQS 完全访问 