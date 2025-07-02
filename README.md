# AWS IoT 架构自动化部署

基于提供的架构图实现的AWS IoT基础设施自动化部署脚本。

## 架构概览

该脚本实现了以下AWS服务的自动化部署：

- **用户层**: APP + AWS Shield防护
- **边缘层**: AWS IoT Greengrass边缘计算
- **IoT核心**: IoT Core、Device Shadow、IoT Rules
- **数据处理**: Lambda函数、TimeStream时序数据库
- **存储分析**: S3数据湖、EMR大数据处理、Airflow工作流
- **设备管理**: OTA空中更新、Edge Manager
- **AI/ML**: 机器学习模型集成支持

## 快速开始

### 前提条件

1. Python 3.7+
2. AWS CLI已配置
3. 必要的Python包：

```bash
pip install boto3
```

### 安装和运行

1. 克隆或下载项目文件

2. 运行部署脚本：

```bash
# 使用默认配置
python aws_iot_architecture_setup.py

# 指定区域和资源前缀
python aws_iot_architecture_setup.py --region us-west-2 --prefix my-iot

# 使用特定的AWS配置文件
python aws_iot_architecture_setup.py --profile my-aws-profile
```

### 参数说明

- `--region`: AWS区域（默认: us-east-1）
- `--prefix`: 资源命名前缀（默认: iot-demo）
- `--profile`: AWS配置文件名（可选）

## 项目结构

```
.
├── aws_iot_architecture_setup.py  # 主部署脚本
├── config/
│   └── iot_architecture_config.py # 配置文件
├── utils/
│   └── aws_helpers.py            # 辅助函数
└── README.md                     # 本文档
```

## 创建的资源

### IAM角色和策略
- IoT规则执行角色
- Lambda函数执行角色
- Greengrass服务角色

### 存储资源
- 数据湖S3桶（含生命周期策略）
- OTA更新S3桶
- Airflow DAGs S3桶

### IoT资源
- Thing类型定义
- 设备连接策略
- IoT规则（数据路由）
- 设备影子配置
- OTA作业模板

### 数据处理
- Lambda数据处理函数
- TimeStream数据库和表
- EMR集群配置（未实际创建）
- Airflow环境配置（未实际创建）

### 安全防护
- AWS Shield Standard（自动启用）
- S3桶加密
- IAM最小权限原则

## 配置自定义

修改 `config/iot_architecture_config.py` 文件来自定义：

- AWS服务配置
- 资源命名规则
- 存储生命周期
- 安全策略
- 成本优化选项

## 成本考虑

为控制成本，以下资源仅创建配置而未实际部署：
- EMR集群
- Airflow (MWAA)环境

需要时可根据生成的配置手动创建。

## 部署后步骤

1. **创建IoT设备**
   ```python
   # 使用提供的辅助函数创建设备
   from utils.aws_helpers import IoTDeviceHelper
   ```

2. **配置设备连接**
   - 下载设备证书
   - 配置MQTT端点
   - 测试设备连接

3. **部署Greengrass**
   - 在边缘设备上安装Greengrass
   - 部署边缘组件

4. **启动数据分析**（按需）
   - 启动EMR集群进行批处理
   - 部署Airflow进行工作流编排

5. **配置监控**
   - 设置CloudWatch告警
   - 配置日志聚合
   - 启用性能监控

## 故障排除

### 常见问题

1. **权限错误**
   - 确保AWS凭证具有足够权限
   - 检查IAM角色是否正确创建

2. **资源已存在**
   - 脚本会跳过已存在的资源
   - 可手动删除后重新运行

3. **区域不可用**
   - 某些服务可能在特定区域不可用
   - 切换到支持的区域

### 日志查看

脚本运行日志会显示在控制台，同时生成部署报告文件。

## 清理资源

要删除创建的资源，请在AWS控制台手动删除，或编写清理脚本。

**注意**: 删除资源前请确保：
- 备份重要数据
- 断开所有设备连接
- 清空S3桶内容

## 安全最佳实践

1. **定期轮换证书和密钥**
2. **启用MFA访问**
3. **使用VPC端点**
4. **加密传输和存储**
5. **实施最小权限原则**
6. **启用审计日志**

## 许可证

本项目仅供学习和参考使用。

## 贡献

欢迎提交问题和改进建议。