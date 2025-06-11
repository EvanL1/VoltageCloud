"""
Infrastructure tests for IoT platform CDK stacks
Tests resource creation, configuration, and dependencies
"""

import pytest
import aws_cdk as cdk
from aws_cdk.assertions import Template, Match
from iot_poc.iot_poc_stack import IotPocStack
from iot_poc.device_shadow_stack import DeviceShadowStack
from iot_poc.auth_stack import AuthStack
from iot_poc.ecs_api_stack import EcsApiStack
from iot_poc.ota_stack import OtaStack
from iot_poc.data_lake_stack import DataLakeStack


class TestIotPocStack:
    """Test IoT core data processing stack"""
    
    def test_sqs_queue_creation(self, cdk_app):
        """Test SQS queue is created with correct configuration"""
        stack = IotPocStack(cdk_app, "TestIotPocStack")
        template = Template.from_stack(stack)
        
        # Verify SQS queue exists
        template.has_resource_properties("AWS::SQS::Queue", {
            "MessageRetentionPeriod": 1209600,  # 14 days
            "VisibilityTimeoutSeconds": 300
        })
        
        # Verify DLQ exists
        template.has_resource_properties("AWS::SQS::Queue", {
            "MessageRetentionPeriod": 1209600
        })
    
    def test_lambda_function_creation(self, cdk_app):
        """Test Lambda function is created with correct configuration"""
        stack = IotPocStack(cdk_app, "TestIotPocStack")
        template = Template.from_stack(stack)
        
        # Verify Lambda function exists
        template.has_resource_properties("AWS::Lambda::Function", {
            "Runtime": "provided.al2",
            "Handler": "bootstrap",
            "Timeout": 300
        })
    
    def test_timestream_database_creation(self, cdk_app):
        """Test TimeStream database and table creation"""
        stack = IotPocStack(cdk_app, "TestIotPocStack")
        template = Template.from_stack(stack)
        
        # Verify TimeStream database
        template.has_resource_properties("AWS::Timestream::Database", {
            "DatabaseName": Match.string_like_regexp("IoTDatabase.*")
        })
        
        # Verify TimeStream table
        template.has_resource_properties("AWS::Timestream::Table", {
            "TableName": Match.string_like_regexp("IoTTable.*")
        })
    
    def test_s3_bucket_creation(self, cdk_app):
        """Test S3 bucket creation with proper configuration"""
        stack = IotPocStack(cdk_app, "TestIotPocStack")
        template = Template.from_stack(stack)
        
        # Verify S3 bucket exists with encryption
        template.has_resource_properties("AWS::S3::Bucket", {
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {
                        "ServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }
                ]
            }
        })


class TestDeviceShadowStack:
    """Test Device Shadow management stack"""
    
    def test_dynamodb_table_creation(self, cdk_app):
        """Test DynamoDB table creation for device shadows"""
        # Create dependencies first
        iot_stack = IotPocStack(cdk_app, "TestIotPocStack")
        shadow_stack = DeviceShadowStack(cdk_app, "TestDeviceShadowStack")
        
        template = Template.from_stack(shadow_stack)
        
        # Verify DynamoDB table
        template.has_resource_properties("AWS::DynamoDB::Table", {
            "BillingMode": "PAY_PER_REQUEST",
            "AttributeDefinitions": [
                {
                    "AttributeName": "device_id",
                    "AttributeType": "S"
                }
            ]
        })
    
    def test_api_gateway_creation(self, cdk_app):
        """Test API Gateway creation for device shadow API"""
        iot_stack = IotPocStack(cdk_app, "TestIotPocStack")
        shadow_stack = DeviceShadowStack(cdk_app, "TestDeviceShadowStack")
        
        template = Template.from_stack(shadow_stack)
        
        # Verify API Gateway
        template.has_resource_properties("AWS::ApiGateway::RestApi", {
            "Name": Match.string_like_regexp(".*DeviceShadowApi.*")
        })


class TestAuthStack:
    """Test authentication and authorization stack"""
    
    def test_cognito_user_pool_creation(self, cdk_app):
        """Test Cognito User Pool creation"""
        auth_stack = AuthStack(cdk_app, "TestAuthStack")
        template = Template.from_stack(auth_stack)
        
        # Verify Cognito User Pool
        template.has_resource_properties("AWS::Cognito::UserPool", {
            "UsernameConfiguration": {
                "CaseSensitive": False
            },
            "AutoVerifiedAttributes": ["email"]
        })
    
    def test_cognito_user_pool_client_creation(self, cdk_app):
        """Test Cognito User Pool Client creation"""
        auth_stack = AuthStack(cdk_app, "TestAuthStack")
        template = Template.from_stack(auth_stack)
        
        # Verify User Pool Client
        template.has_resource_properties("AWS::Cognito::UserPoolClient", {
            "ExplicitAuthFlows": [
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_USER_SRP_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH"
            ]
        })


class TestEcsApiStack:
    """Test ECS API services stack"""
    
    def test_ecs_cluster_creation(self, cdk_app):
        """Test ECS cluster creation"""
        auth_stack = AuthStack(cdk_app, "TestAuthStack")
        ecs_stack = EcsApiStack(cdk_app, "TestEcsApiStack")
        
        template = Template.from_stack(ecs_stack)
        
        # Verify ECS cluster
        template.has_resource_properties("AWS::ECS::Cluster", {
            "ClusterName": Match.string_like_regexp(".*ApiCluster.*")
        })
    
    def test_application_load_balancer_creation(self, cdk_app):
        """Test Application Load Balancer creation"""
        auth_stack = AuthStack(cdk_app, "TestAuthStack")
        ecs_stack = EcsApiStack(cdk_app, "TestEcsApiStack")
        
        template = Template.from_stack(ecs_stack)
        
        # Verify ALB
        template.has_resource_properties("AWS::ElasticLoadBalancingV2::LoadBalancer", {
            "Type": "application",
            "Scheme": "internet-facing"
        })


