# 🧪 IoT 平台测试框架完整指南

## 📋 概览

这是一个为IoT平台设计的全面测试框架，包含单元测试、集成测试、性能测试、安全测试和监控测试。

## 🏗️ 测试架构

```
测试框架架构
├── 🧪 单元测试 (Unit Tests)
│   ├── Lambda函数测试
│   ├── CDK基础设施测试
│   └── 业务逻辑测试
├── 🔗 集成测试 (Integration Tests)
│   ├── AWS服务集成
│   ├── 数据流测试
│   └── API端点测试
├── ⚡ 性能测试 (Performance Tests)
│   ├── 负载测试
│   ├── 压力测试
│   └── 基准测试
├── 📈 监控测试 (Monitoring Tests)
│   ├── 日志记录测试
│   ├── 指标收集测试
│   └── 告警测试
├── 🔒 安全测试 (Security Tests)
│   ├── 漏洞扫描
│   ├── 代码安全检查
│   └── 依赖安全检查
└── 🏃 端到端测试 (E2E Tests)
    ├── 完整工作流测试
    ├── 用户场景测试
    └── 数据管道测试
```

## 🚀 快速开始

### 1. 基本用法

```bash
# 运行所有测试
python run_all_tests.py

# 运行特定测试套件
python run_all_tests.py unit integration

# 运行快速测试
python run_all_tests.py --fast

# 运行关键测试
python run_all_tests.py --critical

# 并行运行测试
python run_all_tests.py --parallel
```

### 2. 使用传统测试运行器

```bash
# 运行单元测试
python tests/test_runner.py unit

# 运行集成测试
python tests/test_runner.py integration

# 运行性能测试
python tests/test_runner.py performance

# 生成测试报告
python tests/test_runner.py all --report
```

### 3. 使用Make命令

```bash
# 安装依赖
make install

# 运行所有测试
make test

# 运行单元测试
make test-unit

# 运行集成测试
make test-integration

# 生成覆盖率报告
make coverage

# 代码质量检查
make lint

# 格式化代码
make format
```

## 📊 测试类型详解

### 🧪 单元测试

测试独立的函数和类，不依赖外部服务。

```bash
# 运行单元测试
pytest tests/test_lambda_functions.py -m unit

# 运行特定模块的单元测试
pytest tests/test_lambda_functions.py::TestSQSProcessor -v
```

**覆盖范围：**
- Lambda函数逻辑
- 数据处理算法
- 工具函数
- 错误处理

### 🔗 集成测试

测试组件间的交互，使用模拟的AWS服务。

```bash
# 运行集成测试
pytest tests/test_integration.py -m integration

# 运行AWS服务集成测试
pytest tests/test_integration.py::TestAWSIntegration -v
```

**覆盖范围：**
- AWS服务交互
- 数据库操作
- 消息队列处理
- API网关集成

### 🏗️ 基础设施测试

测试CDK基础设施配置的正确性。

```bash
# 运行基础设施测试
pytest tests/test_infrastructure.py

# 测试特定栈
pytest tests/test_infrastructure.py::TestIotPocStack -v
```

**覆盖范围：**
- CDK栈配置
- 资源创建
- 权限配置
- 网络设置

### ⚡ 性能测试

测试系统在不同负载下的表现。

```bash
# 运行性能测试
pytest tests/test_performance.py -m benchmark

# 运行负载测试
pytest tests/test_performance.py -m load

# 运行压力测试
pytest tests/test_performance.py -m stress
```

**测试场景：**
- 高并发处理
- 大数据量处理
- 内存使用优化
- 响应时间测试

### 📈 监控测试

测试日志、指标和告警功能。

```bash
# 运行监控测试
pytest tests/test_monitoring.py

# 测试告警功能
pytest tests/test_monitoring.py::TestAlertingAndNotifications -v
```

**覆盖范围：**
- 结构化日志
- 自定义指标
- 健康检查
- 告警配置

## 📄 测试报告

### 自动生成的报告

测试运行后会自动生成多种格式的报告：

1. **HTML报告**: `tests/reports/test_report.html`
2. **JSON摘要**: `tests/reports/test_summary.json`
3. **覆盖率报告**: `tests/reports/coverage_html/index.html`
4. **性能报告**: `tests/reports/benchmark.json`

### 查看报告

```bash
# 生成并打开HTML报告
python run_all_tests.py --open-report

# 手动生成测试摘要
python tests/test_summary_generator.py --html --console

# 在浏览器中查看覆盖率报告
open tests/reports/coverage_html/index.html
```

## 🎯 测试标记 (Markers)

