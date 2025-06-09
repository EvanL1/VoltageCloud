#!/bin/bash
# IoT PoC 项目初始设置脚本

set -e

echo "🚀 IoT PoC 项目初始设置"
echo "======================="

# 检查必要工具
echo "🔍 检查必要工具..."

# 检查 Python
if ! command -v python3 > /dev/null; then
    echo "❌ Python 3 未安装"
    exit 1
fi
echo "✅ Python 3: $(python3 --version)"

# 检查 pip
if ! command -v pip > /dev/null; then
    echo "❌ pip 未安装"
    exit 1
fi
echo "✅ pip: $(pip --version)"

# 检查 Node.js (CDK需要)
if ! command -v node > /dev/null; then
    echo "⚠️  Node.js 未安装，正在安装 CDK..."
    echo "请先安装 Node.js: https://nodejs.org/"
    exit 1
fi
echo "✅ Node.js: $(node --version)"

# 检查 AWS CLI
if ! command -v aws > /dev/null; then
    echo "⚠️  AWS CLI 未安装，正在安装..."
    if command -v brew > /dev/null; then
        brew install awscli
    else
        echo "请手动安装 AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        exit 1
    fi
fi
echo "✅ AWS CLI: $(aws --version)"

# 检查 jq
if ! command -v jq > /dev/null; then
    echo "⚠️  jq 未安装，正在安装..."
    if command -v brew > /dev/null; then
        brew install jq
    elif command -v apt-get > /dev/null; then
        sudo apt-get update && sudo apt-get install -y jq
    else
        echo "请手动安装 jq: https://stedolan.github.io/jq/download/"
        exit 1
    fi
fi
echo "✅ jq: $(jq --version)"

# 创建 Python 虚拟环境
echo ""
echo "📦 设置 Python 虚拟环境..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ 虚拟环境已创建"
else
    echo "✅ 虚拟环境已存在"
fi

# 激活虚拟环境并安装依赖
echo "📦 安装 Python 依赖..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 安装 CDK CLI (全局)
echo ""
echo "📦 安装 AWS CDK CLI..."
if ! command -v cdk > /dev/null; then
    npm install -g aws-cdk
    echo "✅ CDK CLI 已安装"
else
    echo "✅ CDK CLI 已存在: $(cdk --version)"
fi

# 检查 AWS 配置
echo ""
echo "🔐 检查 AWS 配置..."
if aws sts get-caller-identity > /dev/null 2>&1; then
    echo "✅ AWS 凭证已配置"
    aws sts get-caller-identity --output table
else
    echo "❌ AWS 凭证未配置"
    echo "请运行: aws configure"
    echo "或设置环境变量: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
    exit 1
fi

echo ""
echo "🎉 项目设置完成！"
echo ""
echo "📋 下一步操作："
echo "1. 激活虚拟环境: source .venv/bin/activate"
echo "2. 部署基础设施: ./scripts/deploy.sh"
echo "3. 测试 MQTT 连接: ./scripts/test-mqtt.sh"
echo "4. 查询数据: ./scripts/query-timestream.sh"
echo "5. 清理资源: ./scripts/cleanup.sh"
echo ""
echo "更多信息请查看 README.md"
