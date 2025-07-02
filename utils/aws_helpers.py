"""
AWS辅助函数模块
提供通用的AWS资源创建和管理功能
"""

import boto3
import json
import time
import logging
from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class AWSResourceHelper:
    """AWS资源辅助类"""
    
    def __init__(self, region: str = 'us-east-1'):
        """初始化辅助类"""
        self.region = region
        self.account_id = None
        self._get_account_id()
    
    def _get_account_id(self):
        """获取AWS账户ID"""
        try:
            sts = boto3.client('sts')
            self.account_id = sts.get_caller_identity()['Account']
        except Exception as e:
            logger.error(f"获取账户ID失败: {str(e)}")
            raise
    
    def wait_for_resource(self, check_function, resource_name: str, 
                         max_attempts: int = 30, delay: int = 10) -> bool:
        """等待资源就绪"""
        for attempt in range(max_attempts):
            try:
                if check_function():
                    logger.info(f"{resource_name} 已就绪")
                    return True
            except Exception as e:
                logger.debug(f"检查 {resource_name} 状态时出错: {str(e)}")
            
            if attempt < max_attempts - 1:
                logger.info(f"等待 {resource_name} 就绪... ({attempt + 1}/{max_attempts})")
                time.sleep(delay)
        
        logger.error(f"{resource_name} 在 {max_attempts * delay} 秒后仍未就绪")
        return False
    
    def tag_resource(self, client: Any, resource_arn: str, tags: Dict[str, str]) -> bool:
        """为资源添加标签"""
        try:
            tag_list = [{'Key': k, 'Value': v} for k, v in tags.items()]
            
            # 根据不同的服务使用不同的标签方法
            if hasattr(client, 'tag_resource'):
                client.tag_resource(ResourceArn=resource_arn, Tags=tag_list)
            elif hasattr(client, 'add_tags_to_resource'):
                client.add_tags_to_resource(ResourceArn=resource_arn, Tags=tag_list)
            else:
                logger.warning(f"无法为资源添加标签: {resource_arn}")
                return False
            
            logger.info(f"已为资源添加标签: {resource_arn}")
            return True
        except Exception as e:
            logger.error(f"添加标签失败: {str(e)}")
            return False
    
    def create_or_update_ssm_parameter(self, name: str, value: str, 
                                      description: str = "", secure: bool = False) -> bool:
        """创建或更新SSM参数"""
        try:
            ssm = boto3.client('ssm', region_name=self.region)
            
            ssm.put_parameter(
                Name=name,
                Value=value,
                Description=description,
                Type='SecureString' if secure else 'String',
                Overwrite=True
            )
            
            logger.info(f"SSM参数已创建/更新: {name}")
            return True
        except Exception as e:
            logger.error(f"创建/更新SSM参数失败: {str(e)}")
            return False
    
    def check_service_availability(self, service_name: str) -> bool:
        """检查AWS服务在当前区域是否可用"""
        try:
            session = boto3.Session(region_name=self.region)
            available_services = session.get_available_services()
            
            if service_name in available_services:
                logger.info(f"服务 {service_name} 在区域 {self.region} 可用")
                return True
            else:
                logger.warning(f"服务 {service_name} 在区域 {self.region} 不可用")
                return False
        except Exception as e:
            logger.error(f"检查服务可用性失败: {str(e)}")
            return False
    
    def estimate_costs(self, resources: Dict[str, Any]) -> Dict[str, float]:
        """估算资源成本（简化版）"""
        # 这是一个简化的成本估算，实际成本会有所不同
        cost_estimates = {
            'iot_core': {
                'base': 0.0,  # IoT Core按消息计费
                'per_million_messages': 1.0
            },
            's3': {
                'storage_per_gb': 0.023,  # Standard存储
                'requests_per_1000': 0.0004
            },
            'lambda': {
                'per_million_requests': 0.20,
                'per_gb_second': 0.0000166667
            },
            'timestream': {
                'writes_per_million': 0.50,
                'storage_per_gb_month': 0.30,
                'queries_per_gb_scanned': 0.01
            },
            'emr': {
                'per_hour': {
                    'm5.xlarge': 0.192  # 按需价格
                }
            }
        }
        
        monthly_estimate = {
            'iot_messages': 10.0,  # 假设每月1000万条消息
            's3_storage': 2.3,     # 假设100GB存储
            'lambda_compute': 5.0,  # 假设适量调用
            'timestream': 15.0,    # 写入和存储
            'emr': 0.0,           # 未启动
            'total': 32.3
        }
        
        logger.info("成本估算（每月USD）:")
        for service, cost in monthly_estimate.items():
            logger.info(f"  {service}: ${cost:.2f}")
        
        return monthly_estimate


