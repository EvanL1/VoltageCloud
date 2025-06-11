# IoT 平台测试指南

本文档详细说明如何运行和管理 IoT 平台的测试套件。

## 📋 测试概览

测试框架采用分层架构，包含以下测试类型：

### 测试分类

```
tests/
├── conftest.py              # 通用fixtures和配置
├── pytest.ini              # pytest配置
├── requirements-test.txt    # 测试依赖
├── test_runner.py          # 测试运行器
├── test_infrastructure.py  # CDK基础设施测试
├── test_lambda_functions.py # Lambda函数测试
├── test_api_endpoints.py   # API端点测试
├── test_glue_etl.py        # ETL管道测试
├── test_integration.py     # 集成测试
└── reports/                # 测试报告目录
```

### 测试类型说明

| 测试类型 | 描述 | 运行时间 | 依赖 |
|---------|------|---------|------|
| **单元测试** | 测试独立函数和类 | 快速 | 无外部依赖 |
| **集成测试** | 测试组件间交互 | 中等 | Mock AWS服务 |
| **端到端测试** | 测试完整工作流 | 较慢 | 完整环境 |
| **基础设施测试** | 测试CDK栈配置 | 快速 | CDK合成 |
| **API测试** | 测试REST端点 | 中等 | Mock服务 |
| **ETL测试** | 测试数据处理 | 中等 | 数据样本 |

## 🚀 快速开始

### 1. 安装测试依赖

```bash
# 安装测试依赖
pip install -r tests/requirements-test.txt

# 或使用主要的requirements.txt（包含测试依赖）
pip install -r requirements.txt
```

### 2. 运行基本测试

```bash
# 运行所有测试
python tests/test_runner.py all

# 运行特定类型的测试
python tests/test_runner.py unit
python tests/test_runner.py integration
python tests/test_runner.py infrastructure
```

### 3. 查看测试报告

```bash
# 生成详细测试报告
python tests/test_runner.py all --report

# 查看覆盖率报告
open tests/reports/full_coverage/index.html
```

## 🔧 详细测试命令

### 使用测试运行器

```bash
# 运行单元测试（快速）
python tests/test_runner.py unit -v

# 运行集成测试
python tests/test_runner.py integration -v

# 运行基础设施测试
python tests/test_runner.py infrastructure -v

# 运行Lambda函数测试
python tests/test_runner.py lambda -v

# 运行API端点测试
python tests/test_runner.py api -v

# 运行ETL管道测试
python tests/test_runner.py etl -v

# 运行性能测试
python tests/test_runner.py performance -v

# 运行Rust Lambda测试
python tests/test_runner.py rust -v

# 并行运行所有测试（更快）
python tests/test_runner.py all -p
```

### 使用 Shell 脚本运行

```bash
# 基本运行
./run_tests.sh all

# 运行特定测试类型
./run_tests.sh unit -v
./run_tests.sh integration --coverage
./run_tests.sh infrastructure -p

# 生成覆盖率报告
./run_tests.sh all --coverage

# 并行运行所有测试
./run_tests.sh all -p -r
```

### 使用 Makefile

```bash
# 安装依赖
make install

# 运行测试
make test                    # 运行所有测试
make test-unit              # 运行单元测试
make test-integration       # 运行集成测试
make test-infrastructure    # 运行基础设施测试

# 生成覆盖率报告
make coverage

# 代码质量检查
make lint                   # 运行代码检查
make format                 # 格式化代码

# CI/CD 模拟
make ci                     # 模拟完整CI流水线
```

### 使用 pytest 直接运行

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_infrastructure.py -v

# 运行特定测试类
pytest tests/test_lambda_functions.py::TestRustLambdaHandler -v

# 运行特定测试方法
pytest tests/test_infrastructure.py::TestIotPocStack::test_sqs_queue_creation -v

# 使用标记运行测试
pytest tests/ -m "unit" -v
pytest tests/ -m "integration" -v
pytest tests/ -m "slow" -v

# 生成覆盖率报告
pytest tests/ --cov=iot_poc --cov-report=html

# 并行运行测试
pytest tests/ -n auto
```

## 📊 测试标记 (Markers)

使用 pytest 标记来分类和筛选测试：

```python
import pytest

@pytest.mark.unit
def test_unit_function():
    """单元测试"""
    pass

@pytest.mark.integration
def test_integration_workflow():
    """集成测试"""
    pass

@pytest.mark.e2e
def test_end_to_end_flow():
    """端到端测试"""
    pass

@pytest.mark.slow
def test_performance_benchmark():
    """性能测试"""
    pass

@pytest.mark.aws
def test_aws_service():
    """需要AWS服务的测试"""
    pass
