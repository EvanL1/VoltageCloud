#!/bin/bash
# EMS 开发环境启动脚本

echo "🚀 启动能源管理系统开发环境..."
echo "================================"

# 创建必要的目录
mkdir -p ems-vue-frontend/src/{api,components,views,stores,utils,router,types,styles}
mkdir -p ems-backend/src/{controllers,services,models,middleware,routes,utils,config}
mkdir -p ems-grafana/{provisioning,dashboards}
mkdir -p prometheus

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未运行，请先启动 Docker Desktop"
    exit 1
fi

# 启动选项
if [ "$1" = "full" ]; then
    echo "📦 启动完整环境（包括所有服务）..."
    docker-compose -f ems-docker-compose.yml up -d
    echo "✅ 所有服务已启动"
    echo ""
    echo "🌐 访问地址："
    echo "   Vue 开发界面: http://localhost:9000"
    echo "   Grafana: http://localhost:3001 (admin/admin123)"
    echo "   后端 API: http://localhost:3000"
    echo "   Prometheus: http://localhost:9090"
    echo "   InfluxDB: http://localhost:8086"
elif [ "$1" = "frontend" ]; then
    echo "🎨 仅启动前端开发环境..."
    cd ems-vue-frontend
    npm install
    npm run dev
elif [ "$1" = "backend" ]; then
    echo "⚙️ 仅启动后端开发环境..."
    cd ems-backend
    npm install
    npm run dev
else
    echo "📱 启动前端开发服务器（端口 9000）..."
    cd ems-vue-frontend
    
    # 检查是否需要安装依赖
    if [ ! -d "node_modules" ]; then
        echo "📦 安装前端依赖..."
        npm install
    fi
    
    # 启动开发服务器
    echo "🔧 启动 Vue 开发服务器..."
    npm run dev &
    FRONTEND_PID=$!
    
    # 同时启动后端服务（如果需要）
    if [ "$2" = "with-backend" ]; then
        cd ../ems-backend
        if [ ! -d "node_modules" ]; then
            echo "📦 安装后端依赖..."
            npm install
        fi
        echo "🔧 启动后端 API 服务器..."
        npm run dev &
        BACKEND_PID=$!
        
        echo ""
        echo "✅ 开发环境已启动："
        echo "   前端: http://localhost:9000"
        echo "   后端: http://localhost:3000"
        echo ""
        echo "按 Ctrl+C 停止所有服务"
        
        # 等待进程
        wait $FRONTEND_PID $BACKEND_PID
    else
        echo ""
        echo "✅ Vue 开发服务器已启动："
        echo "   访问地址: http://localhost:9000"
        echo ""
        echo "提示: 使用 './ems-dev.sh with-backend' 同时启动后端"
        echo "      使用 './ems-dev.sh full' 启动完整环境"
        echo ""
        echo "按 Ctrl+C 停止服务"
        
        wait $FRONTEND_PID
    fi
fi