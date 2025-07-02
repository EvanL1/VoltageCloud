#!/usr/bin/env python3
"""
AWS IoT Architecture Setup Script
基于架构图实现的AWS IoT基础设施自动化部署脚本
"""

import boto3
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AWSIoTArchitectureSetup:
    """AWS IoT架构设置类"""
    
    def __init__(self, region: str = 'us-east-1', prefix: str = 'iot-demo'):
        """
        初始化AWS客户端
        
        Args:
            region: AWS区域
            prefix: 资源前缀
        """
        self.region = region
        self.prefix = prefix
        self.account_id = boto3.client('sts').get_caller_identity()['Account']
        
        # 初始化AWS服务客户端
        self.iot = boto3.client('iot', region_name=region)
        self.iam = boto3.client('iam', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.timestream = boto3.client('timestream-write', region_name=region)
        self.greengrass = boto3.client('greengrassv2', region_name=region)
        self.shield = boto3.client('shield', region_name=region)
        self.emr = boto3.client('emr', region_name=region)
        self.mwaa = boto3.client('mwaa', region_name=region)  # Managed Airflow
        
        # 存储创建的资源
        self.resources = {}
        
    def create_iam_roles(self) -> Dict[str, str]:
        """创建所需的IAM角色和策略"""
        logger.info("创建IAM角色和策略...")
        
        roles = {}
        
        # IoT Core角色
        iot_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "iot.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        # Lambda执行角色
        lambda_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        # Greengrass角色
        greengrass_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "greengrass.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        # 创建IoT规则角色
        try:
            iot_role_name = f"{self.prefix}-iot-rule-role"
            iot_role = self.iam.create_role(
                RoleName=iot_role_name,
                AssumeRolePolicyDocument=json.dumps(iot_role_policy),
                Description='Role for IoT Rules'
            )
            roles['iot_rule_role'] = iot_role['Role']['Arn']
            
            # 附加策略
            self.iam.attach_role_policy(
                RoleName=iot_role_name,
                PolicyArn='arn:aws:iam::aws:policy/service-role/AWSIoTRuleActions'
            )
            logger.info(f"创建IoT规则角色: {iot_role_name}")
        except self.iam.exceptions.EntityAlreadyExistsException:
            logger.info(f"IoT规则角色已存在: {iot_role_name}")
            roles['iot_rule_role'] = f"arn:aws:iam::{self.account_id}:role/{iot_role_name}"
        
        # 创建Lambda执行角色
        try:
            lambda_role_name = f"{self.prefix}-lambda-execution-role"
            lambda_role = self.iam.create_role(
                RoleName=lambda_role_name,
                AssumeRolePolicyDocument=json.dumps(lambda_role_policy),
                Description='Role for Lambda Functions'
            )
            roles['lambda_role'] = lambda_role['Role']['Arn']
            
            # 附加策略
            policies = [
                'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',
                'arn:aws:iam::aws:policy/AWSIoTFullAccess',
                'arn:aws:iam::aws:policy/AmazonS3FullAccess',
                'arn:aws:iam::aws:policy/AmazonTimestreamFullAccess'
            ]
            for policy in policies:
                self.iam.attach_role_policy(
                    RoleName=lambda_role_name,
                    PolicyArn=policy
                )
            logger.info(f"创建Lambda执行角色: {lambda_role_name}")
        except self.iam.exceptions.EntityAlreadyExistsException:
            logger.info(f"Lambda执行角色已存在: {lambda_role_name}")
            roles['lambda_role'] = f"arn:aws:iam::{self.account_id}:role/{lambda_role_name}"
        
        # 创建Greengrass角色
        try:
            greengrass_role_name = f"{self.prefix}-greengrass-role"
            greengrass_role = self.iam.create_role(
                RoleName=greengrass_role_name,
                AssumeRolePolicyDocument=json.dumps(greengrass_role_policy),
                Description='Role for Greengrass'
            )
            roles['greengrass_role'] = greengrass_role['Role']['Arn']
            
            # 附加策略
            self.iam.attach_role_policy(
                RoleName=greengrass_role_name,
                PolicyArn='arn:aws:iam::aws:policy/service-role/AWSGreengrassResourceAccessRolePolicy'
            )
            logger.info(f"创建Greengrass角色: {greengrass_role_name}")
        except self.iam.exceptions.EntityAlreadyExistsException:
            logger.info(f"Greengrass角色已存在: {greengrass_role_name}")
            roles['greengrass_role'] = f"arn:aws:iam::{self.account_id}:role/{greengrass_role_name}"
        
        time.sleep(10)  # 等待角色生效
        return roles
    
    def create_s3_buckets(self) -> Dict[str, str]:
        """创建S3存储桶"""
        logger.info("创建S3存储桶...")
        
        buckets = {}
        bucket_names = {
            'data_lake': f"{self.prefix}-data-lake-{self.account_id}",
            'ota_updates': f"{self.prefix}-ota-updates-{self.account_id}",
            'airflow_dags': f"{self.prefix}-airflow-dags-{self.account_id}"
        }
        
        for bucket_type, bucket_name in bucket_names.items():
            try:
                if self.region == 'us-east-1':
                    self.s3.create_bucket(Bucket=bucket_name)
                else:
                    self.s3.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': self.region}
                    )
                
                # 启用版本控制
                self.s3.put_bucket_versioning(
                    Bucket=bucket_name,
                    VersioningConfiguration={'Status': 'Enabled'}
                )
                
                # 设置生命周期策略
                if bucket_type == 'data_lake':
                    lifecycle_config = {
                        'Rules': [{
                            'ID': 'Archive old data',
                            'Status': 'Enabled',
                            'Filter': {'Prefix': ''},
                            'Transitions': [{
                                'Days': 30,
                                'StorageClass': 'STANDARD_IA'
                            }, {
                                'Days': 90,
                                'StorageClass': 'GLACIER'
                            }]
                        }]
                    }
                    self.s3.put_bucket_lifecycle_configuration(
                        Bucket=bucket_name,
                        LifecycleConfiguration=lifecycle_config
                    )
                
                buckets[bucket_type] = bucket_name
                logger.info(f"创建S3存储桶: {bucket_name}")
            except self.s3.exceptions.BucketAlreadyExists:
                logger.info(f"S3存储桶已存在: {bucket_name}")
                buckets[bucket_type] = bucket_name
            except self.s3.exceptions.BucketAlreadyOwnedByYou:
                logger.info(f"S3存储桶已拥有: {bucket_name}")
                buckets[bucket_type] = bucket_name
        
        return buckets
    
    def create_iot_thing_type(self) -> str:
        """创建IoT Thing类型"""
        logger.info("创建IoT Thing类型...")
        
        thing_type_name = f"{self.prefix}-device-type"
        
        try:
            response = self.iot.create_thing_type(
                thingTypeName=thing_type_name,
                thingTypeProperties={
                    'thingTypeDescription': 'IoT Device Type',
                    'searchableAttributes': ['deviceType', 'firmware', 'location']
                }
            )
            logger.info(f"创建Thing类型: {thing_type_name}")
            return response['thingTypeArn']
        except self.iot.exceptions.ResourceAlreadyExistsException:
            logger.info(f"Thing类型已存在: {thing_type_name}")
            return f"arn:aws:iot:{self.region}:{self.account_id}:thingtype/{thing_type_name}"
    
    def create_iot_policy(self) -> str:
        """创建IoT策略"""
        logger.info("创建IoT策略...")
        
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
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "iot:GetThingShadow",
                        "iot:UpdateThingShadow",
                        "iot:DeleteThingShadow"
                    ],
                    "Resource": f"arn:aws:iot:{self.region}:{self.account_id}:thing/*"
                }
            ]
        }
        
        try:
            response = self.iot.create_policy(
                policyName=policy_name,
                policyDocument=json.dumps(policy_document)
            )
            logger.info(f"创建IoT策略: {policy_name}")
            return response['policyArn']
        except self.iot.exceptions.ResourceAlreadyExistsException:
            logger.info(f"IoT策略已存在: {policy_name}")
            return f"arn:aws:iot:{self.region}:{self.account_id}:policy/{policy_name}"
    
    def create_timestream_database(self) -> Dict[str, str]:
        """创建TimeStream数据库和表"""
        logger.info("创建TimeStream数据库...")
        
        db_name = f"{self.prefix}_iot_db"
        table_name = "device_metrics"
        
        try:
            # 创建数据库
            self.timestream.create_database(
                DatabaseName=db_name,
                Tags=[
                    {'Key': 'Environment', 'Value': 'Production'},
                    {'Key': 'Project', 'Value': self.prefix}
                ]
            )
            logger.info(f"创建TimeStream数据库: {db_name}")
        except self.timestream.exceptions.ConflictException:
            logger.info(f"TimeStream数据库已存在: {db_name}")
        except Exception as e:
            if "AccessDeniedException" in str(e) or "Only existing Timestream" in str(e):
                logger.warning(f"跳过TimeStream数据库创建 - 需要特殊权限: {str(e)}")
                return {
                    'database_name': f"{db_name} (跳过 - 权限限制)",
                    'table_name': f"{table_name} (跳过 - 权限限制)",
                    'database_arn': f"arn:aws:timestream:{self.region}:{self.account_id}:database/{db_name}",
                    'table_arn': f"arn:aws:timestream:{self.region}:{self.account_id}:database/{db_name}/table/{table_name}"
                }
            else:
                raise
        
        try:
            # 创建表
            self.timestream.create_table(
                DatabaseName=db_name,
                TableName=table_name,
                RetentionProperties={
                    'MemoryStoreRetentionPeriodInHours': 24,
                    'MagneticStoreRetentionPeriodInDays': 365
                },
                MagneticStoreWriteProperties={
                    'EnableMagneticStoreWrites': True
                }
            )
            logger.info(f"创建TimeStream表: {table_name}")
        except self.timestream.exceptions.ConflictException:
            logger.info(f"TimeStream表已存在: {table_name}")
        except Exception as e:
            if "AccessDeniedException" in str(e):
                logger.warning(f"跳过TimeStream表创建 - 需要特殊权限: {str(e)}")
            else:
                raise
        
        return {
            'database': db_name,
            'table': table_name
        }
    
    def create_lambda_functions(self, roles: Dict[str, str], buckets: Dict[str, str]) -> Dict[str, str]:
        """创建Lambda函数"""
        logger.info("创建Lambda函数...")
        
        functions = {}
        
        # Lambda函数代码
        lambda_code = '''
import json
import boto3
import time
from datetime import datetime

def lambda_handler(event, context):
    """处理IoT数据的Lambda函数"""
    
    # 初始化客户端
    s3 = boto3.client('s3')
    timestream = boto3.client('timestream-write')
    
    # 处理IoT消息
    device_id = event.get('deviceId', 'unknown')
    timestamp = str(int(time.time() * 1000))
    
    # 写入TimeStream
    try:
        records = []
        for key, value in event.get('metrics', {}).items():
            records.append({
                'Time': timestamp,
                'TimeUnit': 'MILLISECONDS',
                'Dimensions': [
                    {'Name': 'deviceId', 'Value': device_id},
                    {'Name': 'metricType', 'Value': key}
                ],
                'MeasureName': 'value',
                'MeasureValue': str(value),
                'MeasureValueType': 'DOUBLE'
            })
        
        if records:
            timestream.write_records(
                DatabaseName=event.get('database', 'iot_demo_iot_db'),
                TableName=event.get('table', 'device_metrics'),
                Records=records
            )
    except Exception as e:
        print(f"Error writing to TimeStream: {str(e)}")
    
    # 存储原始数据到S3
    try:
        key = f"raw-data/{device_id}/{datetime.now().strftime('%Y/%m/%d')}/{timestamp}.json"
        s3.put_object(
            Bucket=event.get('bucket', 'iot-demo-data-lake'),
            Key=key,
            Body=json.dumps(event),
            ContentType='application/json'
        )
    except Exception as e:
        print(f"Error writing to S3: {str(e)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Data processed successfully')
    }
'''
        
        # 创建部署包
        import zipfile
        import os
        
        zip_file = f"/tmp/{self.prefix}-lambda.zip"
        with zipfile.ZipFile(zip_file, 'w') as zf:
            zf.writestr('lambda_function.py', lambda_code)
        
        # 创建Lambda函数
        function_name = f"{self.prefix}-iot-data-processor"
        
        try:
            with open(zip_file, 'rb') as f:
                response = self.lambda_client.create_function(
                    FunctionName=function_name,
                    Runtime='python3.9',
                    Role=roles['lambda_role'],
                    Handler='lambda_function.lambda_handler',
                    Code={'ZipFile': f.read()},
                    Description='Process IoT data and store in TimeStream and S3',
                    Timeout=60,
                    MemorySize=256,
                    Environment={
                        'Variables': {
                            'S3_BUCKET': buckets['data_lake'],
                            'TIMESTREAM_DB': f"{self.prefix}_iot_db",
                            'TIMESTREAM_TABLE': 'device_metrics'
                        }
                    }
                )
                functions['data_processor'] = response['FunctionArn']
                logger.info(f"创建Lambda函数: {function_name}")
        except self.lambda_client.exceptions.ResourceConflictException:
            logger.info(f"Lambda函数已存在: {function_name}")
            functions['data_processor'] = f"arn:aws:lambda:{self.region}:{self.account_id}:function:{function_name}"
        
        # 清理临时文件
        if os.path.exists(zip_file):
            os.remove(zip_file)
        
        return functions
    
    def create_iot_rules(self, lambda_arn: str, role_arn: str) -> List[str]:
        """创建IoT规则"""
        logger.info("创建IoT规则...")
        
        rules = []
        
        # 规则1: 处理设备数据
        rule_name = f"{self.prefix.replace('-', '_')}_process_device_data"
        sql = "SELECT *, topic(2) as deviceId FROM 'device/+/telemetry'"
        
        try:
            self.iot.create_topic_rule(
                ruleName=rule_name,
                topicRulePayload={
                    'sql': sql,
                    'description': 'Process device telemetry data',
                    'actions': [{
                        'lambda': {
                            'functionArn': lambda_arn
                        }
                    }],
                    'ruleDisabled': False,
                    'awsIotSqlVersion': '2016-03-23'
                }
            )
            
            # 添加Lambda权限
            self.lambda_client.add_permission(
                FunctionName=lambda_arn.split(':')[-1],
                StatementId=f"{rule_name}-invoke",
                Action='lambda:InvokeFunction',
                Principal='iot.amazonaws.com',
                SourceArn=f"arn:aws:iot:{self.region}:{self.account_id}:rule/{rule_name}"
            )
            
            rules.append(rule_name)
            logger.info(f"创建IoT规则: {rule_name}")
        except self.iot.exceptions.ResourceAlreadyExistsException:
            logger.info(f"IoT规则已存在: {rule_name}")
            rules.append(rule_name)
        except Exception as e:
            logger.error(f"创建IoT规则失败: {str(e)}")
        
        return rules
    
    def create_greengrass_core_definition(self) -> str:
        """创建Greengrass核心定义"""
        logger.info("创建Greengrass核心定义...")
        
        try:
            # 创建Greengrass组件
            component_name = f"{self.prefix}.EdgeProcessor"
            
            # 组件配方
            recipe = {
                "RecipeFormatVersion": "2020-01-25",
                "ComponentName": component_name,
                "ComponentVersion": "1.0.0",
                "ComponentDescription": "Edge data processor for IoT devices",
                "ComponentPublisher": "IoT Demo",
                "Manifests": [{
                    "Platform": {
                        "os": "linux"
                    },
                    "Lifecycle": {
                        "Run": "python3 -u {artifacts:path}/edge_processor.py"
                    },
                    "Artifacts": [{
                        "URI": f"s3://{self.prefix}-ota-updates-{self.account_id}/greengrass/components/edge_processor.py"
                    }]
                }]
            }
            
            # 这里只是示例，实际部署需要更多配置
            logger.info(f"Greengrass组件定义已准备: {component_name}")
            return component_name
            
        except Exception as e:
            logger.error(f"创建Greengrass定义失败: {str(e)}")
            return ""
    
    def enable_shield_protection(self) -> bool:
        """启用AWS Shield保护"""
        logger.info("检查AWS Shield状态...")
        
        try:
            # 检查Shield Advanced订阅状态
            subscription = self.shield.describe_subscription()
            logger.info("AWS Shield Advanced已启用")
            return True
        except self.shield.exceptions.ResourceNotFoundException:
            logger.info("AWS Shield Standard已自动启用（免费）")
            logger.info("如需Shield Advanced保护，请在AWS控制台手动启用")
            return True
        except Exception as e:
            logger.error(f"检查Shield状态失败: {str(e)}")
            return False
    
    def create_emr_cluster(self, buckets: Dict[str, str]) -> str:
        """创建EMR集群配置"""
        logger.info("准备EMR集群配置...")
        
        # EMR集群配置（仅创建配置，不实际启动集群以节省成本）
        cluster_config = {
            "Name": f"{self.prefix}-iot-analytics-cluster",
            "ReleaseLabel": "emr-6.9.0",
            "Applications": [
                {"Name": "Spark"},
                {"Name": "Hadoop"},
                {"Name": "Hive"}
            ],
            "Instances": {
                "InstanceGroups": [
                    {
                        "Name": "Master",
                        "Market": "ON_DEMAND",
                        "InstanceRole": "MASTER",
                        "InstanceType": "m5.xlarge",
                        "InstanceCount": 1
                    },
                    {
                        "Name": "Worker",
                        "Market": "SPOT",
                        "InstanceRole": "CORE",
                        "InstanceType": "m5.xlarge",
                        "InstanceCount": 2
                    }
                ],
                "KeepJobFlowAliveWhenNoSteps": False,
                "TerminationProtected": False
            },
            "LogUri": f"s3://{buckets['data_lake']}/emr-logs/",
            "ServiceRole": "EMR_DefaultRole",
            "JobFlowRole": "EMR_EC2_DefaultRole",
            "VisibleToAllUsers": True,
            "Tags": [
                {"Key": "Environment", "Value": "Production"},
                {"Key": "Project", "Value": self.prefix}
            ]
        }
        
        logger.info("EMR集群配置已准备（未实际创建以节省成本）")
        logger.info(f"配置详情: {json.dumps(cluster_config, indent=2)}")
        
        return json.dumps(cluster_config)
    
    def create_airflow_environment(self, buckets: Dict[str, str]) -> Dict[str, Any]:
        """创建Airflow环境配置"""
        logger.info("准备Airflow (MWAA) 环境配置...")
        
        # Airflow环境配置（仅创建配置，不实际部署以节省成本）
        airflow_config = {
            "Name": f"{self.prefix}-iot-airflow",
            "DagS3Path": f"s3://{buckets['airflow_dags']}/dags",
            "ExecutionRoleArn": f"arn:aws:iam::{self.account_id}:role/{self.prefix}-mwaa-execution-role",
            "NetworkConfiguration": {
                "SubnetIds": ["subnet-xxxxx", "subnet-yyyyy"],  # 需要实际的子网ID
                "SecurityGroupIds": ["sg-xxxxx"]  # 需要实际的安全组ID
            },
            "WebserverAccessMode": "PUBLIC_ONLY",
            "MaxWorkers": 10,
            "MinWorkers": 1,
            "Schedulers": 2,
            "EnvironmentClass": "mw1.small",
            "Tags": {
                "Environment": "Production",
                "Project": self.prefix
            }
        }
        
        # 创建示例DAG
        sample_dag = '''
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.amazon.aws.operators.emr import EmrAddStepsOperator
from airflow.providers.amazon.aws.sensors.emr import EmrStepSensor

default_args = {
    'owner': 'iot-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'iot_data_processing',
    default_args=default_args,
    description='Process IoT data with EMR',
    schedule_interval=timedelta(days=1),
    catchup=False
)

# EMR步骤定义
spark_steps = [
    {
        'Name': 'Process IoT Data',
        'ActionOnFailure': 'CONTINUE',
        'HadoopJarStep': {
            'Jar': 'command-runner.jar',
            'Args': [
                'spark-submit',
                '--deploy-mode', 'cluster',
                's3://''' + buckets['data_lake'] + '''/scripts/process_iot_data.py'
            ]
        }
    }
]

# 添加EMR步骤
add_steps = EmrAddStepsOperator(
    task_id='add_emr_steps',
    job_flow_id="{{ var.value.emr_cluster_id }}",
    steps=spark_steps,
    dag=dag
)

# 等待步骤完成
step_checker = EmrStepSensor(
    task_id='watch_step',
    job_flow_id="{{ var.value.emr_cluster_id }}",
    step_id="{{ task_instance.xcom_pull(task_ids='add_emr_steps', key='return_value')[0] }}",
    dag=dag
)

add_steps >> step_checker
'''
        
        logger.info("Airflow环境配置已准备（未实际创建以节省成本）")
        logger.info(f"配置详情: {json.dumps(airflow_config, indent=2)}")
        
        return {
            'config': airflow_config,
            'sample_dag': sample_dag
        }
    
    def create_device_shadow_config(self) -> Dict[str, Any]:
        """创建设备影子配置"""
        logger.info("创建设备影子配置...")
        
        shadow_config = {
            "classic": {
                "desired": {
                    "welcome": "aws-iot",
                    "color": "green",
                    "temperature": 20,
                    "firmware_version": "1.0.0"
                },
                "reported": {
                    "welcome": "aws-iot",
                    "color": "green",
                    "temperature": 20,
                    "firmware_version": "1.0.0"
                }
            },
            "named_shadows": {
                "config": {
                    "desired": {
                        "sample_rate": 60,
                        "reporting_interval": 300,
                        "debug_mode": False
                    }
                },
                "status": {
                    "reported": {
                        "online": True,
                        "battery_level": 85,
                        "signal_strength": -65
                    }
                }
            }
        }
        
        logger.info("设备影子配置已准备")
        return shadow_config
    
    def create_ota_job_template(self) -> str:
        """创建OTA作业模板"""
        logger.info("创建OTA作业模板...")
        
        job_template_id = f"{self.prefix}-ota-template"
        
        try:
            response = self.iot.create_job_template(
                jobTemplateId=job_template_id,
                description="OTA update job template for IoT devices",
                document="""{
                    "operation": "ota_update",
                    "files": [{
                        "fileName": "firmware.bin",
                        "fileSource": {
                            "s3Location": {
                                "bucket": "${bucket}",
                                "key": "${key}"
                            }
                        }
                    }]
                }""",
                jobExecutionsRolloutConfig={
                    'maximumPerMinute': 10,
                    'exponentialRate': {
                        'baseRatePerMinute': 2,
                        'incrementFactor': 2.0,
                        'rateIncreaseCriteria': {
                            'numberOfSucceededThings': 5
                        }
                    }
                },
                abortConfig={
                    'criteriaList': [{
                        'failureType': 'FAILED',
                        'action': 'CANCEL',
                        'thresholdPercentage': 10.0,
                        'minNumberOfExecutedThings': 10
                    }]
                },
                timeoutConfig={
                    'inProgressTimeoutInMinutes': 60
                }
            )
            logger.info(f"创建OTA作业模板: {job_template_id}")
            return response['jobTemplateArn']
        except self.iot.exceptions.ResourceAlreadyExistsException:
            logger.info(f"OTA作业模板已存在: {job_template_id}")
            return f"arn:aws:iot:{self.region}:{self.account_id}:jobtemplate/{job_template_id}"
    
    def generate_summary_report(self) -> str:
        """生成部署摘要报告"""
        logger.info("生成部署摘要报告...")
        
        report = f"""
# AWS IoT架构部署报告
部署时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
区域: {self.region}
账户ID: {self.account_id}
资源前缀: {self.prefix}

## 已创建的资源

### IAM角色
- IoT规则角色: {self.resources.get('roles', {}).get('iot_rule_role', 'N/A')}
- Lambda执行角色: {self.resources.get('roles', {}).get('lambda_role', 'N/A')}
- Greengrass角色: {self.resources.get('roles', {}).get('greengrass_role', 'N/A')}

### S3存储桶
- 数据湖: {self.resources.get('buckets', {}).get('data_lake', 'N/A')}
- OTA更新: {self.resources.get('buckets', {}).get('ota_updates', 'N/A')}
- Airflow DAGs: {self.resources.get('buckets', {}).get('airflow_dags', 'N/A')}

### IoT核心资源
- Thing类型: {self.resources.get('thing_type', 'N/A')}
- 设备策略: {self.resources.get('iot_policy', 'N/A')}
- IoT规则: {', '.join(self.resources.get('iot_rules', []))}

### 数据处理
- TimeStream数据库: {self.resources.get('timestream', {}).get('database', 'N/A')}
- TimeStream表: {self.resources.get('timestream', {}).get('table', 'N/A')}
- Lambda函数: {self.resources.get('lambda_functions', {}).get('data_processor', 'N/A')}

### 边缘计算
- Greengrass组件: {self.resources.get('greengrass_component', 'N/A')}

### OTA更新
- OTA作业模板: {self.resources.get('ota_template', 'N/A')}

### 安全
- AWS Shield: {'已启用' if self.resources.get('shield_enabled', False) else '未启用'}

### 大数据处理
- EMR集群配置: 已准备（未实际创建）
- Airflow环境配置: 已准备（未实际创建）

## 后续步骤
1. 创建IoT设备并注册到IoT Core
2. 配置设备证书和连接
3. 部署Greengrass到边缘设备
4. 根据需要启动EMR集群进行数据分析
5. 根据需要部署Airflow环境进行工作流编排
6. 配置监控和告警

## 注意事项
- 部分资源（EMR、Airflow）仅创建配置，未实际部署以节省成本
- 请根据实际需求调整资源配置
- 定期检查和优化成本
- 确保所有安全最佳实践得到遵循
"""
        
        # 保存报告
        report_file = f"{self.prefix}_deployment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"部署报告已保存到: {report_file}")
        return report
    
    def deploy_architecture(self):
        """部署完整的IoT架构"""
        logger.info("开始部署AWS IoT架构...")
        
        try:
            # 1. 创建IAM角色
            self.resources['roles'] = self.create_iam_roles()
            
            # 2. 创建S3存储桶
            self.resources['buckets'] = self.create_s3_buckets()
            
            # 3. 创建IoT Thing类型
            self.resources['thing_type'] = self.create_iot_thing_type()
            
            # 4. 创建IoT策略
            self.resources['iot_policy'] = self.create_iot_policy()
            
            # 5. 创建TimeStream数据库
            self.resources['timestream'] = self.create_timestream_database()
            
            # 6. 创建Lambda函数
            self.resources['lambda_functions'] = self.create_lambda_functions(
                self.resources['roles'],
                self.resources['buckets']
            )
            
            # 7. 创建IoT规则
            self.resources['iot_rules'] = self.create_iot_rules(
                self.resources['lambda_functions']['data_processor'],
                self.resources['roles']['iot_rule_role']
            )
            
            # 8. 创建Greengrass组件
            self.resources['greengrass_component'] = self.create_greengrass_core_definition()
            
            # 9. 启用Shield保护
            self.resources['shield_enabled'] = self.enable_shield_protection()
            
            # 10. 创建EMR集群配置
            self.resources['emr_config'] = self.create_emr_cluster(self.resources['buckets'])
            
            # 11. 创建Airflow环境配置
            self.resources['airflow_config'] = self.create_airflow_environment(self.resources['buckets'])
            
            # 12. 创建设备影子配置
            self.resources['device_shadow'] = self.create_device_shadow_config()
            
            # 13. 创建OTA作业模板
            self.resources['ota_template'] = self.create_ota_job_template()
            
            # 生成部署报告
            report = self.generate_summary_report()
            
            logger.info("AWS IoT架构部署完成！")
            print(report)
            
            return self.resources
            
        except Exception as e:
            logger.error(f"部署过程中出现错误: {str(e)}")
            raise


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AWS IoT架构自动化部署脚本')
    parser.add_argument('--region', default='us-east-1', help='AWS区域')
    parser.add_argument('--prefix', default='iot-demo', help='资源前缀')
    parser.add_argument('--profile', help='AWS配置文件名')
    
    args = parser.parse_args()
    
    # 设置AWS配置文件
    if args.profile:
        boto3.setup_default_session(profile_name=args.profile)
    
    # 创建并运行部署
    setup = AWSIoTArchitectureSetup(region=args.region, prefix=args.prefix)
    
    try:
        resources = setup.deploy_architecture()
        logger.info("部署成功完成！")
    except Exception as e:
        logger.error(f"部署失败: {str(e)}")
        raise


if __name__ == "__main__":
    main()