```

### 按标记运行测试

```bash
# 只运行单元测试
pytest -m "unit"

# 只运行集成测试
pytest -m "integration"

# 跳过慢速测试
pytest -m "not slow"

# 运行AWS相关测试
pytest -m "aws"

# 组合标记
pytest -m "unit or integration"
pytest -m "aws and not slow"
```

## 🧪 测试配置

### pytest.ini 配置

```ini
[tool.pytest.ini_options]
minversion = "6.0"
addopts = [
    "-ra",
    "--strict-markers",
    "--strict-config",
    "--cov=iot_poc",
    "--cov-report=term-missing",
    "--cov-report=html:tests/htmlcov",
    "-v"
]
testpaths = ["tests"]
markers = [
    "unit: 单元测试",
    "integration: 集成测试",
    "e2e: 端到端测试",
    "slow: 慢速测试",
    "aws: AWS服务测试",
    "rust: Rust代码测试"
]
```

## 📈 覆盖率报告

### 生成覆盖率报告

```bash
# 生成HTML覆盖率报告
pytest --cov=iot_poc --cov=lambda --cov-report=html:tests/reports/coverage

# 生成终端覆盖率报告
pytest --cov=iot_poc --cov-report=term-missing

# 生成XML覆盖率报告（用于CI/CD）
pytest --cov=iot_poc --cov-report=xml:tests/reports/coverage.xml
```

### 覆盖率阈值

项目要求的最低覆盖率：
- **总体覆盖率**: ≥ 85%
- **单个文件**: ≥ 80%
- **核心模块**: ≥ 90%

## 🔍 调试测试

### 调试失败的测试

```bash
# 详细输出模式
pytest tests/test_lambda_functions.py -v -s

# 在第一个失败时停止
pytest tests/ -x

# 只运行失败的测试
pytest tests/ --lf

# 运行最后失败的测试，然后运行其他测试
pytest tests/ --ff

# 显示最慢的10个测试
pytest tests/ --durations=10
```

### 使用 pdb 调试

```bash
# 在失败时进入调试器
pytest tests/ --pdb

# 在测试开始时进入调试器
pytest tests/ --pdb-trace
```

### 日志输出

```bash
# 显示日志输出
pytest tests/ -s --log-cli-level=INFO

# 显示特定级别的日志
pytest tests/ --log-cli-level=DEBUG
```

## 🚢 CI/CD 集成

### GitHub Actions 集成

项目已配置 GitHub Actions，包括：

```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r tests/requirements-test.txt
      - name: Run tests
        run: ./run_tests.sh all --coverage
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### 本地 CI 模拟

```bash
# 运行完整CI流水线
make ci

# 或手动执行步骤
make install
make lint
make test
make coverage
```

## 🏗️ 测试架构详解

### 1. 基础设施测试 (test_infrastructure.py)

测试 CDK Stack 的正确性：

```python
def test_sqs_queue_creation(self, cdk_app):
    """测试SQS队列创建"""
    stack = IotPocStack(cdk_app, "TestIotPocStack")
    template = Template.from_stack(stack)
    
    template.has_resource_properties("AWS::SQS::Queue", {
        "MessageRetentionPeriod": 1209600,
        "VisibilityTimeoutSeconds": 300
    })
```

**覆盖的组件：**
- SQS 队列和 DLQ
- Lambda 函数
- TimeStream 数据库和表
- S3 存储桶
- DynamoDB 表
- API Gateway
- Cognito 用户池
- ECS 集群和服务
- Step Functions 工作流

### 2. Lambda 函数测试 (test_lambda_functions.py)

测试 Python 和 Rust Lambda 函数：

```python
@pytest.mark.unit
def test_rust_device_id_extraction(self):
    """测试Rust Lambda设备ID提取"""
    # 测试主题解析
    payload = {"source_topic": "devices/sensor001/data"}
    device_id = extract_device_id(payload)
    assert device_id == "sensor001"
```

**覆盖的功能：**
- SQS 消息处理
- TimeStream 数据写入
- S3 数据存储
- 设备影子管理
- 认证授权
- OTA 更新管理
- 数据湖查询

### 3. API 端点测试 (test_api_endpoints.py)

测试 REST API 端点：

```python
@pytest.mark.integration
async def test_device_data_retrieval(self):
    """测试设备数据获取API"""
    response = await self.api_client.get(
        "/api/devices/device001/data",
        params={"start_date": "2024-01-01", "limit": 100}
    )
    assert response.status_code == 200
```

**覆盖的端点：**
- 设备管理
- 数据查询
- 用户认证
- OTA 管理
- 分析报表

### 4. ETL 管道测试 (test_glue_etl.py)

测试数据处理管道：

