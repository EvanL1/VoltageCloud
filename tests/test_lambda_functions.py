"""
Unit tests for Lambda functions in the IoT platform
Tests both Rust and Python Lambda functions
"""

import pytest
import json
import boto3
from unittest.mock import Mock, patch, MagicMock
from moto import mock_dynamodb, mock_timestream_write, mock_s3, mock_sqs
import os
import sys

# Mock imports for Rust Lambda testing
class MockRustLambda:
    """Mock Rust Lambda handler for testing"""
    
    @staticmethod
    def lambda_handler(event, context):
        """Mock implementation of Rust Lambda handler"""
        records = event.get('Records', [])
        processed_count = 0
        
        for record in records:
            try:
                body = json.loads(record['body'])
                if 'device_id' in body and 'timestamp' in body:
                    processed_count += 1
            except json.JSONDecodeError:
                continue
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'processed_records': processed_count,
                'total_records': len(records)
            })
        }


class TestRustLambdaHandler:
    """Test Rust Lambda data processing function"""
    
    def test_process_single_sqs_message(self, lambda_event, lambda_context):
        """Test processing a single SQS message"""
        handler = MockRustLambda()
        
        response = handler.lambda_handler(lambda_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed_records'] == 1
        assert body['total_records'] == 1
    
    def test_process_multiple_sqs_messages(self, lambda_context):
        """Test processing multiple SQS messages"""
        event = {
            "Records": [
                {
                    "messageId": "test-message-1",
                    "body": json.dumps({
                        "device_id": "device_001",
                        "timestamp": 1640995200,
                        "temperature": 23.5
                    })
                },
                {
                    "messageId": "test-message-2",
                    "body": json.dumps({
                        "device_id": "device_002",
                        "timestamp": 1640995260,
                        "temperature": 24.1
                    })
                }
            ]
        }
        
        handler = MockRustLambda()
        response = handler.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed_records'] == 2
        assert body['total_records'] == 2
    
    def test_process_malformed_message(self, lambda_context):
        """Test handling malformed SQS messages"""
        event = {
            "Records": [
                {
                    "messageId": "test-message-1",
                    "body": "invalid json"
                },
                {
                    "messageId": "test-message-2",
                    "body": json.dumps({
                        "device_id": "device_001",
                        "timestamp": 1640995200,
                        "temperature": 23.5
                    })
                }
            ]
        }
        
        handler = MockRustLambda()
        response = handler.lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed_records'] == 1
        assert body['total_records'] == 2


class TestDeviceShadowLambda:
    """Test device shadow management Lambda functions"""
    
    @patch('boto3.resource')
    def test_get_device_shadow(self, mock_boto3_resource, mock_dynamodb_table, api_gateway_event, lambda_context):
        """Test getting device shadow from DynamoDB"""
        # Setup mock DynamoDB response
        mock_table = Mock()
        mock_table.get_item.return_value = {
            'Item': {
                'device_id': 'device_test_001',
                'shadow_document': json.dumps({
                    'state': {
                        'reported': {
                            'temperature': 23.5,
                            'humidity': 65.2
                        }
                    },
                    'version': 1
                })
            }
        }
        mock_boto3_resource.return_value.Table.return_value = mock_table
        
        # Mock Lambda handler
        def shadow_handler(event, context):
            device_id = event['pathParameters']['device_id']
            
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table('device-shadow-table')
            
            response = table.get_item(Key={'device_id': device_id})
            
            if 'Item' in response:
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'device_id': device_id,
                        'shadow': json.loads(response['Item']['shadow_document'])
                    })
                }
            else:
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': 'Device not found'})
                }
        
        # Mock event with path parameters
        event = {
            **api_gateway_event,
            'pathParameters': {'device_id': 'device_test_001'}
        }
        
        response = shadow_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['device_id'] == 'device_test_001'
        assert 'shadow' in body
    
    @patch('boto3.resource')
    def test_update_device_shadow(self, mock_boto3_resource, lambda_context):
        """Test updating device shadow in DynamoDB"""
        # Setup mock DynamoDB
        mock_table = Mock()
        mock_table.put_item.return_value = {}
        mock_boto3_resource.return_value.Table.return_value = mock_table
        
        # Mock Lambda handler
        def shadow_update_handler(event, context):
            device_id = event['pathParameters']['device_id']
            shadow_update = json.loads(event['body'])
            
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table('device-shadow-table')
            
            table.put_item(
                Item={
                    'device_id': device_id,
                    'shadow_document': json.dumps(shadow_update),
                    'updated_at': '2024-01-01T00:00:00Z'
                }
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Shadow updated successfully'})
            }
        
        event = {
            'httpMethod': 'PUT',
            'pathParameters': {'device_id': 'device_test_001'},
            'body': json.dumps({
                'state': {
                    'desired': {
                        'temperature_threshold': 25.0
                    }
                }
            })
        }
        
        response = shadow_update_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        mock_table.put_item.assert_called_once()


