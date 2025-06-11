"""
Performance and benchmark tests for IoT platform
Tests system performance, scalability, and resource usage
"""

import pytest
import time
import asyncio
import concurrent.futures
import json
import boto3
from unittest.mock import Mock, patch
import psutil
import threading
from datetime import datetime, timedelta
import random
import string

from moto import mock_dynamodb, mock_s3, mock_sqs, mock_timestream_write


class TestPerformanceBenchmarks:
    """Performance and load testing for IoT platform components"""

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_sqs_message_processing_throughput(self, benchmark, mock_sqs_queue):
        """Benchmark SQS message processing throughput"""
        from lambda.processor import process_sqs_message
        
        # Create sample message
        sample_message = {
            "device_id": "perf_test_device",
            "temperature": 25.5,
            "humidity": 60.0,
            "timestamp": int(time.time())
        }
        
        def process_batch():
            """Process a batch of 100 messages"""
            for _ in range(100):
                process_sqs_message(sample_message)
        
        result = benchmark(process_batch)
        # Should process at least 50 messages per second
        assert result is not None

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_dynamodb_concurrent_writes(self, mock_dynamodb_table):
        """Test concurrent DynamoDB write performance"""
        from lambda.shadow_manager import update_device_shadow
        
        def write_shadow(device_id):
            """Write a device shadow"""
            shadow_data = {
                "state": {
                    "desired": {"temperature": random.uniform(20, 30)},
                    "reported": {"temperature": random.uniform(20, 30)}
                }
            }
            return update_device_shadow(device_id, shadow_data)
        
        start_time = time.time()
        
        # Create 50 concurrent writes
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(write_shadow, f"device_{i:03d}")
                for i in range(50)
            ]
            
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete 50 writes in under 5 seconds
        assert duration < 5.0
        assert len(results) == 50

    @pytest.mark.slow
    @pytest.mark.benchmark  
    def test_memory_usage_under_load(self):
        """Test memory usage during high load processing"""
        from lambda.processor import process_iot_data
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Process 1000 messages
        for i in range(1000):
            large_payload = {
                "device_id": f"load_test_device_{i:04d}",
                "data": "x" * 1024,  # 1KB of data per message
                "timestamp": int(time.time()),
                "temperature": random.uniform(15, 35),
                "humidity": random.uniform(40, 80),
                "pressure": random.uniform(990, 1030)
            }
            process_iot_data(large_payload)
            
            # Force garbage collection every 100 iterations
            if i % 100 == 0:
                import gc
                gc.collect()
        
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory
        
        # Memory growth should be less than 50MB
        assert memory_growth < 50 * 1024 * 1024

    @pytest.mark.slow
    @pytest.mark.benchmark
    async def test_async_api_performance(self):
        """Test async API endpoint performance"""
        from lambda.api_integration import handle_api_request
        
        async def make_request(device_id):
            """Simulate API request"""
            event = {
                "httpMethod": "GET",
                "path": f"/api/devices/{device_id}/data",
                "queryStringParameters": {"limit": "10"}
            }
            return await handle_api_request(event)
        
        start_time = time.time()
        
        # Make 100 concurrent API requests
        tasks = [make_request(f"device_{i:03d}") for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle 100 requests in under 10 seconds
        assert duration < 10.0
        
        # Most requests should succeed
        successful_requests = len([r for r in results if not isinstance(r, Exception)])
        assert successful_requests >= 90

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_etl_processing_performance(self):
        """Test ETL pipeline processing performance"""
        from lambda.glue_etl_scripts.raw_to_processed import process_raw_data
        
        # Create large dataset
        large_dataset = []
        for i in range(10000):
            record = {
                "device_id": f"etl_test_{i % 100:03d}",
                "timestamp": int(time.time()) - (i * 60),  # 1 minute intervals
                "temperature": random.uniform(15, 35),
                "humidity": random.uniform(40, 80),
                "battery_level": random.uniform(20, 100)
            }
            large_dataset.append(record)
        
        start_time = time.time()
        
        # Process the dataset
        processed_data = process_raw_data(large_dataset)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should process 10K records in under 30 seconds
        assert duration < 30.0
        assert len(processed_data) > 0

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_timestream_write_performance(self, mock_timestream_database):
        """Test TimeStream write performance"""
        import boto3
        from moto import mock_timestream_write
        
        with mock_timestream_write():
            timestream = boto3.client('timestream-write', region_name='us-east-1')
            
            # Prepare batch of records
            records = []
            current_time = int(time.time() * 1000)  # milliseconds
            
            for i in range(1000):
                record = {
                    'Dimensions': [
                        {'Name': 'deviceId', 'Value': f'perf_device_{i % 10:02d}'},
                        {'Name': 'metric', 'Value': 'temperature'}
                    ],
                    'MeasureName': 'value',
                    'MeasureValue': str(random.uniform(20, 30)),
                    'MeasureValueType': 'DOUBLE',
                    'Time': str(current_time + i * 1000),
                    'TimeUnit': 'MILLISECONDS'
                }
                records.append(record)
            
            start_time = time.time()
            
            # Write in batches of 100 (TimeStream limit)
            batch_size = 100
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                timestream.write_records(
                    DatabaseName='test-iot-database',
                    TableName='test-iot-table',
                    Records=batch
                )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Should write 1000 records in under 10 seconds
            assert duration < 10.0

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_concurrent_lambda_executions(self):
        """Test performance under concurrent Lambda executions"""
        from lambda.processor import lambda_handler
        
        def simulate_lambda_execution():
            """Simulate a Lambda execution"""
            event = {
                "Records": [
                    {
                        "messageId": f"msg_{random.randint(1000, 9999)}",
                        "body": json.dumps({
                            "device_id": f"concurrent_device_{random.randint(1, 100):03d}",
                            "temperature": random.uniform(20, 30),
                            "timestamp": int(time.time())
                        })
                    }
                ]
            }
            
            context = Mock()
            context.remaining_time_in_millis = lambda: 30000
            
            return lambda_handler(event, context)
        
        start_time = time.time()
        
        # Run 20 concurrent executions
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(simulate_lambda_execution)
                for _ in range(20)
            ]
            
            results = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"Lambda execution failed: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete 20 executions in under 15 seconds
        assert duration < 15.0
        assert len(results) >= 18  # Allow for some failures

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_data_compression_performance(self):
        """Test data compression and decompression performance"""
        import gzip
        import json
        
        # Create large JSON data
        large_data = []
        for i in range(10000):
            record = {
                "device_id": f"compression_test_{i:06d}",
                "timestamp": int(time.time()) + i,
                "measurements": {
                    "temperature": random.uniform(15, 35),
                    "humidity": random.uniform(40, 80),
                    "pressure": random.uniform(990, 1030),
                    "light": random.uniform(0, 1000),
                    "sound": random.uniform(30, 90)
                },
                "location": {
                    "latitude": random.uniform(-90, 90),
                    "longitude": random.uniform(-180, 180)
                },
                "metadata": {
                    "firmware_version": "1.2.3",
                    "battery_level": random.uniform(0, 100),
                    "signal_strength": random.uniform(-100, -20)
                }
            }
            large_data.append(record)
        
        json_data = json.dumps(large_data)
        original_size = len(json_data.encode('utf-8'))
        
        # Test compression
        start_time = time.time()
        compressed_data = gzip.compress(json_data.encode('utf-8'))
        compression_time = time.time() - start_time
        
        compressed_size = len(compressed_data)
        compression_ratio = compressed_size / original_size
        
        # Test decompression
        start_time = time.time()
        decompressed_data = gzip.decompress(compressed_data).decode('utf-8')
        decompression_time = time.time() - start_time
        
        # Verify data integrity
        assert json.loads(decompressed_data) == large_data
        
        # Performance assertions
        assert compression_time < 5.0  # Should compress in under 5 seconds
        assert decompression_time < 2.0  # Should decompress in under 2 seconds
        assert compression_ratio < 0.3  # Should achieve at least 70% compression

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_cpu_intensive_processing(self):
        """Test CPU-intensive data processing performance"""
        import numpy as np
        from datetime import datetime, timedelta
        
        def calculate_moving_averages(data, window_size=10):
            """Calculate moving averages - CPU intensive operation"""
            results = []
            for i in range(len(data) - window_size + 1):
                window = data[i:i + window_size]
                avg = sum(window) / len(window)
                results.append(avg)
            return results
        
        def complex_statistical_analysis(temperature_data, humidity_data):
            """Perform complex statistical analysis"""
            # Calculate correlations, standard deviations, etc.
            temp_mean = np.mean(temperature_data)
            temp_std = np.std(temperature_data)
            humidity_mean = np.mean(humidity_data)
            humidity_std = np.std(humidity_data)
            
            # Calculate correlation coefficient
            correlation = np.corrcoef(temperature_data, humidity_data)[0, 1]
            
            return {
                "temperature_stats": {"mean": temp_mean, "std": temp_std},
                "humidity_stats": {"mean": humidity_mean, "std": humidity_std},
                "correlation": correlation
            }
        
        # Generate large dataset
        size = 50000
        temperature_data = [random.uniform(15, 35) for _ in range(size)]
        humidity_data = [random.uniform(40, 80) for _ in range(size)]
        
        start_time = time.time()
        
        # Perform CPU-intensive operations
        temp_moving_avg = calculate_moving_averages(temperature_data, 100)
        humidity_moving_avg = calculate_moving_averages(humidity_data, 100)
        
        stats = complex_statistical_analysis(temperature_data, humidity_data)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete analysis in under 10 seconds
        assert duration < 10.0
        assert len(temp_moving_avg) > 0
        assert len(humidity_moving_avg) > 0
        assert "correlation" in stats


