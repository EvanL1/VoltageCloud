#!/usr/bin/env python3
"""
环境变量配置检查脚本
检查 IoT PoC 项目运行所需的环境变量配置
"""

import os
import sys
import boto3
from typing import List, Tuple, Dict
import subprocess
import json

def check_required_vars() -> List[Tuple[str, bool, str, str]]:
    """检查必需的环境变量"""
    required_vars = [
        ('AWS_REGION', 'AWS 区域', 'us-east-1'),
        ('ENVIRONMENT', '环境名称', 'testing'),
    ]
    
    results = []
    for var, desc, default in required_vars:
        value = os.environ.get(var)
        results.append((var, bool(value), desc, value or f"建议设置为: {default}"))
    
    return results

def check_aws_credentials() -> Tuple[bool, Dict[str, str]]:
    """检查 AWS 凭证"""
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        return True, {
            'account': identity['Account'],
            'user_id': identity.get('UserId', 'N/A'),
            'arn': identity['Arn']
        }
    except Exception as e:
        return False, {'error': str(e)}

def check_recommended_vars() -> List[Tuple[str, str, str]]:
    """检查推荐的环境变量"""
    recommended_vars = [
        ('LAMBDA_MEMORY_MB', '512'),
        ('ENABLE_DETAILED_MONITORING', 'true'),
        ('PYTEST_TIMEOUT', '300'),
        ('TEST_COVERAGE_THRESHOLD', '80'),
        ('STACK_NAME', 'IotPocStack'),
        ('PROJECT_NAME', 'IoT-PoC'),
    ]
    
    results = []
    for var, default in recommended_vars:
        value = os.environ.get(var, "未设置")
        suggestion = f"建议设置为: {default}" if value == "未设置" else ""
        results.append((var, value, suggestion))
    
    return results

def check_optional_vars() -> List[Tuple[str, str, str]]:
    """检查可选的环境变量"""
    optional_vars = [
        ('ALERT_EMAIL', 'admin@company.com'),
        ('SLACK_WEBHOOK_URL', 'https://hooks.slack.com/...'),
        ('ENABLE_X_RAY_TRACING', 'true'),
        ('PYTEST_WORKERS', '4'),
        ('AWS_ACCOUNT_ID', '从 AWS CLI 自动获取'),
    ]
    
    results = []
    for var, example in optional_vars:
        value = os.environ.get(var, "未设置")
        suggestion = f"示例: {example}" if value == "未设置" else ""
        results.append((var, value, suggestion))
    
    return results

