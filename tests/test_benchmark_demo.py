"""
Benchmark tests to demonstrate performance testing with conda environment
"""

import pytest
import time
import json
import boto3
from moto import mock_aws


class TestPerformanceBenchmarks:
    """Performance benchmark tests"""
    
    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_json_processing_benchmark(self, benchmark):
        """Benchmark JSON processing performance"""
        sample_data = {
            "device_id": "test_device_001",
            "timestamp": 1640995200,
            "measurements": [
                {"type": "temperature", "value": 23.5, "unit": "celsius"},
                {"type": "humidity", "value": 65.2, "unit": "percent"},
                {"type": "pressure", "value": 1013.25, "unit": "hPa"}
            ]
        }
        
        def process_json():
            # Simulate JSON processing
            json_str = json.dumps(sample_data)
            parsed = json.loads(json_str)
            
            # Some processing
            total_measurements = len(parsed["measurements"])
            avg_temp = sum(m["value"] for m in parsed["measurements"] if m["type"] == "temperature")
            
            return total_measurements, avg_temp
        
        result = benchmark(process_json)
        assert result[0] == 3  # 3 measurements
        assert result[1] == 23.5  # temperature value
    
    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_boto3_client_creation_benchmark(self, benchmark):
        """Benchmark boto3 client creation"""
        
        def create_clients():
            # Create multiple AWS service clients
            clients = {}
            services = ['s3', 'sqs', 'dynamodb', 'iot-data']
            
            for service in services:
                clients[service] = boto3.client(service, region_name='us-east-1')
            
            return len(clients)
        
        with mock_aws():
            result = benchmark(create_clients)
            assert result == 4  # 4 clients created
    
    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_data_transformation_benchmark(self, benchmark):
        """Benchmark data transformation operations"""
        
        # Generate test data
        test_data = []
        for i in range(1000):
            test_data.append({
                "device_id": f"device_{i:03d}",
                "timestamp": 1640995200 + i,
                "temperature": 20.0 + (i % 10),
                "humidity": 50.0 + (i % 20)
            })
        
        def transform_data():
            # Transform data
            transformed = []
            for record in test_data:
                transformed_record = {
                    "id": record["device_id"],
                    "ts": record["timestamp"] * 1000,  # Convert to milliseconds
                    "temp_f": record["temperature"] * 9/5 + 32,  # Convert to Fahrenheit
                    "humidity_norm": record["humidity"] / 100.0  # Normalize humidity
                }
                transformed.append(transformed_record)
            
            return len(transformed)
        
        result = benchmark(transform_data)
        assert result == 1000  # All records transformed
    
    @pytest.mark.unit
    @pytest.mark.benchmark
    def test_string_operations_benchmark(self, benchmark):
        """Benchmark string operations"""
        
        def string_ops():
            # Simulate device ID generation and validation
            device_ids = []
            for i in range(500):
                device_id = f"iot-device-{i:06d}-sensor"
                # Validate format
                if device_id.startswith("iot-device-") and device_id.endswith("-sensor"):
                    device_ids.append(device_id.upper())
            
            return len(device_ids)
        
        result = benchmark(string_ops)
        assert result == 500


@pytest.mark.slow
@pytest.mark.benchmark
def test_simple_performance_test():
    """Simple performance test without benchmark fixture"""
    print("\n⚡ Running Performance Test")
    print("=" * 40)
    
    # Test list comprehension vs loop
    data_size = 10000
    
    # List comprehension timing
    start_time = time.time()
    list_comp_result = [x**2 for x in range(data_size)]
    list_comp_time = time.time() - start_time
    print(f"List comprehension: {list_comp_time:.4f}s for {data_size} items")
    
    # Loop timing
    start_time = time.time()
    loop_result = []
    for x in range(data_size):
        loop_result.append(x**2)
    loop_time = time.time() - start_time
    print(f"Loop: {loop_time:.4f}s for {data_size} items")
    
    # Verify results are the same
    assert list_comp_result == loop_result
    
    # List comprehension should generally be faster
    print(f"List comprehension is {loop_time/list_comp_time:.1f}x faster")
    
    print("✅ Performance test completed!")


if __name__ == "__main__":
    # For direct execution
    test_simple_performance_test() 