class TestOtaStack:
    """Test OTA update management stack"""
    
    def test_s3_bucket_for_firmware(self, cdk_app):
        """Test S3 bucket creation for firmware storage"""
        iot_stack = IotPocStack(cdk_app, "TestIotPocStack")
        shadow_stack = DeviceShadowStack(cdk_app, "TestDeviceShadowStack")
        ota_stack = OtaStack(cdk_app, "TestOtaStack")
        
        template = Template.from_stack(ota_stack)
        
        # Verify firmware S3 bucket
        template.has_resource_properties("AWS::S3::Bucket", {
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {
                        "ServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }
                ]
            }
        })
    
    def test_iot_job_creation_lambda(self, cdk_app):
        """Test Lambda function for IoT job creation"""
        iot_stack = IotPocStack(cdk_app, "TestIotPocStack")
        shadow_stack = DeviceShadowStack(cdk_app, "TestDeviceShadowStack")
        ota_stack = OtaStack(cdk_app, "TestOtaStack")
        
        template = Template.from_stack(ota_stack)
        
        # Verify OTA Lambda function
        template.has_resource_properties("AWS::Lambda::Function", {
            "Runtime": "python3.11",
            "Timeout": 300
        })


class TestDataLakeStack:
    """Test data lake and analytics stack"""
    
    def test_glue_database_creation(self, cdk_app):
        """Test Glue database creation"""
        iot_stack = IotPocStack(cdk_app, "TestIotPocStack")
        data_lake_stack = DataLakeStack(cdk_app, "TestDataLakeStack")
        
        template = Template.from_stack(data_lake_stack)
        
        # Verify Glue database
        template.has_resource_properties("AWS::Glue::Database", {
            "DatabaseInput": {
                "Name": "iot_data_lake"
            }
        })
    
    def test_glue_table_creation(self, cdk_app):
        """Test Glue table creation for data lake"""
        iot_stack = IotPocStack(cdk_app, "TestIotPocStack")
        data_lake_stack = DataLakeStack(cdk_app, "TestDataLakeStack")
        
        template = Template.from_stack(data_lake_stack)
        
        # Verify raw data table
        template.has_resource_properties("AWS::Glue::Table", {
            "TableInput": {
                "Name": "raw_iot_data",
                "StorageDescriptor": {
                    "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                    "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                    "SerdeInfo": {
                        "SerializationLibrary": "org.openx.data.jsonserde.JsonSerDe"
                    }
                }
            }
        })
    
    def test_step_functions_workflow(self, cdk_app):
        """Test Step Functions workflow creation"""
        iot_stack = IotPocStack(cdk_app, "TestIotPocStack")
        data_lake_stack = DataLakeStack(cdk_app, "TestDataLakeStack")
        
        template = Template.from_stack(data_lake_stack)
        
        # Verify Step Functions state machine
        template.has_resource_properties("AWS::StepFunctions::StateMachine", {
            "StateMachineName": Match.string_like_regexp(".*DataProcessingWorkflow.*")
        })


class TestStackDependencies:
    """Test stack dependencies and integration"""
    
    def test_all_stacks_creation(self, cdk_app):
        """Test all stacks can be created together"""
        # Create all stacks in dependency order
        iot_stack = IotPocStack(cdk_app, "TestIotPocStack")
        shadow_stack = DeviceShadowStack(cdk_app, "TestDeviceShadowStack")
        auth_stack = AuthStack(cdk_app, "TestAuthStack")
        ecs_stack = EcsApiStack(cdk_app, "TestEcsApiStack")
        ota_stack = OtaStack(cdk_app, "TestOtaStack")
        data_lake_stack = DataLakeStack(cdk_app, "TestDataLakeStack")
        
        # Verify all stacks are created successfully
        assert iot_stack is not None
        assert shadow_stack is not None
        assert auth_stack is not None
        assert ecs_stack is not None
        assert ota_stack is not None
        assert data_lake_stack is not None
    
    def test_resource_count_reasonable(self, cdk_app):
        """Test that total resource count is reasonable"""
        # Create all stacks
        iot_stack = IotPocStack(cdk_app, "TestIotPocStack")
        shadow_stack = DeviceShadowStack(cdk_app, "TestDeviceShadowStack")
        auth_stack = AuthStack(cdk_app, "TestAuthStack")
        ecs_stack = EcsApiStack(cdk_app, "TestEcsApiStack")
        ota_stack = OtaStack(cdk_app, "TestOtaStack")
        data_lake_stack = DataLakeStack(cdk_app, "TestDataLakeStack")
        
        # Check resource counts are reasonable (not too many, indicating runaway resource creation)
        for stack in [iot_stack, shadow_stack, auth_stack, ecs_stack, ota_stack, data_lake_stack]:
            template = Template.from_stack(stack)
            resource_count = len(template.to_json()["Resources"])
            assert resource_count < 100, f"Stack {stack.stack_name} has {resource_count} resources, which seems excessive" 