def check_conda_environment() -> Tuple[bool, str]:
    """检查 conda 环境"""
    try:
        # 检查是否在 conda 环境中
        conda_env = os.environ.get('CONDA_DEFAULT_ENV')
        if conda_env:
            return True, conda_env
        
        # 检查 conda 是否可用
        result = subprocess.run(['conda', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            return True, "conda 可用，但未激活环境"
        else:
            return False, "conda 不可用"
    except Exception:
        return False, "conda 不可用"

def check_python_packages() -> List[Tuple[str, bool, str]]:
    """检查关键 Python 包"""
    packages = [
        'boto3',
        'pytest',
        'pytest-cov',
        'aws-cdk-lib',
        'moto'
    ]
    
    results = []
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
            results.append((package, True, "已安装"))
        except ImportError:
            results.append((package, False, "未安装"))
    
    return results

def get_aws_account_id() -> str:
    """获取当前 AWS 账户 ID"""
    try:
        sts = boto3.client('sts')
        return sts.get_caller_identity()['Account']
    except Exception:
        return "无法获取"

def generate_env_template():
    """生成环境变量模板文件"""
    account_id = get_aws_account_id()
    
    template = f"""# IoT PoC 测试环境变量配置模板
# 复制此文件为 .env.testing 并修改相应值

# === AWS 基础配置 ===
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID={account_id}

# === 项目配置 ===
export ENVIRONMENT=testing
export STACK_NAME=IotPocStack-Test
export PROJECT_NAME=IoT-PoC

# === 测试配置 ===
export ENABLE_INTEGRATION_TESTS=true
export TEST_COVERAGE_THRESHOLD=80
export PYTEST_TIMEOUT=600
export PYTEST_WORKERS=4

# === Lambda 配置 ===
export LAMBDA_MEMORY_MB=512
export LAMBDA_TIMEOUT_SECONDS=60

# === 监控配置 ===
export ENABLE_DETAILED_MONITORING=true
export ENABLE_X_RAY_TRACING=true

# === 安全配置 ===
export ENABLE_ENCRYPTION_AT_REST=true
export ENABLE_ENCRYPTION_IN_TRANSIT=true

# === 通知配置（可选）===
# export ALERT_EMAIL=your-email@company.com
# export SLACK_WEBHOOK_URL=your-slack-webhook

# === 加载此配置的命令 ===
# source .env.testing
# 或者
# export $(cat .env.testing | grep -v '^#' | xargs)
"""
    
    with open('.env.template', 'w') as f:
        f.write(template)
    
    return '.env.template'

def main():
    print("🔍 IoT PoC 环境变量配置检查")
    print("=" * 60)
    
    # 检查必需变量
    print("\n📋 必需的环境变量:")
    required_results = check_required_vars()
    required_missing = []
    
    for var, exists, desc, info in required_results:
        status = "✅" if exists else "❌"
        print(f"  {status} {var}: {desc}")
        if exists:
            value = os.environ.get(var)
            print(f"     当前值: {value}")
        else:
            print(f"     {info}")
            required_missing.append(var)
    
    # 检查 AWS 凭证
    print("\n🔐 AWS 凭证检查:")
    aws_ok, aws_info = check_aws_credentials()
    if aws_ok:
        print("  ✅ AWS 凭证配置正确")
        print(f"     账户: {aws_info['account']}")
        print(f"     ARN: {aws_info['arn']}")
    else:
        print("  ❌ AWS 凭证配置错误")
        print(f"     错误: {aws_info['error']}")
    
    # 检查 conda 环境
    print("\n🐍 Conda 环境检查:")
    conda_ok, conda_info = check_conda_environment()
    if conda_ok:
        print(f"  ✅ {conda_info}")
        if 'iot-testing' in conda_info:
            print("     推荐的测试环境已激活")
        else:
            print("     建议激活 iot-testing 环境: conda activate iot-testing")
    else:
        print(f"  ⚠️  {conda_info}")
        print("     建议安装 conda 并创建测试环境")
    
    # 检查 Python 包
    print("\n📦 关键 Python 包检查:")
    package_results = check_python_packages()
    missing_packages = []
    
    for package, installed, status in package_results:
        icon = "✅" if installed else "❌"
        print(f"  {icon} {package}: {status}")
        if not installed:
            missing_packages.append(package)
    
    # 检查推荐变量
    print("\n🎯 推荐的环境变量:")
    recommended_results = check_recommended_vars()
    
    for var, value, suggestion in recommended_results:
        status = "✅" if value != "未设置" else "⚠️"
        print(f"  {status} {var}: {value}")
        if suggestion:
            print(f"     {suggestion}")
    
    # 检查可选变量
    print("\n🔧 可选的环境变量:")
    optional_results = check_optional_vars()
    
    for var, value, suggestion in optional_results:
        status = "✅" if value != "未设置" else "💡"
        print(f"  {status} {var}: {value}")
        if suggestion:
            print(f"     {suggestion}")
    
    # 生成配置建议
    print("\n" + "=" * 60)
    print("📝 配置建议:")
    
    if required_missing:
        print("\n❗ 必需配置缺失:")
        for var in required_missing:
            print(f"  - 请设置 {var}")
    
    if not aws_ok:
        print("\n❗ AWS 凭证配置:")
        print("  - 运行 'aws configure' 配置凭证")
        print("  - 或设置 AWS_ACCESS_KEY_ID 和 AWS_SECRET_ACCESS_KEY 环境变量")
    
    if missing_packages:
        print("\n❗ 缺失的 Python 包:")
        print("  - 运行 'pip install -r requirements.txt'")
        print("  - 或使用 conda: 'conda env create -f environment-testing.yml'")
    
    # 生成环境变量模板
    print("\n🚀 快速启动:")
    template_file = generate_env_template()
    print(f"  1. 环境变量模板已生成: {template_file}")
    print("  2. 复制并修改模板:")
    print(f"     cp {template_file} .env.testing")
    print("     # 编辑 .env.testing 文件设置您的值")
    print("  3. 加载环境变量:")
    print("     source .env.testing")
    print("  4. 运行此检查脚本验证:")
    print("     python3 check_env.py")
    print("  5. 运行测试:")
    print("     ./run_tests_conda.sh all -v -r")
    
    # 返回状态码
    if required_missing or not aws_ok:
        print(f"\n❌ 配置检查失败: 请解决上述问题后重新运行")
        return 1
    else:
        print(f"\n✅ 环境配置检查通过: 可以开始运行测试")
        return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  检查被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 检查过程中出现错误: {e}")
        sys.exit(1) 