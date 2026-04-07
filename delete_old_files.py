#!/usr/bin/env python3
import os
import sys

# 定义要删除的文件列表
files_to_delete = [
    # 旧的部署报告和配置
    "monarch-iot-demo_deployment_report.txt",
    "monarch-iot-demo_device_config.json",
    "iot-demo_deployment_report_20250702_103117.md",
    
    # 过时的测试和临时脚本
    "limited_iot_setup.py",
    "fixed_lambda_function.py",
    "lambda_function.zip",
    "check_permissions.py",
    "check_role_permissions.py",
    "test_aws_connection.py",
    "create_test_device.py",
    "run_device_locally.py",
    
    # 过时的文档
    "README_DETAILED.md",
    "PROJECT_SUMMARY.md",
    "DEVICE_AUTO_REGISTRATION_GUIDE.md",
    
    # EMS相关的测试脚本
    "ems-backend/test-aws-connection.ts",
    "ems-backend/test-backend-api.sh"
]

# 删除文件
deleted_count = 0
for file_path in files_to_delete:
    full_path = os.path.join("/Users/lyf/dev/cloud", file_path)
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
            print(f"✓ 删除成功: {file_path}")
            deleted_count += 1
        except Exception as e:
            print(f"✗ 删除失败: {file_path} - {str(e)}")
    else:
        print(f"- 文件不存在: {file_path}")

print(f"\n总计: 成功删除 {deleted_count} 个文件")