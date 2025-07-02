#!/usr/bin/env python3
"""检查 AWS 账户权限"""
import boto3
import json

def check_permissions(profile=None):
    if profile:
        boto3.setup_default_session(profile_name=profile)
    
    # 获取身份信息
    sts = boto3.client('sts')
    identity = sts.get_caller_identity()
    print(f"当前身份: {identity['Arn']}")
    print(f"账户 ID: {identity['Account']}")
    print("\n检查各项服务权限:")
    
    services_to_check = {
        'iam': ['ListRoles', 'ListPolicies'],
        'iot': ['ListThings', 'ListPolicies', 'ListThingTypes'],
        's3': ['ListBuckets'],
        'lambda': ['ListFunctions'],
        'timestream-write': ['ListDatabases'],
    }
    
    results = {}
    
    for service, actions in services_to_check.items():
        print(f"\n{service.upper()} 权限:")
        results[service] = {}
        
        try:
            client = boto3.client(service)
            
            for action in actions:
                try:
                    # 尝试执行只读操作来测试权限
                    if service == 'iam':
                        if action == 'ListRoles':
                            client.list_roles(MaxItems=1)
                        elif action == 'ListPolicies':
                            client.list_policies(MaxItems=1)
                    elif service == 'iot':
                        if action == 'ListThings':
                            client.list_things(maxResults=1)
                        elif action == 'ListPolicies':
                            client.list_policies(pageSize=1)
                        elif action == 'ListThingTypes':
                            client.list_thing_types(maxResults=1)
                    elif service == 's3':
                        client.list_buckets()
                    elif service == 'lambda':
                        client.list_functions(MaxItems=1)
                    elif service == 'timestream-write':
                        client.list_databases(MaxResults=1)
                    
                    print(f"  ✓ {action}: 有权限")
                    results[service][action] = True
                    
                except Exception as e:
                    print(f"  ✗ {action}: 无权限 ({str(e).split(':')[0]})")
                    results[service][action] = False
                    
        except Exception as e:
            print(f"  ✗ 无法访问 {service} 服务")
            results[service] = {"error": str(e)}
    
    # 检查创建权限
    print("\n\n创建资源权限检查:")
    create_actions = {
        'iam': 'CreateRole',
        'iot': 'CreateThing',
        's3': 'CreateBucket',
        'lambda': 'CreateFunction'
    }
    
    for service, action in create_actions.items():
        print(f"{service.upper()}: {action} - ", end="")
        # 基于列表权限推断创建权限
        if service in results and any(results[service].values()):
            print("可能没有权限（需要更高权限）")
        else:
            print("无权限")
    
    return results

if __name__ == "__main__":
    import sys
    profile = sys.argv[1] if len(sys.argv) > 1 else None
    check_permissions(profile)