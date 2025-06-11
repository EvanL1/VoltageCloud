"""
Integration tests for IoT platform
Tests end-to-end workflows and component interactions
"""

import pytest
import json
import boto3
import time
from unittest.mock import Mock, patch, MagicMock
from moto import mock_sqs, mock_dynamodb, mock_s3, mock_timestream_write, mock_iot
import requests
from concurrent.futures import ThreadPoolExecutor
import threading


class TestDataIngestionPipeline:
    """Test complete data ingestion pipeline"""
    
    @mock_sqs
    @mock_timestream_write
    @mock_s3
    def test_end_to_end_data_flow(self, aws_credentials, sample_iot_payload):
        """Test complete data flow from IoT device to storage"""
        # Setup AWS services
        sqs = boto3.client('sqs', region_name='us-east-1')
        timestream = boto3.client('timestream-write', region_name='us-east-1')
        s3 = boto3.client('s3', region_name='us-east-1')
        
        # Create resources
        queue_url = sqs.create_queue(QueueName='iot-data-queue')['QueueUrl']
        timestream.create_database(DatabaseName='IoTDatabase')
        timestream.create_table(DatabaseName='IoTDatabase', TableName='IoTTable')
        s3.create_bucket(Bucket='iot-data-bucket')
        
        # Simulate IoT device sending data
        def simulate_device_data_ingestion():
            """Simulate complete data ingestion process"""
            # Step 1: Device sends data to SQS
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(sample_iot_payload)
            )
            
            # Step 2: Lambda processes SQS message
            messages = sqs.receive_message(QueueUrl=queue_url).get('Messages', [])
            
            processed_data = []
            for message in messages:
                try:
                    data = json.loads(message['Body'])
                    
                    # Step 3: Write to TimeStream
                    timestream.write_records(
                        DatabaseName='IoTDatabase',
                        TableName='IoTTable',
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
                    
                    # Step 4: Store raw data in S3
                    s3.put_object(
                        Bucket='iot-data-bucket',
                        Key=f"raw-data/{data['device_id']}/{data['timestamp']}.json",
                        Body=json.dumps(data)
                    )
                    
                    processed_data.append(data)
                    
                    # Step 5: Delete message from SQS
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    
                except Exception as e:
                    print(f"Error processing message: {e}")
                    continue
            
            return processed_data
        
        # Execute the pipeline
        result = simulate_device_data_ingestion()
        
        # Verify results
        assert len(result) == 1
        assert result[0]['device_id'] == sample_iot_payload['device_id']
        
        # Verify S3 storage
        objects = s3.list_objects_v2(Bucket='iot-data-bucket')
        assert objects['KeyCount'] == 1
        
        # Verify SQS queue is empty
        remaining_messages = sqs.receive_message(QueueUrl=queue_url).get('Messages', [])
        assert len(remaining_messages) == 0
    
    @mock_sqs
    def test_batch_processing(self, aws_credentials):
        """Test batch processing of multiple IoT messages"""
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue_url = sqs.create_queue(QueueName='iot-batch-queue')['QueueUrl']
        
        # Send multiple messages
        test_devices = [f'device_{i:03d}' for i in range(10)]
        
        for i, device_id in enumerate(test_devices):
            message = {
                'device_id': device_id,
                'timestamp': 1640995200 + i * 60,
                'temperature': 20 + i,
                'humidity': 50 + i
            }
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message)
            )
        
        # Process batch
        def process_batch():
            messages = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10
            ).get('Messages', [])
            
            processed = []
            for message in messages:
                try:
                    data = json.loads(message['Body'])
                    processed.append(data)
                    
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                except Exception:
                    continue
            
            return processed
        
        # Process all messages
        all_processed = []
        while True:
            batch = process_batch()
            if not batch:
                break
            all_processed.extend(batch)
        
        # Verify all messages were processed
        assert len(all_processed) == 10
        processed_device_ids = [item['device_id'] for item in all_processed]
        assert set(processed_device_ids) == set(test_devices)