```python
@pytest.mark.slow
def test_data_aggregation_pipeline(self):
    """测试数据聚合管道"""
    # 创建测试数据
    test_data = self.create_sample_data()
    
    # 运行ETL作业
    result = self.etl_processor.aggregate_hourly_data(test_data)
    
    # 验证结果
    assert len(result) > 0
    assert "avg_temperature" in result.columns
```

**覆盖的流程：**
- 数据清洗
- 数据聚合
- 分区策略
- 数据质量检查
- 性能优化

### 5. 集成测试 (test_integration.py)

测试端到端工作流：

```python
@pytest.mark.e2e
async def test_complete_device_onboarding_flow(self):
    """测试完整设备接入流程"""
    # 1. 设备注册
    device = await self.register_device("test-device-001")
    
    # 2. 发送数据
    await self.send_device_data(device.id, sample_data)
    
    # 3. 验证数据存储
    stored_data = await self.query_device_data(device.id)
    assert len(stored_data) > 0
    
    # 4. 验证分析结果
    analytics = await self.get_device_analytics(device.id)
    assert analytics.avg_temperature > 0
```

**测试流程：**
- 设备注册和认证
- 数据采集和处理
- 实时分析
- OTA 更新
- 告警和通知

## 🎯 测试最佳实践

### 1. 测试命名规范

```python
# ✅ 好的测试名称
def test_device_registration_with_valid_credentials():
    """使用有效凭据测试设备注册"""
    pass

def test_data_processing_handles_invalid_timestamp():
    """测试数据处理如何处理无效时间戳"""
    pass

# ❌ 不好的测试名称
def test_1():
    pass

def test_device():
    pass
```

### 2. 使用 Fixtures

```python
@pytest.fixture
def sample_device_data():
    """创建示例设备数据"""
    return {
        "device_id": "test-device-001",
        "timestamp": 1640995200,
        "temperature": 23.5,
        "humidity": 65.2
    }

def test_data_validation(sample_device_data):
    """测试数据验证"""
    result = validate_device_data(sample_device_data)
    assert result.is_valid
```

### 3. Mock 外部依赖

```python
@mock_s3
def test_s3_data_storage():
    """测试S3数据存储"""
    s3_client = boto3.client('s3', region_name='us-east-1')
    s3_client.create_bucket(Bucket='test-bucket')
    
    # 测试代码
    result = upload_to_s3(data, 'test-bucket', 'test-key')
    assert result.success
```

### 4. 测试错误处理

```python
def test_invalid_device_id_raises_error():
    """测试无效设备ID引发错误"""
    with pytest.raises(ValueError, match="Invalid device ID"):
        process_device_data({"device_id": ""})
```

### 5. 参数化测试

```python
@pytest.mark.parametrize("temperature,expected", [
    (-10, "cold"),
    (25, "normal"),
    (40, "hot")
])
def test_temperature_classification(temperature, expected):
    """测试温度分类"""
    result = classify_temperature(temperature)
    assert result == expected
```

## 📋 故障排除

### 常见问题

1. **ImportError: No module named 'moto'**
   ```bash
   pip install -r tests/requirements-test.txt
   ```

2. **AWS 凭据错误**
   ```bash
   export AWS_ACCESS_KEY_ID=testing
   export AWS_SECRET_ACCESS_KEY=testing
   export AWS_DEFAULT_REGION=us-east-1
   ```

3. **Rust 测试失败**
   ```bash
   cd rust-lambda
   cargo test
   ```

4. **CDK 合成失败**
   ```bash
   npm install -g aws-cdk
   cdk synth
   ```

### 性能优化

1. **并行运行测试**
   ```bash
   pytest -n auto  # 使用所有CPU核心
   pytest -n 4     # 使用4个进程
   ```

2. **跳过慢速测试**
   ```bash
   pytest -m "not slow"
   ```

3. **只运行失败的测试**
   ```bash
   pytest --lf
   ```

## 📊 测试报告分析

### 生成详细报告

```bash
# 生成完整测试报告
python tests/test_runner.py all --report

# 查看报告
cat tests/reports/test_report.json
```

### 报告包含内容

- 测试执行时间
- 覆盖率统计
- 失败测试详情
- 性能基准
- 资源使用情况

## 🔄 持续改进

### 定期任务

1. **每周**：检查测试覆盖率
2. **每月**：更新测试依赖
3. **每季度**：评估测试策略

### 监控指标

- 测试通过率：> 95%
- 测试执行时间：< 10分钟
- 代码覆盖率：> 85%
- 失败率趋势：下降

---

## 📞 支持

如遇到测试相关问题，请：

1. 查看本文档
2. 检查测试日志
3. 联系开发团队

**Happy Testing! 🎉** 