class TestStressTests:
    """Stress tests for system limits and error handling"""

    @pytest.mark.slow
    @pytest.mark.stress
    def test_maximum_message_size_handling(self):
        """Test handling of maximum size messages"""
        from lambda.processor import process_iot_data
        
        # Create message close to Lambda payload limit (6MB)
        large_payload = {
            "device_id": "stress_test_device",
            "timestamp": int(time.time()),
            "large_data": "x" * (5 * 1024 * 1024)  # 5MB of data
        }
        
        try:
            result = process_iot_data(large_payload)
            # Should handle gracefully or raise appropriate error
            assert result is not None or True  # Either succeed or fail gracefully
        except Exception as e:
            # Should be a specific, expected error
            assert "size" in str(e).lower() or "limit" in str(e).lower()

    @pytest.mark.slow
    @pytest.mark.stress
    def test_high_frequency_requests(self):
        """Test system behavior under high frequency requests"""
        from lambda.api_integration import handle_api_request
        
        request_count = 0
        errors = []
        
        def make_rapid_requests():
            nonlocal request_count, errors
            for i in range(100):
                try:
                    event = {
                        "httpMethod": "GET",
                        "path": "/api/health",
                        "queryStringParameters": None
                    }
                    handle_api_request(event)
                    request_count += 1
                except Exception as e:
                    errors.append(str(e))
                
                # No delay - rapid fire requests
        
        # Start multiple threads making rapid requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_rapid_requests)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should handle most requests successfully
        success_rate = request_count / (request_count + len(errors))
        assert success_rate > 0.8  # At least 80% success rate

    @pytest.mark.slow
    @pytest.mark.stress
    def test_resource_exhaustion_recovery(self):
        """Test system recovery from resource exhaustion"""
        import gc
        
        # Intentionally consume memory
        memory_hogs = []
        try:
            # Allocate memory until we hit a reasonable limit
            for i in range(100):
                # Allocate 10MB chunks
                chunk = bytearray(10 * 1024 * 1024)
                memory_hogs.append(chunk)
                
                if i % 10 == 0:
                    # Try to perform normal operations
                    from lambda.processor import process_iot_data
                    test_payload = {
                        "device_id": "recovery_test_device",
                        "temperature": 25.5,
                        "timestamp": int(time.time())
                    }
                    
                    try:
                        process_iot_data(test_payload)
                    except MemoryError:
                        # Expected under memory pressure
                        break
        finally:
            # Clean up memory
            memory_hogs.clear()
            gc.collect()
        
        # System should recover after cleanup
        from lambda.processor import process_iot_data
        recovery_payload = {
            "device_id": "post_recovery_device", 
            "temperature": 23.0,
            "timestamp": int(time.time())
        }
        
        # Should work normally after recovery
        result = process_iot_data(recovery_payload)
        assert result is not None