class TestDeviceManagementWorkflow:
    """Test device management workflows"""
    
    @mock_dynamodb
    @mock_iot
    def test_device_registration_and_shadow_creation(self, aws_credentials):
        """Test complete device registration workflow"""
        # Setup services
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        iot = boto3.client('iot', region_name='us-east-1')
        
        # Create DynamoDB table
        table = dynamodb.create_table(
            TableName='device-registry',
            KeySchema=[
                {'AttributeName': 'device_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'device_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        
        def register_device_workflow(device_id, device_config):
            """Complete device registration workflow"""
            # Step 1: Create IoT Thing
            iot.create_thing(thingName=device_id)
            
            # Step 2: Create device certificate
            cert_response = iot.create_keys_and_certificate(setAsActive=True)
            
            # Step 3: Create policy
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
                        "Resource": f"arn:aws:iot:*:*:*/{device_id}"
                    }
                ]
            }
            
            iot.create_policy(
                policyName=f'{device_id}-policy',
                policyDocument=json.dumps(policy_document)
            )
            
            # Step 4: Attach policy to certificate
            iot.attach_policy(
                policyName=f'{device_id}-policy',
                target=cert_response['certificateArn']
            )
            
            # Step 5: Attach certificate to thing
            iot.attach_thing_principal(
                thingName=device_id,
                principal=cert_response['certificateArn']
            )
            
            # Step 6: Store device info in DynamoDB
            table.put_item(
                Item={
                    'device_id': device_id,
                    'certificate_arn': cert_response['certificateArn'],
                    'status': 'active',
                    'config': device_config,
                    'created_at': '2024-01-01T00:00:00Z'
                }
            )
            
            return {
                'device_id': device_id,
                'certificate_arn': cert_response['certificateArn'],
                'status': 'registered'
            }
        
        # Test device registration
        device_config = {
            'type': 'temperature_sensor',
            'location': 'building_a_floor_1',
            'reporting_interval': 300
        }
        
        result = register_device_workflow('test_device_001', device_config)
        
        # Verify registration
        assert result['device_id'] == 'test_device_001'
        assert result['status'] == 'registered'
        assert 'certificate_arn' in result
        
        # Verify DynamoDB entry
        response = table.get_item(Key={'device_id': 'test_device_001'})
        assert 'Item' in response
        assert response['Item']['status'] == 'active'


