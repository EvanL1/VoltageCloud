"""
Pytest configuration and shared fixtures for IoT platform testing
"""

import pytest
import boto3
import json
import os
from moto import mock_dynamodb, mock_s3, mock_lambda, mock_sqs, mock_iot, mock_timestream_write
from unittest.mock import Mock, patch
import aws_cdk as cdk
from aws_cdk.assertions import Template


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture
def mock_dynamodb_table(aws_credentials):
    """Create a mocked DynamoDB table for testing."""
    with mock_dynamodb():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='test-device-shadow',
            KeySchema=[
                {'AttributeName': 'device_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'device_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        yield table


@pytest.fixture
def mock_s3_bucket(aws_credentials):
    """Create a mocked S3 bucket for testing."""
    with mock_s3():
        s3 = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-iot-data-bucket'
        s3.create_bucket(Bucket=bucket_name)
        yield bucket_name


@pytest.fixture
def mock_sqs_queue(aws_credentials):
    """Create a mocked SQS queue for testing."""
    with mock_sqs():
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue_url = sqs.create_queue(QueueName='test-iot-data-queue')['QueueUrl']
        yield queue_url


@pytest.fixture
def mock_timestream_database(aws_credentials):
    """Create a mocked TimeStream database for testing."""
    with mock_timestream_write():
        timestream = boto3.client('timestream-write', region_name='us-east-1')
        database_name = 'test-iot-database'
        table_name = 'test-iot-table'
        
        timestream.create_database(DatabaseName=database_name)
        timestream.create_table(
            DatabaseName=database_name,
            TableName=table_name
        )
        yield database_name, table_name


@pytest.fixture
def cdk_app():
    """Create CDK app for testing."""
    return cdk.App()


@pytest.fixture
def sample_iot_payload():
    """Sample IoT device payload for testing."""
    return {
        "device_id": "device_test_001",
        "timestamp": 1640995200,  # 2022-01-01 00:00:00
        "temperature": 23.5,
        "humidity": 65.2,
        "pressure": 1013.25,
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060
        },
        "battery_level": 85,
        "signal_strength": -65
    }


@pytest.fixture
def sample_device_shadow():
    """Sample device shadow document for testing."""
    return {
        "device_id": "device_test_001",
        "state": {
            "desired": {
                "temperature_threshold": 25.0,
                "humidity_threshold": 70.0,
                "reporting_interval": 300
            },
            "reported": {
                "temperature_threshold": 25.0,
                "humidity_threshold": 70.0,
                "reporting_interval": 300,
                "last_seen": "2024-01-01T00:00:00Z"
            }
        },
        "metadata": {
            "desired": {
                "temperature_threshold": {
                    "timestamp": 1640995200
                }
            },
            "reported": {
                "temperature_threshold": {
                    "timestamp": 1640995200
                }
            }
        },
        "version": 1
    }


@pytest.fixture
def lambda_event():
    """Sample Lambda event for testing."""
    return {
        "Records": [
            {
                "messageId": "test-message-id",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps({
                    "device_id": "device_test_001",
                    "timestamp": 1640995200,
                    "temperature": 23.5,
                    "humidity": 65.2
                }),
                "attributes": {
                    "ApproximateReceiveCount": "1",
                    "SentTimestamp": "1640995200000",
                    "SenderId": "test-sender-id",
                    "ApproximateFirstReceiveTimestamp": "1640995200000"
                }
            }
        ]
    }


@pytest.fixture
def lambda_context():
    """Mock Lambda context for testing."""
    class MockContext:
        def __init__(self):
            self.function_name = "test-function"
            self.function_version = "1"
            self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
            self.memory_limit_in_mb = 128
            self.remaining_time_in_millis = lambda: 30000
            self.log_group_name = "/aws/lambda/test-function"
            self.log_stream_name = "test-stream"
            self.aws_request_id = "test-request-id"
    
    return MockContext()


@pytest.fixture
def api_gateway_event():
    """Sample API Gateway event for testing."""
    return {
        "httpMethod": "GET",
        "path": "/api/devices/device_test_001",
        "queryStringParameters": {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31"
        },
        "headers": {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json"
        },
        "body": None,
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "test",
            "httpMethod": "GET",
            "path": "/api/devices/device_test_001"
        }
    }


@pytest.fixture
def glue_job_context():
    """Mock Glue job context for testing."""
    class MockGlueContext:
        def __init__(self):
            self.params = {
                'JOB_NAME': 'test-etl-job',
                'source_database': 'test_iot_database',
                'source_table': 'test_raw_data',
                'target_database': 'test_iot_database',
                'target_table': 'test_processed_data',
                's3_target_path': 's3://test-bucket/processed/'
            }
    
    return MockGlueContext() 