使用pytest标记来分类和过滤测试：

```bash
# 运行快速测试
pytest -m "not slow"

# 运行AWS相关测试
pytest -m aws

# 运行端到端测试
pytest -m e2e

# 运行基准测试
pytest -m benchmark

# 运行关键路径测试
pytest -m critical
```

**可用标记：**
- `unit`: 单元测试
- `integration`: 集成测试
- `e2e`: 端到端测试
- `slow`: 耗时测试
- `fast`: 快速测试
- `aws`: AWS服务相关
- `benchmark`: 性能基准测试
- `critical`: 关键路径测试

## 🔧 配置选项

### 环境变量

```bash
# AWS测试环境
export AWS_ACCESS_KEY_ID=testing
export AWS_SECRET_ACCESS_KEY=testing
export AWS_DEFAULT_REGION=us-east-1

# 测试配置
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export IOT_TEST_MODE=true
```

### pytest配置文件

编辑 `tests/pytest.ini` 来自定义测试行为：

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --disable-warnings
    --tb=short
    -ra
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
    fast: Fast running tests
    aws: AWS service tests
    benchmark: Performance benchmarks
    critical: Critical path tests
```

## 🚦 CI/CD 集成

### GitHub Actions

项目包含完整的GitHub Actions工作流 (`.github/workflows/test.yml`)，支持：

- 多Python版本测试
- 并行测试执行
- 自动报告生成
- 覆盖率上传
- 安全扫描
- 性能基准测试

### 本地CI模拟

```bash
# 模拟CI环境运行
make ci

# 完整的代码质量检查
make quality-check

# 安全扫描
make security-scan
```

## 🏃‍♂️ 常用命令速查

### 开发阶段

```bash
# 快速单元测试
make test-unit

# 监控代码质量
make lint format

# 本地集成测试
pytest tests/test_integration.py -v
```

### 部署前检查

```bash
# 完整测试套件
python run_all_tests.py --critical

# 性能基准测试
python run_all_tests.py performance --parallel

# 生成完整报告
python run_all_tests.py --open-report
```

### 调试测试

```bash
# 详细输出运行失败的测试
pytest tests/ -vvv --tb=long --failed-first

# 运行到第一个失败就停止
pytest tests/ -x

# 运行特定的失败测试
pytest tests/test_lambda_functions.py::test_specific_function -s
```

## 🔍 故障排除

### 常见问题

1. **AWS凭证错误**
   ```bash
   # 设置测试环境变量
   export AWS_ACCESS_KEY_ID=testing
   export AWS_SECRET_ACCESS_KEY=testing
   ```

2. **依赖缺失**
   ```bash
   # 重新安装测试依赖
   pip install -r tests/requirements-test.txt
   ```

3. **端口冲突**
   ```bash
   # 检查占用的端口
   lsof -i :8000
   ```

4. **权限问题**
   ```bash
   # 确保脚本可执行
   chmod +x run_all_tests.py
   chmod +x tests/test_summary_generator.py
   ```

### 调试技巧

```python
# 在测试中添加调试点
import pytest

def test_with_debug():
    # 这会在测试失败时启动调试器
    pytest.set_trace()
    
    # 或者使用标准调试器
    import pdb; pdb.set_trace()
```

## 📈 最佳实践

### 编写测试

1. **遵循AAA模式**: Arrange, Act, Assert
2. **使用描述性的测试名称**
3. **保持测试独立性**
4. **使用fixtures共享测试数据**
5. **添加适当的测试标记**

### 性能考虑

1. **使用并行测试**: `--parallel`
2. **分离快速和慢速测试**: 使用 `fast` 和 `slow` 标记
3. **优化测试数据**: 使用最小必要的测试数据
4. **缓存重复操作**: 使用session级别的fixtures

### 维护测试

1. **定期更新测试依赖**
2. **清理过时的测试**
3. **监控测试覆盖率**
4. **审查测试报告**

## 🎖️ 测试覆盖率目标

- **整体覆盖率**: ≥ 80%
- **关键路径覆盖率**: ≥ 95%
- **Lambda函数覆盖率**: ≥ 90%
- **CDK基础设施**: 100%

## 📚 相关文档

- [README.md](README.md) - 项目概览
- [DATA_LAKE_ACCESS_GUIDE.md](DATA_LAKE_ACCESS_GUIDE.md) - 数据湖访问指南
- [IOT_PLATFORM_ARCHITECTURE.md](IOT_PLATFORM_ARCHITECTURE.md) - 架构文档
- [tests/README.md](tests/README.md) - 测试详细说明

---

**Happy Testing! 🧪✨** 