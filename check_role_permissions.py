#!/usr/bin/env python3
"""
查看和分析 AWS IAM 角色权限
"""

import boto3
import json
from datetime import datetime

def analyze_role_permissions(profile=None):
    """分析当前用户的角色和权限"""
    
    if profile:
        boto3.setup_default_session(profile_name=profile)
    
    iam = boto3.client('iam')
    sts = boto3.client('sts')
    
    print("=" * 60)
    print("AWS 角色权限分析报告")
    print("=" * 60)
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. 获取当前身份信息
    identity = sts.get_caller_identity()
    print("当前身份信息:")
    print(f"- 账户 ID: {identity['Account']}")
    print(f"- 用户 ARN: {identity['Arn']}")
    print(f"- 用户 ID: {identity['UserId']}")
    
    # 从 ARN 中提取角色名
    arn_parts = identity['Arn'].split('/')
    if 'assumed-role' in identity['Arn']:
        role_name = arn_parts[1]
        session_name = arn_parts[2] if len(arn_parts) > 2 else None
        print(f"- 当前角色: {role_name}")
        print(f"- 会话名称: {session_name}")
    
    print()
    
    # 2. 尝试获取角色信息
    try:
        # 对于 SSO 角色，角色名可能需要调整
        if 'AWSReservedSSO' in role_name:
            print("SSO 角色信息:")
            print(f"- 角色类型: AWS SSO 托管角色")
            print(f"- 权限集 ID: {role_name.split('_')[-1]}")
            
            # 尝试获取角色详情
            try:
                role_info = iam.get_role(RoleName=role_name)
                print(f"- 创建时间: {role_info['Role']['CreateDate']}")
                print(f"- 最大会话时长: {role_info['Role'].get('MaxSessionDuration', 3600)} 秒")
            except Exception as e:
                print(f"- 无法获取角色详情: {str(e).split(':')[0]}")
    except Exception as e:
        print(f"获取角色信息失败: {e}")
    
    print()
    
    # 3. 列出可以访问的策略
    print("附加的策略:")
    try:
        # 尝试列出角色的策略
        if 'assumed-role' in identity['Arn']:
            # 对于假定的角色，尝试列出附加的策略
            try:
                # 内联策略
                inline_policies = iam.list_role_policies(RoleName=role_name)
                if inline_policies['PolicyNames']:
                    print("\n内联策略:")
                    for policy_name in inline_policies['PolicyNames']:
                        print(f"  - {policy_name}")
            except Exception:
                print("  - 无法列出内联策略")
            
            try:
                # 托管策略
                attached_policies = iam.list_attached_role_policies(RoleName=role_name)
                if attached_policies['AttachedPolicies']:
                    print("\n托管策略:")
                    for policy in attached_policies['AttachedPolicies']:
                        print(f"  - {policy['PolicyName']} (ARN: {policy['PolicyArn']})")
            except Exception:
                print("  - 无法列出托管策略")
    except Exception as e:
        print(f"  - 无法获取策略列表: {str(e).split(':')[0]}")
    
    print()
    
    # 4. 测试具体权限
    print("权限测试结果:")
    print("\n服务级别权限:")
    
    # 定义要测试的服务和操作
    service_tests = {
        'IAM': {
            'client': 'iam',
            'read_ops': {
                'ListRoles': lambda c: c.list_roles(MaxItems=1),
                'ListUsers': lambda c: c.list_users(MaxItems=1),
                'ListGroups': lambda c: c.list_groups(MaxItems=1),
                'ListPolicies': lambda c: c.list_policies(MaxItems=1, Scope='Local'),
            },
            'write_ops': {
                'CreateRole': '创建角色',
                'CreatePolicy': '创建策略',
                'CreateUser': '创建用户',
            }
        },
        'S3': {
            'client': 's3',
            'read_ops': {
                'ListBuckets': lambda c: c.list_buckets(),
            },
            'write_ops': {
                'CreateBucket': '创建存储桶',
                'PutObject': '上传对象',
            }
        },
        'IoT': {
            'client': 'iot',
            'read_ops': {
                'ListThings': lambda c: c.list_things(maxResults=1),
                'ListPolicies': lambda c: c.list_policies(pageSize=1),
                'ListThingTypes': lambda c: c.list_thing_types(maxResults=1),
                'DescribeEndpoint': lambda c: c.describe_endpoint(endpointType='iot:Data-ATS'),
            },
            'write_ops': {
                'CreateThing': '创建设备',
                'CreatePolicy': '创建策略',
                'CreateThingType': '创建设备类型',
            }
        },
        'Lambda': {
            'client': 'lambda',
            'read_ops': {
                'ListFunctions': lambda c: c.list_functions(MaxItems=1),
            },
            'write_ops': {
                'CreateFunction': '创建函数',
            }
        },
        'EC2': {
            'client': 'ec2',
            'read_ops': {
                'DescribeInstances': lambda c: c.describe_instances(MaxResults=5),
                'DescribeVpcs': lambda c: c.describe_vpcs(MaxResults=5),
            },
            'write_ops': {
                'RunInstances': '启动实例',
                'CreateVpc': '创建 VPC',
            }
        }
    }
    
    permissions_summary = {}
    
    for service_name, service_config in service_tests.items():
        print(f"\n{service_name}:")
        permissions_summary[service_name] = {
            'read': [],
            'write': []
        }
        
        try:
            client = boto3.client(service_config['client'])
            
            # 测试读权限
            for op_name, op_func in service_config['read_ops'].items():
                try:
                    op_func(client)
                    print(f"  ✓ {op_name}")
                    permissions_summary[service_name]['read'].append(op_name)
                except Exception as e:
                    error_type = str(e).split(':')[0].replace('An error occurred (', '').replace(')', '')
                    print(f"  ✗ {op_name} ({error_type})")
            
            # 写权限只显示状态（不实际执行）
            for op_name, op_desc in service_config['write_ops'].items():
                if permissions_summary[service_name]['read']:
                    print(f"  ? {op_name} - {op_desc} (需要更高权限)")
                else:
                    print(f"  ✗ {op_name} - {op_desc} (无权限)")
                    
        except Exception as e:
            print(f"  ✗ 无法访问 {service_name} 服务")
    
    # 5. 生成权限摘要
    print("\n" + "=" * 60)
    print("权限摘要:")
    print("=" * 60)
    
    # 可访问的服务
    accessible_services = [s for s, perms in permissions_summary.items() if perms['read']]
    print(f"\n可访问的服务 ({len(accessible_services)}):")
    for service in accessible_services:
        read_count = len(permissions_summary[service]['read'])
        print(f"  - {service}: {read_count} 个读取操作")
    
    # 受限的服务
    restricted_services = [s for s, perms in permissions_summary.items() if not perms['read']]
    if restricted_services:
        print(f"\n无权访问的服务 ({len(restricted_services)}):")
        for service in restricted_services:
            print(f"  - {service}")
    
    # 建议
    print("\n建议:")
    print("1. 当前角色主要具有以下服务的读取权限:")
    for service in accessible_services:
        print(f"   - {service}")
    
    print("\n2. 如需创建资源，请联系管理员添加以下权限:")
    print("   - IAM: CreateRole, AttachRolePolicy")
    print("   - S3: CreateBucket, PutObject")
    print("   - Lambda: CreateFunction")
    print("   - IoT: CreateThing, CreateThingType")
    
    print("\n3. 当前角色适合:")
    print("   - 查看和监控现有资源")
    print("   - 管理 IoT 设备策略")
    print("   - 读取配置和状态信息")
    
    return permissions_summary

if __name__ == "__main__":
    import sys
    profile = sys.argv[1] if len(sys.argv) > 1 else None
    analyze_role_permissions(profile)