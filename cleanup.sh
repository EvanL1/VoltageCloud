#!/bin/bash

# 删除旧的部署报告和配置文件
echo "正在删除旧的部署报告和配置文件..."
rm -f monarch-iot-demo_deployment_report.txt
rm -f monarch-iot-demo_device_config.json
rm -f iot-demo_deployment_report_20250702_103117.md

# 删除过时的测试和临时脚本
echo "正在删除过时的测试和临时脚本..."
rm -f limited_iot_setup.py
rm -f fixed_lambda_function.py
rm -f lambda_function.zip
rm -f check_permissions.py
rm -f check_role_permissions.py
rm -f test_aws_connection.py
rm -f create_test_device.py
rm -f run_device_locally.py

# 删除过时的文档
echo "正在删除过时的文档..."
rm -f README_DETAILED.md
rm -f PROJECT_SUMMARY.md
rm -f DEVICE_AUTO_REGISTRATION_GUIDE.md

# 删除EMS相关的测试脚本
echo "正在删除EMS相关的测试脚本..."
rm -f ems-backend/test-aws-connection.ts
rm -f ems-backend/test-backend-api.sh

# 删除临时创建的Python脚本
rm -f delete_old_files.py

echo "清理完成！"