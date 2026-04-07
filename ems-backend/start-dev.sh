#!/bin/bash

# EMS Backend 开发启动脚本

echo "🚀 启动 EMS 后端开发服务器..."

# 检查是否已安装依赖
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖..."
    npm install
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件，请先配置环境变量"
    echo "   可以复制 .env.example 作为模板："
    echo "   cp .env.example .env"
    exit 1
fi

# 检查 AWS 配置
echo "🔍 检查 AWS 配置..."
AWS_REGION=$(grep AWS_REGION .env | cut -d '=' -f2)
if [ -z "$AWS_REGION" ]; then
    echo "⚠️  请在 .env 中配置 AWS_REGION"
fi

# 获取 IoT 端点
echo "🔗 获取 AWS IoT 端点..."
IOT_ENDPOINT=$(aws iot describe-endpoint --endpoint-type iot:Data-ATS --query 'endpointAddress' --output text 2>/dev/null)
if [ ! -z "$IOT_ENDPOINT" ]; then
    echo "   IoT Endpoint: $IOT_ENDPOINT"
    echo "   请更新 .env 中的 AWS_IOT_ENDPOINT 配置"
fi

# 启动开发服务器
echo ""
echo "🌟 启动开发服务器..."
echo "   API地址: http://localhost:3000"
echo "   API文档: http://localhost:3000/api"
echo "   健康检查: http://localhost:3000/health"
echo ""

npm run dev