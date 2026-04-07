#!/usr/bin/env python3
"""
ECS Infrastructure Setup for Energy Management System
"""
import boto3
import json
from datetime import datetime

class ECSInfrastructureSetup:
    def __init__(self, region='us-east-1', prefix='ems'):
        self.region = region
        self.prefix = prefix
        self.ec2 = boto3.client('ec2', region_name=region)
        self.ecs = boto3.client('ecs', region_name=region)
        self.ecr = boto3.client('ecr', region_name=region)
        self.iam = boto3.client('iam', region_name=region)
        self.elbv2 = boto3.client('elbv2', region_name=region)
        self.logs = boto3.client('logs', region_name=region)
        
        # 获取账户ID
        sts = boto3.client('sts', region_name=region)
        self.account_id = sts.get_caller_identity()['Account']
        
    def create_vpc_and_network(self):
        """创建VPC和网络资源"""
        print("🔧 创建VPC和网络资源...")
        
        # 创建VPC
        vpc_response = self.ec2.create_vpc(
            CidrBlock='10.0.0.0/16',
            TagSpecifications=[{
                'ResourceType': 'vpc',
                'Tags': [
                    {'Key': 'Name', 'Value': f'{self.prefix}-vpc'},
                    {'Key': 'Project', 'Value': 'EMS'}
                ]
            }]
        )
        vpc_id = vpc_response['Vpc']['VpcId']
        
        # 启用DNS支持
        self.ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={'Value': True})
        self.ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={'Value': True})
        
        # 创建Internet Gateway
        igw_response = self.ec2.create_internet_gateway(
            TagSpecifications=[{
                'ResourceType': 'internet-gateway',
                'Tags': [{'Key': 'Name', 'Value': f'{self.prefix}-igw'}]
            }]
        )
        igw_id = igw_response['InternetGateway']['InternetGatewayId']
        self.ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        
        # 获取可用区
        azs = self.ec2.describe_availability_zones()['AvailabilityZones'][:3]
        
        # 创建子网
        public_subnets = []
        private_subnets = []
        
        for i, az in enumerate(azs):
            # Public Subnet
            public_subnet = self.ec2.create_subnet(
                VpcId=vpc_id,
                CidrBlock=f'10.0.{i+1}.0/24',
                AvailabilityZone=az['ZoneName'],
                TagSpecifications=[{
                    'ResourceType': 'subnet',
                    'Tags': [{'Key': 'Name', 'Value': f'{self.prefix}-public-{az["ZoneName"]}'}]
                }]
            )
            public_subnets.append(public_subnet['Subnet']['SubnetId'])
            
            # Private Subnet
            private_subnet = self.ec2.create_subnet(
                VpcId=vpc_id,
                CidrBlock=f'10.0.{i+11}.0/24',
                AvailabilityZone=az['ZoneName'],
                TagSpecifications=[{
                    'ResourceType': 'subnet',
                    'Tags': [{'Key': 'Name', 'Value': f'{self.prefix}-private-{az["ZoneName"]}'}]
                }]
            )
            private_subnets.append(private_subnet['Subnet']['SubnetId'])
        
        # 创建NAT Gateway (仅在第一个公共子网)
        eip_response = self.ec2.allocate_address(Domain='vpc')
        nat_response = self.ec2.create_nat_gateway(
            SubnetId=public_subnets[0],
            AllocationId=eip_response['AllocationId'],
            TagSpecifications=[{
                'ResourceType': 'nat-gateway',
                'Tags': [{'Key': 'Name', 'Value': f'{self.prefix}-nat'}]
            }]
        )
        nat_id = nat_response['NatGateway']['NatGatewayId']
        
        # 创建路由表
        # Public Route Table
        public_rt = self.ec2.create_route_table(
            VpcId=vpc_id,
            TagSpecifications=[{
                'ResourceType': 'route-table',
                'Tags': [{'Key': 'Name', 'Value': f'{self.prefix}-public-rt'}]
            }]
        )
        public_rt_id = public_rt['RouteTable']['RouteTableId']
        
        self.ec2.create_route(
            RouteTableId=public_rt_id,
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=igw_id
        )
        
        for subnet_id in public_subnets:
            self.ec2.associate_route_table(RouteTableId=public_rt_id, SubnetId=subnet_id)
        
        # Private Route Table
        private_rt = self.ec2.create_route_table(
            VpcId=vpc_id,
            TagSpecifications=[{
                'ResourceType': 'route-table',
                'Tags': [{'Key': 'Name', 'Value': f'{self.prefix}-private-rt'}]
            }]
        )
        private_rt_id = private_rt['RouteTable']['RouteTableId']
        
        # 等待NAT Gateway可用后创建路由
        waiter = self.ec2.get_waiter('nat_gateway_available')
        waiter.wait(NatGatewayIds=[nat_id])
        
        self.ec2.create_route(
            RouteTableId=private_rt_id,
            DestinationCidrBlock='0.0.0.0/0',
            NatGatewayId=nat_id
        )
        
        for subnet_id in private_subnets:
            self.ec2.associate_route_table(RouteTableId=private_rt_id, SubnetId=subnet_id)
        
        print(f"✅ VPC创建成功: {vpc_id}")
        
        return {
            'vpc_id': vpc_id,
            'public_subnets': public_subnets,
            'private_subnets': private_subnets
        }
    
    def create_security_groups(self, vpc_id):
        """创建安全组"""
        print("🔧 创建安全组...")
        
        # ALB Security Group
        alb_sg = self.ec2.create_security_group(
            GroupName=f'{self.prefix}-alb-sg',
            Description='Security group for Application Load Balancer',
            VpcId=vpc_id,
            TagSpecifications=[{
                'ResourceType': 'security-group',
                'Tags': [{'Key': 'Name', 'Value': f'{self.prefix}-alb-sg'}]
            }]
        )
        alb_sg_id = alb_sg['GroupId']
        
        # 允许HTTP和HTTPS入站
        self.ec2.authorize_security_group_ingress(
            GroupId=alb_sg_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 80,
                    'ToPort': 80,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 443,
                    'ToPort': 443,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        
        # ECS Tasks Security Group
        ecs_sg = self.ec2.create_security_group(
            GroupName=f'{self.prefix}-ecs-tasks-sg',
            Description='Security group for ECS tasks',
            VpcId=vpc_id,
            TagSpecifications=[{
                'ResourceType': 'security-group',
                'Tags': [{'Key': 'Name', 'Value': f'{self.prefix}-ecs-tasks-sg'}]
            }]
        )
        ecs_sg_id = ecs_sg['GroupId']
        
        # 允许从ALB的入站流量
        self.ec2.authorize_security_group_ingress(
            GroupId=ecs_sg_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 80,
                    'ToPort': 80,
                    'UserIdGroupPairs': [{'GroupId': alb_sg_id}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 3000,
                    'ToPort': 3000,
                    'UserIdGroupPairs': [{'GroupId': alb_sg_id}]
                }
            ]
        )
        
        print(f"✅ 安全组创建成功")
        
        return {
            'alb_sg_id': alb_sg_id,
            'ecs_sg_id': ecs_sg_id
        }
    
    def create_ecr_repositories(self):
        """创建ECR仓库"""
        print("🔧 创建ECR仓库...")
        
        repositories = ['frontend', 'backend']
        
        for repo in repositories:
            repo_name = f'{self.prefix}-{repo}'
            try:
                response = self.ecr.create_repository(
                    repositoryName=repo_name,
                    imageScanningConfiguration={'scanOnPush': True},
                    imageTagMutability='MUTABLE',
                    tags=[
                        {'Key': 'Project', 'Value': 'EMS'},
                        {'Key': 'Component', 'Value': repo}
                    ]
                )
                print(f"✅ ECR仓库创建成功: {repo_name}")
                
                # 设置生命周期策略
                lifecycle_policy = {
                    "rules": [
                        {
                            "rulePriority": 1,
                            "description": "Keep last 10 images",
                            "selection": {
                                "tagStatus": "any",
                                "countType": "imageCountMoreThan",
                                "countNumber": 10
                            },
                            "action": {
                                "type": "expire"
                            }
                        }
                    ]
                }
                
                self.ecr.put_lifecycle_policy(
                    repositoryName=repo_name,
                    lifecyclePolicyText=json.dumps(lifecycle_policy)
                )
                
            except self.ecr.exceptions.RepositoryAlreadyExistsException:
                print(f"⚠️  ECR仓库已存在: {repo_name}")
    
    def create_iam_roles(self):
        """创建IAM角色"""
        print("🔧 创建IAM角色...")
        
        # ECS Task Execution Role
        task_execution_role_name = f'{self.prefix}-ecs-task-execution-role'
        
        try:
            task_execution_trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "ecs-tasks.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
            
            task_execution_role = self.iam.create_role(
                RoleName=task_execution_role_name,
                AssumeRolePolicyDocument=json.dumps(task_execution_trust_policy),
                Description='ECS task execution role for EMS',
                Tags=[
                    {'Key': 'Project', 'Value': 'EMS'}
                ]
            )
            
            # 附加托管策略
            self.iam.attach_role_policy(
                RoleName=task_execution_role_name,
                PolicyArn='arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy'
            )
            
            print(f"✅ Task Execution Role 创建成功")
            
        except self.iam.exceptions.EntityAlreadyExistsException:
            print(f"⚠️  Task Execution Role 已存在")
        
        # ECS Task Role
        task_role_name = f'{self.prefix}-ecs-task-role'
        
        try:
            task_role = self.iam.create_role(
                RoleName=task_role_name,
                AssumeRolePolicyDocument=json.dumps(task_execution_trust_policy),
                Description='ECS task role for EMS application',
                Tags=[
                    {'Key': 'Project', 'Value': 'EMS'}
                ]
            )
            
            # 创建自定义策略
            task_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:*",
                            "iot-data:*",
                            "timestream:DescribeEndpoints",
                            "timestream:SelectValues",
                            "timestream:CancelQuery",
                            "timestream:Query",
                            "dynamodb:GetItem",
                            "dynamodb:PutItem",
                            "dynamodb:Query",
                            "dynamodb:Scan",
                            "s3:GetObject",
                            "s3:PutObject"
                        ],
                        "Resource": "*"
                    }
                ]
            }
            
            self.iam.put_role_policy(
                RoleName=task_role_name,
                PolicyName=f'{self.prefix}-task-policy',
                PolicyDocument=json.dumps(task_policy)
            )
            
            print(f"✅ Task Role 创建成功")
            
        except self.iam.exceptions.EntityAlreadyExistsException:
            print(f"⚠️  Task Role 已存在")
        
        return {
            'task_execution_role_arn': f'arn:aws:iam::{self.account_id}:role/{task_execution_role_name}',
            'task_role_arn': f'arn:aws:iam::{self.account_id}:role/{task_role_name}'
        }
    
    def create_ecs_cluster(self):
        """创建ECS集群"""
        print("🔧 创建ECS集群...")
        
        cluster_name = f'{self.prefix}-cluster'
        
        try:
            response = self.ecs.create_cluster(
                clusterName=cluster_name,
                settings=[
                    {
                        'name': 'containerInsights',
                        'value': 'enabled'
                    }
                ],
                capacityProviders=['FARGATE', 'FARGATE_SPOT'],
                defaultCapacityProviderStrategy=[
                    {
                        'capacityProvider': 'FARGATE',
                        'weight': 1,
                        'base': 1
                    },
                    {
                        'capacityProvider': 'FARGATE_SPOT',
                        'weight': 4
                    }
                ],
                tags=[
                    {'key': 'Project', 'value': 'EMS'}
                ]
            )
            
            print(f"✅ ECS集群创建成功: {cluster_name}")
            
        except Exception as e:
            print(f"⚠️  创建ECS集群时出错: {str(e)}")
        
        return cluster_name
    
    def create_log_groups(self):
        """创建CloudWatch日志组"""
        print("🔧 创建日志组...")
        
        log_groups = [
            f'/ecs/{self.prefix}-frontend',
            f'/ecs/{self.prefix}-backend'
        ]
        
        for log_group in log_groups:
            try:
                self.logs.create_log_group(
                    logGroupName=log_group,
                    tags={
                        'Project': 'EMS'
                    }
                )
                
                # 设置日志保留期为30天
                self.logs.put_retention_policy(
                    logGroupName=log_group,
                    retentionInDays=30
                )
                
                print(f"✅ 日志组创建成功: {log_group}")
                
            except self.logs.exceptions.ResourceAlreadyExistsException:
                print(f"⚠️  日志组已存在: {log_group}")
    
    def create_alb(self, vpc_id, public_subnets, alb_sg_id):
        """创建Application Load Balancer"""
        print("🔧 创建Application Load Balancer...")
        
        alb_name = f'{self.prefix}-alb'
        
        try:
            response = self.elbv2.create_load_balancer(
                Name=alb_name,
                Subnets=public_subnets,
                SecurityGroups=[alb_sg_id],
                Scheme='internet-facing',
                Type='application',
                IpAddressType='ipv4',
                Tags=[
                    {'Key': 'Project', 'Value': 'EMS'}
                ]
            )
            
            alb_arn = response['LoadBalancers'][0]['LoadBalancerArn']
            alb_dns = response['LoadBalancers'][0]['DNSName']
            
            print(f"✅ ALB创建成功: {alb_dns}")
            
            # 创建目标组
            frontend_tg = self.elbv2.create_target_group(
                Name=f'{self.prefix}-frontend-tg',
                Protocol='HTTP',
                Port=80,
                VpcId=vpc_id,
                TargetType='ip',
                HealthCheckPath='/',
                HealthCheckIntervalSeconds=30,
                HealthCheckTimeoutSeconds=5,
                HealthyThresholdCount=2,
                UnhealthyThresholdCount=3,
                Tags=[
                    {'Key': 'Project', 'Value': 'EMS'}
                ]
            )
            
            backend_tg = self.elbv2.create_target_group(
                Name=f'{self.prefix}-backend-tg',
                Protocol='HTTP',
                Port=3000,
                VpcId=vpc_id,
                TargetType='ip',
                HealthCheckPath='/health',
                HealthCheckIntervalSeconds=30,
                HealthCheckTimeoutSeconds=5,
                HealthyThresholdCount=2,
                UnhealthyThresholdCount=3,
                Tags=[
                    {'Key': 'Project', 'Value': 'EMS'}
                ]
            )
            
            # 创建监听器
            listener = self.elbv2.create_listener(
                LoadBalancerArn=alb_arn,
                Protocol='HTTP',
                Port=80,
                DefaultActions=[
                    {
                        'Type': 'fixed-response',
                        'FixedResponseConfig': {
                            'StatusCode': '404',
                            'ContentType': 'text/plain',
                            'MessageBody': 'Not Found'
                        }
                    }
                ]
            )
            
            # 添加规则
            self.elbv2.create_rule(
                ListenerArn=listener['Listeners'][0]['ListenerArn'],
                Priority=1,
                Conditions=[
                    {
                        'Field': 'path-pattern',
                        'Values': ['/api/*']
                    }
                ],
                Actions=[
                    {
                        'Type': 'forward',
                        'TargetGroupArn': backend_tg['TargetGroups'][0]['TargetGroupArn']
                    }
                ]
            )
            
            self.elbv2.create_rule(
                ListenerArn=listener['Listeners'][0]['ListenerArn'],
                Priority=2,
                Conditions=[
                    {
                        'Field': 'path-pattern',
                        'Values': ['/*']
                    }
                ],
                Actions=[
                    {
                        'Type': 'forward',
                        'TargetGroupArn': frontend_tg['TargetGroups'][0]['TargetGroupArn']
                    }
                ]
            )
            
            return {
                'alb_arn': alb_arn,
                'alb_dns': alb_dns,
                'frontend_tg_arn': frontend_tg['TargetGroups'][0]['TargetGroupArn'],
                'backend_tg_arn': backend_tg['TargetGroups'][0]['TargetGroupArn']
            }
            
        except Exception as e:
            print(f"❌ 创建ALB时出错: {str(e)}")
            return None
    
    def deploy(self):
        """执行完整部署"""
        print("🚀 开始部署ECS基础设施...")
        print(f"   账户ID: {self.account_id}")
        print(f"   区域: {self.region}")
        print(f"   前缀: {self.prefix}")
        
        results = {}
        
        # 创建VPC和网络
        network = self.create_vpc_and_network()
        results['network'] = network
        
        # 创建安全组
        security_groups = self.create_security_groups(network['vpc_id'])
        results['security_groups'] = security_groups
        
        # 创建ECR仓库
        self.create_ecr_repositories()
        
        # 创建IAM角色
        iam_roles = self.create_iam_roles()
        results['iam_roles'] = iam_roles
        
        # 创建日志组
        self.create_log_groups()
        
        # 创建ECS集群
        cluster_name = self.create_ecs_cluster()
        results['cluster_name'] = cluster_name
        
        # 创建ALB
        alb = self.create_alb(
            network['vpc_id'],
            network['public_subnets'],
            security_groups['alb_sg_id']
        )
        results['alb'] = alb
        
        # 保存配置
        config = {
            'region': self.region,
            'account_id': self.account_id,
            'prefix': self.prefix,
            'cluster_name': cluster_name,
            'vpc_id': network['vpc_id'],
            'private_subnets': network['private_subnets'],
            'security_groups': security_groups,
            'iam_roles': iam_roles,
            'alb': alb,
            'ecr_repositories': {
                'frontend': f'{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/{self.prefix}-frontend',
                'backend': f'{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/{self.prefix}-backend'
            }
        }
        
        with open('ecs-config.json', 'w') as f:
            json.dump(config, f, indent=2)
        
        print("\n✅ ECS基础设施部署完成！")
        print(f"   ALB DNS: {alb['alb_dns'] if alb else 'N/A'}")
        print("\n📋 下一步:")
        print("   1. 构建并推送Docker镜像到ECR")
        print("   2. 创建ECS任务定义")
        print("   3. 创建ECS服务")
        print("   4. 配置域名和SSL证书")
        
        return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy ECS infrastructure for EMS')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--prefix', default='ems', help='Resource prefix')
    
    args = parser.parse_args()
    
    setup = ECSInfrastructureSetup(region=args.region, prefix=args.prefix)
    setup.deploy()