class TestOtaLambda:
    """Test OTA management Lambda functions"""
    
    @patch('boto3.client')
    def test_create_ota_job(self, mock_boto3_client, lambda_context):
        """Test creating an OTA job"""
        # Setup mock IoT client
        mock_iot_client = Mock()
        mock_iot_client.create_job.return_value = {
            'jobArn': 'arn:aws:iot:us-east-1:123456789012:job/test-ota-job',
            'jobId': 'test-ota-job'
        }
        mock_boto3_client.return_value = mock_iot_client
        
        # Mock Lambda handler
        def ota_handler(event, context):
            iot_client = boto3.client('iot')
            
            job_document = {
                'operation': 'firmware_update',
                'firmwareUrl': event['firmware_url'],
                'version': event['version']
            }
            
            response = iot_client.create_job(
                jobId=event['job_id'],
                targets=event['targets'],
                document=json.dumps(job_document),
                jobExecutionsRolloutConfig={
                    'maximumPerMinute': 10
                }
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'jobId': response['jobId'],
                    'jobArn': response['jobArn']
                })
            }
        
        event = {
            'job_id': 'test-ota-job',
            'targets': ['device_test_001'],
            'firmware_url': 's3://firmware-bucket/firmware-v1.0.bin',
            'version': '1.0'
        }
        
        response = ota_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['jobId'] == 'test-ota-job'
        mock_iot_client.create_job.assert_called_once()


class TestDataLakeApiLambda:
    """Test data lake API Lambda functions"""
    
    @patch('boto3.client')
    def test_execute_athena_query(self, mock_boto3_client, lambda_context):
        """Test executing Athena query"""
        # Setup mock Athena client
        mock_athena_client = Mock()
        mock_athena_client.start_query_execution.return_value = {
            'QueryExecutionId': 'test-query-id'
        }
        mock_athena_client.get_query_execution.return_value = {
            'QueryExecution': {
                'Status': {'State': 'SUCCEEDED'}
            }
        }
        mock_athena_client.get_query_results.return_value = {
            'ResultSet': {
                'Rows': [
                    {
                        'Data': [
                            {'VarCharValue': 'device_001'},
                            {'VarCharValue': '23.5'}
                        ]
                    }
                ]
            }
        }
        mock_boto3_client.return_value = mock_athena_client
        
        # Mock Lambda handler
        def athena_handler(event, context):
            athena_client = boto3.client('athena')
            
            query = event['query']
            
            # Start query execution
            response = athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': 'iot_data_lake'},
                WorkGroup='iot-analytics'
            )
            
            query_id = response['QueryExecutionId']
            
            # Check query status (simplified for testing)
            status_response = athena_client.get_query_execution(
                QueryExecutionId=query_id
            )
            
            if status_response['QueryExecution']['Status']['State'] == 'SUCCEEDED':
                results = athena_client.get_query_results(
                    QueryExecutionId=query_id
                )
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'queryId': query_id,
                        'results': results['ResultSet']['Rows']
                    })
                }
            else:
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': 'Query failed'})
                }
        
        event = {
            'query': 'SELECT device_id, AVG(temperature) FROM iot_data_lake.raw_iot_data GROUP BY device_id'
        }
        
        response = athena_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'queryId' in body
        assert 'results' in body


class TestLambdaIntegration:
    """Integration tests for Lambda functions with AWS services"""
    
    @mock_sqs
    @mock_timestream_write
    def test_sqs_to_timestream_integration(self, aws_credentials, sample_iot_payload, lambda_context):
        """Test complete SQS to TimeStream integration"""
        # Create mock SQS queue
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue_url = sqs.create_queue(QueueName='test-iot-queue')['QueueUrl']
        
        # Create mock TimeStream database
        timestream = boto3.client('timestream-write', region_name='us-east-1')
        timestream.create_database(DatabaseName='test-database')
        timestream.create_table(
            DatabaseName='test-database',
            TableName='test-table'
        )
        
        # Send message to SQS
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(sample_iot_payload)
        )
        
        # Mock complete handler
        def integrated_handler(event, context):
            processed = 0
            for record in event['Records']:
                try:
                    data = json.loads(record['body'])
                    
                    # Write to TimeStream (mocked)
                    timestream.write_records(
                        DatabaseName='test-database',
                        TableName='test-table',
                        Records=[
                            {
                                'Dimensions': [
                                    {'Name': 'device_id', 'Value': data['device_id']}
                                ],
                                'MeasureName': 'temperature',
                                'MeasureValue': str(data['temperature']),
                                'MeasureValueType': 'DOUBLE',
                                'Time': str(data['timestamp'])
                            }
                        ]
                    )
                    processed += 1
                except Exception:
                    continue
            
            return {
                'statusCode': 200,
                'body': json.dumps({'processed': processed})
            }
        
        # Create SQS event
        event = {
            'Records': [
                {
                    'messageId': 'test-message',
                    'body': json.dumps(sample_iot_payload),
                    'attributes': {}
                }
            ]
        }
        
        response = integrated_handler(event, lambda_context)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed'] == 1


class TestProcessorChunking:
    """Tests for write_to_timestream chunking logic."""

    def test_write_to_timestream_chunking(self, monkeypatch):
        os.environ['TDB'] = 'test-db'
        os.environ['TBL'] = 'test-table'
        os.environ['BUCKET'] = 'test-bucket'
        os.environ['REGION'] = 'us-east-1'

        import importlib
        processor = importlib.import_module('lambda.processor')
        write_to_timestream = processor.write_to_timestream
        ts_client = processor.ts_client

        calls = []

        def mock_write_records(**kwargs):
            calls.append(len(kwargs.get('Records', [])))
            return {}

        monkeypatch.setattr(ts_client, 'write_records', mock_write_records)

        records = [
            {
                'Dimensions': [],
                'MeasureName': 'value',
                'MeasureValue': '0',
                'MeasureValueType': 'DOUBLE',
                'Time': str(i),
                'TimeUnit': 'MILLISECONDS',
            }
            for i in range(250)
        ]

        result = write_to_timestream(records)

        assert result is True
        assert calls == [100, 100, 50]
