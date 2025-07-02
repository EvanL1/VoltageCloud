#!/bin/bash
# 使用 uv 环境部署 AWS IoT 架构

echo "AWS IoT 架构部署脚本 (使用 uv 环境)"
echo "================================="

# 检查是否已创建虚拟环境
if [ ! -d ".venv" ]; then
    echo "创建 uv 虚拟环境..."
    uv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source .venv/bin/activate

# 检查并安装依赖
echo "检查依赖..."
if ! python -c "import boto3" 2>/dev/null; then
    echo "安装 boto3..."
    uv pip install boto3
fi

# 测试 AWS 连接
echo -e "\n测试 AWS 连接..."
python test_aws_connection.py $1

# 如果连接成功，询问是否继续部署
if [ $? -eq 0 ]; then
    echo -e "\nAWS 连接成功！"
    read -p "是否继续部署 IoT 架构？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "\n开始部署..."
        if [ -n "$1" ]; then
            python aws_iot_architecture_setup.py --profile "$1" "${@:2}"
        else
            python aws_iot_architecture_setup.py "${@}"
        fi
    else
        echo "部署已取消。"
    fi
else
    echo -e "\nAWS 连接失败。请先配置 AWS 认证："
    echo "1. 使用 SSO: aws sso login --profile MonarchCloud"
    echo "2. 使用环境变量:"
    echo "   export AWS_ACCESS_KEY_ID=your-key"
    echo "   export AWS_SECRET_ACCESS_KEY=your-secret"
    echo "3. 使用 aws configure 配置默认凭证"
fi