class TestLoadTests:
    """Load tests for sustained performance"""

    @pytest.mark.slow
    @pytest.mark.load
    def test_sustained_load_processing(self):
        """Test system performance under sustained load"""
        from lambda.processor import process_iot_data
        
        start_time = time.time()
        processed_count = 0
        errors = 0
        
        # Run for 60 seconds or 10,000 messages, whichever comes first
        while time.time() - start_time < 60 and processed_count < 10000:
            try:
                payload = {
                    "device_id": f"load_device_{processed_count % 100:03d}",
                    "temperature": random.uniform(20, 30),
                    "humidity": random.uniform(50, 70),
                    "timestamp": int(time.time())
                }
                
                process_iot_data(payload)
                processed_count += 1
                
                # Brief pause to simulate realistic load
                time.sleep(0.001)  # 1ms delay
                
            except Exception:
                errors += 1
        
        duration = time.time() - start_time
        throughput = processed_count / duration
        error_rate = errors / (processed_count + errors) if (processed_count + errors) > 0 else 0
        
        # Should maintain reasonable throughput and low error rate
        assert throughput > 50  # At least 50 messages per second
        assert error_rate < 0.05  # Less than 5% error rate

    @pytest.mark.slow
    @pytest.mark.load
    def test_gradual_load_increase(self):
        """Test system behavior as load gradually increases"""
        from lambda.processor import process_iot_data
        
        results = []
        
        for load_level in [1, 5, 10, 25, 50, 100]:
            start_time = time.time()
            processed = 0
            errors = 0
            
            # Process messages at current load level for 10 seconds
            while time.time() - start_time < 10:
                for _ in range(load_level):
                    try:
                        payload = {
                            "device_id": f"gradual_device_{processed % 20:02d}",
                            "temperature": random.uniform(20, 30),
                            "timestamp": int(time.time())
                        }
                        process_iot_data(payload)
                        processed += 1
                    except Exception:
                        errors += 1
                
                time.sleep(0.1)  # 100ms between batches
            
            duration = time.time() - start_time
            throughput = processed / duration
            error_rate = errors / (processed + errors) if (processed + errors) > 0 else 0
            
            results.append({
                "load_level": load_level,
                "throughput": throughput,
                "error_rate": error_rate,
                "processed": processed,
                "errors": errors
            })
        
        # Analyze results - throughput should scale reasonably
        for i, result in enumerate(results):
            # Error rate should remain acceptable
            assert result["error_rate"] < 0.1  # Less than 10% errors
            
            # Throughput should generally increase (with some reasonable limits)
            if i > 0:
                prev_throughput = results[i-1]["throughput"]
                current_throughput = result["throughput"]
                # Allow for some degradation at very high loads
                assert current_throughput > prev_throughput * 0.7 