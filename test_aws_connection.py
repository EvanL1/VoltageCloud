#!/usr/bin/env python3
"""测试 AWS 连接"""
import boto3
import sys

def test_connection(profile=None):
    try:
        if profile:
            boto3.setup_default_session(profile_name=profile)
            print(f"使用 profile: {profile}")
        
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        
        print("AWS 连接成功！")
        print(f"Account ID: {identity['Account']}")
        print(f"User ARN: {identity['Arn']}")
        print(f"User ID: {identity['UserId']}")
        return True
        
    except Exception as e:
        print(f"AWS 连接失败: {str(e)}")
        return False

if __name__ == "__main__":
    profile = sys.argv[1] if len(sys.argv) > 1 else None
    success = test_connection(profile)
    sys.exit(0 if success else 1)