class IoTDeviceHelper:
    """IoT设备管理辅助类"""
    
    def __init__(self, iot_client, region: str):
        self.iot = iot_client
        self.region = region
    
    def create_thing_with_certificate(self, thing_name: str, thing_type: str, 
                                    policy_name: str, attributes: Dict[str, str]) -> Dict[str, str]:
        """创建Thing并生成证书"""
        try:
            # 创建Thing
            thing_response = self.iot.create_thing(
                thingName=thing_name,
                thingTypeName=thing_type,
                attributePayload={'attributes': attributes}
            )
            
            # 创建证书
            cert_response = self.iot.create_keys_and_certificate(setAsActive=True)
            
            # 附加策略到证书
            self.iot.attach_policy(
                policyName=policy_name,
                target=cert_response['certificateArn']
            )
            
            # 附加证书到Thing
            self.iot.attach_thing_principal(
                thingName=thing_name,
                principal=cert_response['certificateArn']
            )
            
            logger.info(f"创建Thing和证书: {thing_name}")
            
            return {
                'thingArn': thing_response['thingArn'],
                'certificateArn': cert_response['certificateArn'],
                'certificateId': cert_response['certificateId'],
                'certificatePem': cert_response['certificatePem'],
                'privateKey': cert_response['keyPair']['PrivateKey'],
                'publicKey': cert_response['keyPair']['PublicKey']
            }
            
        except Exception as e:
            logger.error(f"创建Thing失败: {str(e)}")
            raise
    
    def update_device_shadow(self, thing_name: str, desired_state: Dict[str, Any]) -> bool:
        """更新设备影子"""
        try:
            iot_data = boto3.client('iot-data', region_name=self.region)
            
            payload = {
                'state': {
                    'desired': desired_state
                }
            }
            
            iot_data.update_thing_shadow(
                thingName=thing_name,
                payload=json.dumps(payload)
            )
            
            logger.info(f"更新设备影子: {thing_name}")
            return True
            
        except Exception as e:
            logger.error(f"更新设备影子失败: {str(e)}")
            return False


class S3Helper:
    """S3操作辅助类"""
    
    def __init__(self, s3_client):
        self.s3 = s3_client
    
    def upload_file_to_s3(self, file_path: str, bucket: str, key: str, 
                         metadata: Optional[Dict[str, str]] = None) -> bool:
        """上传文件到S3"""
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
            
            self.s3.upload_file(file_path, bucket, key, ExtraArgs=extra_args)
            logger.info(f"文件已上传到 s3://{bucket}/{key}")
            return True
            
        except Exception as e:
            logger.error(f"上传文件失败: {str(e)}")
            return False
    
    def create_presigned_url(self, bucket: str, key: str, 
                           expiration: int = 3600) -> Optional[str]:
        """生成预签名URL"""
        try:
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"生成预签名URL失败: {str(e)}")
            return None


class CloudWatchHelper:
    """CloudWatch监控辅助类"""
    
    def __init__(self, region: str):
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.logs = boto3.client('logs', region_name=region)
    
    def create_log_group(self, log_group_name: str, retention_days: int = 30) -> bool:
        """创建日志组"""
        try:
            self.logs.create_log_group(logGroupName=log_group_name)
            
            # 设置保留期
            self.logs.put_retention_policy(
                logGroupName=log_group_name,
                retentionInDays=retention_days
            )
            
            logger.info(f"创建日志组: {log_group_name}")
            return True
            
        except self.logs.exceptions.ResourceAlreadyExistsException:
            logger.info(f"日志组已存在: {log_group_name}")
            return True
        except Exception as e:
            logger.error(f"创建日志组失败: {str(e)}")
            return False
    
    def create_metric_alarm(self, alarm_name: str, metric_name: str, 
                          namespace: str, threshold: float,
                          comparison_operator: str = 'GreaterThanThreshold',
                          evaluation_periods: int = 1,
                          datapoints_to_alarm: int = 1) -> bool:
        """创建CloudWatch告警"""
        try:
            self.cloudwatch.put_metric_alarm(
                AlarmName=alarm_name,
                ComparisonOperator=comparison_operator,
                EvaluationPeriods=evaluation_periods,
                MetricName=metric_name,
                Namespace=namespace,
                Period=300,  # 5分钟
                Statistic='Average',
                Threshold=threshold,
                ActionsEnabled=True,
                AlarmDescription=f'Alarm for {metric_name}',
                DatapointsToAlarm=datapoints_to_alarm
            )
            
            logger.info(f"创建告警: {alarm_name}")
            return True
            
        except Exception as e:
            logger.error(f"创建告警失败: {str(e)}")
            return False


def validate_aws_credentials() -> bool:
    """验证AWS凭证"""
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        logger.info(f"AWS凭证有效 - 账户: {identity['Account']}, 用户: {identity['Arn']}")
        return True
    except Exception as e:
        logger.error(f"AWS凭证无效: {str(e)}")
        return False


def get_resource_arn(service: str, region: str, account_id: str, 
                    resource_type: str, resource_name: str) -> str:
    """构建资源ARN"""
    return f"arn:aws:{service}:{region}:{account_id}:{resource_type}/{resource_name}"


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全地解析JSON"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"JSON解析失败，返回默认值: {default}")
        return default


def retry_with_backoff(func, max_retries: int = 3, backoff_factor: float = 2.0):
    """带退避的重试装饰器"""
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                if e.response['Error']['Code'] in ['ThrottlingException', 'TooManyRequestsException']:
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor ** attempt
                        logger.warning(f"请求被限流，等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        continue
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"操作失败，重试 {attempt + 1}/{max_retries}: {str(e)}")
                    time.sleep(backoff_factor ** attempt)
                    continue
                raise
        
        raise Exception(f"操作在 {max_retries} 次重试后失败")
    
    return wrapper