class TestOtaUpdateWorkflow:
    """Test OTA update workflow"""
    
    @mock_s3
    @mock_iot
    @mock_dynamodb
    def test_complete_ota_workflow(self, aws_credentials):
        """Test complete OTA update workflow"""
        # Setup services
        s3 = boto3.client('s3', region_name='us-east-1')
        iot = boto3.client('iot', region_name='us-east-1')
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create resources
        s3.create_bucket(Bucket='firmware-bucket')
        
        # Create job tracking table
        job_table = dynamodb.create_table(
            TableName='ota-jobs',
            KeySchema=[
                {'AttributeName': 'job_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'job_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        job_table.wait_until_exists()
        
        def ota_update_workflow(job_id, firmware_version, target_devices):
            """Complete OTA update workflow"""
            # Step 1: Upload firmware to S3
            firmware_content = b"mock firmware binary content"
            firmware_key = f"firmware/{firmware_version}/firmware.bin"
            
            s3.put_object(
                Bucket='firmware-bucket',
                Key=firmware_key,
                Body=firmware_content
            )
            
            # Step 2: Create IoT job document
            job_document = {
                "operation": "firmware_update",
                "firmware_version": firmware_version,
                "firmware_url": f"s3://firmware-bucket/{firmware_key}",
                "checksum": "mock_checksum"
            }
            
            # Step 3: Create IoT job
            iot.create_job(
                jobId=job_id,
                targets=target_devices,
                document=json.dumps(job_document),
                jobExecutionsRolloutConfig={
                    'maximumPerMinute': 5
                }
            )
            
            # Step 4: Track job in DynamoDB
            job_table.put_item(
                Item={
                    'job_id': job_id,
                    'firmware_version': firmware_version,
                    'target_devices': target_devices,
                    'status': 'IN_PROGRESS',
                    'created_at': '2024-01-01T00:00:00Z'
                }
            )
            
            # Step 5: Simulate job execution monitoring
            job_executions = []
            for device in target_devices:
                execution = {
                    'device_id': device,
                    'status': 'QUEUED',
                    'start_time': '2024-01-01T00:00:00Z'
                }
                job_executions.append(execution)
            
            return {
                'job_id': job_id,
                'firmware_version': firmware_version,
                'target_count': len(target_devices),
                'status': 'CREATED',
                'executions': job_executions
            }
        
        # Test OTA workflow
        target_devices = ['device_001', 'device_002', 'device_003']
        result = ota_update_workflow('ota_job_001', 'v1.2.0', target_devices)
        
        # Verify results
        assert result['job_id'] == 'ota_job_001'
        assert result['firmware_version'] == 'v1.2.0'
        assert result['target_count'] == 3
        assert result['status'] == 'CREATED'
        
        # Verify S3 firmware upload
        objects = s3.list_objects_v2(Bucket='firmware-bucket')
        assert objects['KeyCount'] == 1
        assert 'firmware/v1.2.0/firmware.bin' in objects['Contents'][0]['Key']
        
        # Verify job tracking
        job_response = job_table.get_item(Key={'job_id': 'ota_job_001'})
        assert 'Item' in job_response
        assert job_response['Item']['status'] == 'IN_PROGRESS'


class TestDataAnalyticsPipeline:
    """Test data analytics pipeline"""
    
    @mock_s3
    def test_data_lake_etl_pipeline(self, aws_credentials):
        """Test data lake ETL pipeline"""
        s3 = boto3.client('s3', region_name='us-east-1')
        
        # Create buckets
        s3.create_bucket(Bucket='raw-data-bucket')
        s3.create_bucket(Bucket='processed-data-bucket')
        
        # Generate sample raw data
        raw_data = []
        for i in range(100):
            raw_data.append({
                'device_id': f'device_{i % 10:03d}',
                'timestamp': 1640995200 + i * 60,
                'temperature': 20 + (i % 15),
                'humidity': 50 + (i % 20),
                'year': '2022',
                'month': '01',
                'day': '01',
                'hour': f'{i // 60:02d}'
            })
        
        def run_etl_pipeline():
            """Simulate ETL pipeline"""
            # Step 1: Store raw data in S3
            for i, record in enumerate(raw_data):
                s3.put_object(
                    Bucket='raw-data-bucket',
                    Key=f"raw/{record['year']}/{record['month']}/{record['day']}/{i:06d}.json",
                    Body=json.dumps(record)
                )
            
            # Step 2: Process data (simulate Glue job)
            import pandas as pd
            
            df = pd.DataFrame(raw_data)
            
            # Aggregate by device and hour
            hourly_agg = df.groupby(['device_id', 'year', 'month', 'day', 'hour']).agg({
                'temperature': ['mean', 'min', 'max', 'count'],
                'humidity': ['mean', 'min', 'max']
            }).round(2)
            
            hourly_agg.columns = [
                'avg_temperature', 'min_temperature', 'max_temperature', 'reading_count',
                'avg_humidity', 'min_humidity', 'max_humidity'
            ]
            
            hourly_agg = hourly_agg.reset_index()
            
            # Step 3: Store processed data
            processed_data = hourly_agg.to_dict('records')
            
            for i, record in enumerate(processed_data):
                s3.put_object(
                    Bucket='processed-data-bucket',
                    Key=f"processed/{record['year']}/{record['month']}/{record['day']}/{i:06d}.json",
                    Body=json.dumps(record)
                )
            
            return {
                'raw_records': len(raw_data),
                'processed_records': len(processed_data),
                'unique_devices': len(df['device_id'].unique()),
                'unique_hours': len(df['hour'].unique())
            }
        
        # Run ETL pipeline
        result = run_etl_pipeline()
        
        # Verify results
        assert result['raw_records'] == 100
        assert result['unique_devices'] == 10
        
        # Verify S3 storage
        raw_objects = s3.list_objects_v2(Bucket='raw-data-bucket')
        processed_objects = s3.list_objects_v2(Bucket='processed-data-bucket')
        
        assert raw_objects['KeyCount'] == 100
        assert processed_objects['KeyCount'] > 0


class TestSystemResilience:
    """Test system resilience and error handling"""
    
    @mock_sqs
    def test_dlq_processing(self, aws_credentials):
        """Test dead letter queue processing"""
        sqs = boto3.client('sqs', region_name='us-east-1')
        
        # Create main queue and DLQ
        dlq_url = sqs.create_queue(QueueName='iot-data-dlq')['QueueUrl']
        main_queue_url = sqs.create_queue(
            QueueName='iot-data-main',
            Attributes={
                'RedrivePolicy': json.dumps({
                    'deadLetterTargetArn': f'arn:aws:sqs:us-east-1:123456789012:iot-data-dlq',
                    'maxReceiveCount': 3
                })
            }
        )['QueueUrl']
        
        def simulate_message_processing_with_failures():
            """Simulate message processing with failures"""
            # Send messages - some will be invalid
            messages = [
                {'device_id': 'device_001', 'temperature': 23.5},  # Valid
                {'invalid': 'data'},  # Invalid - missing device_id
                {'device_id': 'device_002', 'temperature': 'invalid'},  # Invalid - non-numeric temp
                {'device_id': 'device_003', 'temperature': 25.0},  # Valid
            ]
            
            for msg in messages:
                sqs.send_message(
                    QueueUrl=main_queue_url,
                    MessageBody=json.dumps(msg)
                )
            
            processed = []
            failed = []
            
            # Process messages
            for _ in range(len(messages)):
                response = sqs.receive_message(QueueUrl=main_queue_url)
                messages_received = response.get('Messages', [])
                
                for message in messages_received:
                    try:
                        data = json.loads(message['Body'])
                        
                        # Validate message
                        if 'device_id' not in data:
                            raise ValueError("Missing device_id")
                        if not isinstance(data.get('temperature'), (int, float)):
                            raise ValueError("Invalid temperature")
                        
                        processed.append(data)
                        
                        # Delete successful message
                        sqs.delete_message(
                            QueueUrl=main_queue_url,
                            ReceiptHandle=message['ReceiptHandle']
                        )
                        
                    except Exception as e:
                        failed.append({
                            'message': message['Body'],
                            'error': str(e)
                        })
                        # Don't delete - let it retry and eventually go to DLQ
            
            return {
                'processed': processed,
                'failed': failed
            }
        
        result = simulate_message_processing_with_failures()
        
        # Verify processing results
        assert len(result['processed']) == 2  # Two valid messages
        assert len(result['failed']) == 2    # Two invalid messages
    
    def test_concurrent_processing(self):
        """Test concurrent processing capabilities"""
        import threading
        import time
        
        def simulate_concurrent_device_processing():
            """Simulate concurrent processing of multiple devices"""
            results = []
            results_lock = threading.Lock()
            
            def process_device_data(device_id):
                """Process data for a single device"""
                # Simulate processing time
                time.sleep(0.1)
                
                result = {
                    'device_id': device_id,
                    'processed_records': 10,
                    'processing_time': 0.1,
                    'thread_id': threading.current_thread().ident
                }
                
                with results_lock:
                    results.append(result)
            
            # Process 10 devices concurrently
            threads = []
            for i in range(10):
                device_id = f'device_{i:03d}'
                thread = threading.Thread(target=process_device_data, args=(device_id,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            return results
        
        start_time = time.time()
        results = simulate_concurrent_device_processing()
        end_time = time.time()
        
        # Verify concurrent processing
        assert len(results) == 10
        assert len(set(r['thread_id'] for r in results)) > 1  # Multiple threads used
        assert end_time - start_time < 1.0  # Should be much faster than sequential


class TestPerformanceBenchmarks:
    """Performance benchmarks and load testing"""
    
    def test_message_throughput(self):
        """Test message processing throughput"""
        import time
        
        def benchmark_message_processing(message_count=1000):
            """Benchmark message processing performance"""
            # Generate test messages
            messages = []
            for i in range(message_count):
                messages.append({
                    'device_id': f'device_{i % 100:03d}',
                    'timestamp': 1640995200 + i,
                    'temperature': 20 + (i % 10),
                    'humidity': 50 + (i % 20)
                })
            
            # Process messages
            start_time = time.time()
            processed_count = 0
            
            for message in messages:
                try:
                    # Simulate processing (validation, transformation, etc.)
                    if 'device_id' in message and 'timestamp' in message:
                        processed_count += 1
                except Exception:
                    continue
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            return {
                'total_messages': message_count,
                'processed_messages': processed_count,
                'processing_time': processing_time,
                'messages_per_second': processed_count / processing_time if processing_time > 0 else 0
            }
        
        # Run benchmark
        result = benchmark_message_processing()
        
        # Verify performance
        assert result['processed_messages'] == result['total_messages']
        assert result['messages_per_second'] > 1000  # Should process at least 1000 msg/sec
        assert result['processing_time'] < 1.0  # Should complete within 1 second 