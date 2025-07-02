#!/usr/bin/env python3
"""
限制权限的 AWS IoT 架构设置脚本
只创建当前用户有权限的资源
"""

import boto3
import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LimitedIoTSetup:
    """限制权限的 IoT 设置类"""
    
    def __init__(self, region='us-east-1', prefix='monarch-iot-demo'):
        self.region = region
        self.prefix = prefix
        self.resources = {}
        
        # 初始化客户端
        self.iot = boto3.client('iot', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.sts = boto3.client('sts', region_name=region)
        
        # 获取账户信息
        identity = self.sts.get_caller_identity()
        self.account_id = identity['Account']
        self.user_arn = identity['Arn']
        
    def create_iot_resources(self):
        """创建 IoT 资源（Things, Policies, Rules）"""
        logger.info("创建 IoT 资源...")
        
        # 1. 创建 Thing Type
        try:
            thing_type_name = f"{self.prefix}-device-type"
            self.iot.create_thing_type(
                thingTypeName=thing_type_name,
                thingTypeProperties={
                    'thingTypeDescription': 'IoT设备类型',
                    'searchableAttributes': ['deviceModel', 'firmwareVersion']
                }
            )
            logger.info(f"创建 Thing Type: {thing_type_name}")
            self.resources['thing_type'] = thing_type_name
        except self.iot.exceptions.ResourceAlreadyExistsException:
            logger.info(f"Thing Type 已存在: {thing_type_name}")
        except Exception as e:
            logger.warning(f"无法创建 Thing Type: {e}")
            
        # 2. 创建 IoT Policy
        try:
            policy_name = f"{self.prefix}-device-policy"
            policy_document = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:Connect",
                            "iot:Publish",
                            "iot:Subscribe",
                            "iot:Receive"
                        ],
                        "Resource": [
                            f"arn:aws:iot:{self.region}:{self.account_id}:topic/${{iot:Connection.Thing.ThingName}}/*",
                            f"arn:aws:iot:{self.region}:{self.account_id}:topicfilter/${{iot:Connection.Thing.ThingName}}/*",
                            f"arn:aws:iot:{self.region}:{self.account_id}:client/${{iot:Connection.Thing.ThingName}}"
                        ]
                    }
                ]
            }
            
            self.iot.create_policy(
                policyName=policy_name,
                policyDocument=json.dumps(policy_document)
            )
            logger.info(f"创建 IoT Policy: {policy_name}")
            self.resources['iot_policy'] = policy_name
        except self.iot.exceptions.ResourceAlreadyExistsException:
            logger.info(f"IoT Policy 已存在: {policy_name}")
        except Exception as e:
            logger.warning(f"无法创建 IoT Policy: {e}")
            
        # 3. 创建示例 Thing
        try:
            thing_name = f"{self.prefix}-sample-device"
            self.iot.create_thing(
                thingName=thing_name,
                thingTypeName=self.resources.get('thing_type', thing_type_name),
                attributePayload={
                    'attributes': {
                        'deviceModel': 'IoT-Sensor-v1',
                        'location': 'us-east-1'
                    }
                }
            )
            logger.info(f"创建示例 Thing: {thing_name}")
            self.resources['sample_thing'] = thing_name
        except self.iot.exceptions.ResourceAlreadyExistsException:
            logger.info(f"Thing 已存在: {thing_name}")
        except Exception as e:
            logger.warning(f"无法创建 Thing: {e}")
            
    def check_s3_permissions(self):
        """检查并创建 S3 资源"""
        logger.info("检查 S3 权限...")
        
        try:
            # 列出现有的 buckets
            response = self.s3.list_buckets()
            existing_buckets = [b['Name'] for b in response['Buckets']]
            logger.info(f"找到 {len(existing_buckets)} 个现有 S3 桶")
            
            # 尝试创建新桶
            bucket_name = f"{self.prefix}-iot-data-{self.account_id}"
            if bucket_name not in existing_buckets:
                try:
                    if self.region == 'us-east-1':
                        self.s3.create_bucket(Bucket=bucket_name)
                    else:
                        self.s3.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                    logger.info(f"创建 S3 桶: {bucket_name}")
                    self.resources['s3_bucket'] = bucket_name
                except Exception as e:
                    logger.warning(f"无法创建 S3 桶: {e}")
            else:
                logger.info(f"S3 桶已存在: {bucket_name}")
                self.resources['s3_bucket'] = bucket_name
                
        except Exception as e:
            logger.warning(f"S3 操作失败: {e}")
            
    def generate_device_config(self):
        """生成设备连接配置"""
        logger.info("生成设备连接配置...")
        
        try:
            # 获取 IoT 端点
            endpoint_response = self.iot.describe_endpoint(endpointType='iot:Data-ATS')
            endpoint = endpoint_response['endpointAddress']
            
            config = {
                "iot_endpoint": endpoint,
                "region": self.region,
                "thing_name": self.resources.get('sample_thing', f"{self.prefix}-sample-device"),
                "policy_name": self.resources.get('iot_policy', f"{self.prefix}-device-policy"),
                "connection_instructions": {
                    "1": "创建设备证书: aws iot create-keys-and-certificate --set-as-active",
                    "2": "附加策略到证书: aws iot attach-policy --policy-name <policy> --target <cert-arn>",
                    "3": "附加证书到设备: aws iot attach-thing-principal --thing-name <thing> --principal <cert-arn>",
                    "4": "使用 MQTT 客户端连接到端点"
                }
            }
            
            # 保存配置文件
            config_file = f"{self.prefix}_device_config.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                
            logger.info(f"设备配置已保存到: {config_file}")
            self.resources['config_file'] = config_file
            
            return config
            
        except Exception as e:
            logger.error(f"生成配置失败: {e}")
            return None
            
    def generate_report(self):
        """生成部署报告"""
        report = f"""
AWS IoT 限制权限部署报告
=======================
部署时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
账户 ID: {self.account_id}
用户: {self.user_arn}
区域: {self.region}
资源前缀: {self.prefix}

创建的资源:
-----------"""
        
        if self.resources:
            for key, value in self.resources.items():
                report += f"\n- {key}: {value}"
        else:
            report += "\n- 没有创建任何资源"
            
        report += """

后续步骤:
---------
1. 请联系管理员获取以下权限:
   - IAM: CreateRole (创建服务角色)
   - Lambda: CreateFunction (创建数据处理函数)
   - TimeStream: CreateDatabase (创建时序数据库)

2. 使用现有 IoT 资源:
   - 查看设备配置: cat {}_device_config.json
   - 创建设备证书并连接

3. 可以使用的功能:
   - IoT Core: 设备连接、消息发布订阅
   - S3: 数据存储（如果有权限）
   - Device Shadow: 设备状态同步
""".format(self.prefix)
        
        return report
        
    def deploy(self):
        """执行部署"""
        logger.info("开始限制权限的 IoT 部署...")
        
        try:
            # 创建 IoT 资源
            self.create_iot_resources()
            
            # 检查 S3 权限
            self.check_s3_permissions()
            
            # 生成设备配置
            self.generate_device_config()
            
            # 生成报告
            report = self.generate_report()
            print(report)
            
            # 保存报告
            report_file = f"{self.prefix}_deployment_report.txt"
            with open(report_file, 'w') as f:
                f.write(report)
            logger.info(f"部署报告已保存到: {report_file}")
            
            return self.resources
            
        except Exception as e:
            logger.error(f"部署失败: {e}")
            raise

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='限制权限的 AWS IoT 部署脚本')
    parser.add_argument('--region', default='us-east-1', help='AWS区域')
    parser.add_argument('--prefix', default='monarch-iot-demo', help='资源前缀')
    parser.add_argument('--profile', help='AWS配置文件名')
    
    args = parser.parse_args()
    
    if args.profile:
        boto3.setup_default_session(profile_name=args.profile)
    
    setup = LimitedIoTSetup(region=args.region, prefix=args.prefix)
    
    try:
        setup.deploy()
        logger.info("部署完成！")
    except Exception as e:
        logger.error(f"部署失败: {e}")
        raise

if __name__ == "__main__":
    main()