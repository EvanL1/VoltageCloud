#!/bin/bash

# EMS Backend API 测试脚本
# 用于测试后端API是否正常工作

API_BASE="http://localhost:3000"
API_V1="$API_BASE/api/v1"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试函数
test_endpoint() {
    local method=$1
    local endpoint=$2
    local name=$3
    local data=$4
    
    echo -n "测试 $name ($method $endpoint)... "
    
    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X $method "$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X $method "$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)
    
    if [[ $http_code =~ ^[2-3][0-9][0-9]$ ]]; then
        echo -e "${GREEN}✓ OK${NC} (HTTP $http_code)"
        if [ "$VERBOSE" = "true" ]; then
            echo "Response: $body" | jq . 2>/dev/null || echo "$body"
        fi
    else
        echo -e "${RED}✗ FAIL${NC} (HTTP $http_code)"
        echo "Error: $body"
    fi
    echo
}

# 主测试流程
echo "======================================"
echo "EMS Backend API 测试"
echo "======================================"
echo

# 1. 检查服务器是否运行
echo "1. 检查服务器状态"
echo "-------------------"
test_endpoint "GET" "$API_BASE/health" "健康检查"
test_endpoint "GET" "$API_BASE/api" "API信息"

# 2. 测试设备管理API（无认证）
echo -e "\n${YELLOW}注意：以下API需要认证，预期返回401错误${NC}"
echo "2. 设备管理 API 测试"
echo "-------------------"
test_endpoint "GET" "$API_V1/devices" "获取设备列表"
test_endpoint "GET" "$API_V1/devices/test-device-001" "获取设备详情"
test_endpoint "GET" "$API_V1/devices/stats" "获取设备统计"

# 3. 测试遥测数据API
echo "3. 遥测数据 API 测试"
echo "-------------------"
test_endpoint "GET" "$API_V1/telemetry/test-device-001?startTime=2025-01-01&endTime=2025-01-31" "获取设备遥测数据"
test_endpoint "GET" "$API_V1/telemetry/test-device-001/latest" "获取最新遥测数据"
test_endpoint "GET" "$API_V1/telemetry/test-device-001/stream" "获取数据流端点"

# 4. 测试能源管理API
echo "4. 能源管理 API 测试"
echo "-------------------"
test_endpoint "GET" "$API_V1/energy/consumption?startTime=2025-01-01&endTime=2025-01-31" "获取能源消耗"
test_endpoint "GET" "$API_V1/energy/efficiency" "获取能效分析"
test_endpoint "GET" "$API_V1/energy/cost" "获取成本分析"

echo "======================================"
echo "测试完成"
echo "======================================"
echo
echo "提示："
echo "1. 如果看到 401 错误，说明认证中间件正常工作"
echo "2. 要测试完整功能，需要先实现认证并获取JWT token"
echo "3. 使用 VERBOSE=true ./test-backend-api.sh 查看详细响应"
echo
echo "示例：使用认证token测试"
echo 'TOKEN="your-jwt-token"'
echo 'curl -H "Authorization: Bearer $TOKEN" http://localhost:3000/api/v1/devices'