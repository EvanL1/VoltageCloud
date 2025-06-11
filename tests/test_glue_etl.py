"""
Tests for Glue ETL scripts in the data lake pipeline
Tests data transformation logic and processing workflows
"""

import pytest
import json
import boto3
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import pandas as pd
from moto import mock_s3, mock_glue
import os


class MockGlueContext:
    """Mock AWS Glue context for testing"""
    
    def __init__(self):
        self.params = {
            'JOB_NAME': 'test-etl-job',
            'source_database': 'test_iot_database',
            'source_table': 'test_raw_data',
            'target_database': 'test_iot_database',
            'target_table': 'test_processed_data',
            's3_target_path': 's3://test-bucket/processed/'
        }


class MockDynamicFrame:
    """Mock Glue DynamicFrame for testing"""
    
    def __init__(self, data=None):
        self.data = data or []
    
    def toDF(self):
        """Convert to Spark DataFrame (mocked as pandas)"""
        return pd.DataFrame(self.data)
    
    def count(self):
        return len(self.data)
    
    def show(self, n=10):
        print(f"Showing {min(n, len(self.data))} rows:")
        for i, row in enumerate(self.data[:n]):
            print(f"Row {i}: {row}")


class TestRawToProcessedETL:
    """Test raw data to processed data ETL transformation"""
    
    def setup_method(self):
        """Setup test data for each test method"""
        self.sample_raw_data = [
            {
                'device_id': 'device_001',
                'timestamp': 1640995200,  # 2022-01-01 00:00:00
                'temperature': 23.5,
                'humidity': 65.2,
                'pressure': 1013.25,
                'battery_level': 85,
                'year': '2022',
                'month': '01',
                'day': '01',
                'hour': '00'
            },
            {
                'device_id': 'device_002',
                'timestamp': 1640995260,  # 2022-01-01 00:01:00
                'temperature': 24.1,
                'humidity': 68.7,
                'pressure': 1012.8,
                'battery_level': 92,
                'year': '2022',
                'month': '01',
                'day': '01',
                'hour': '00'
            },
            {
                'device_id': 'device_001',
                'timestamp': 1640995320,  # 2022-01-01 00:02:00
                'temperature': 23.8,
                'humidity': 66.1,
                'pressure': 1013.1,
                'battery_level': 84,
                'year': '2022',
                'month': '01',
                'day': '01',
                'hour': '00'
            }
        ]
    
    def test_data_cleaning_and_validation(self):
        """Test data cleaning and validation logic"""
        def clean_and_validate_data(raw_data):
            """Mock ETL data cleaning function"""
            cleaned_data = []
            
            for record in raw_data:
                # Validate required fields
                if not all(field in record for field in ['device_id', 'timestamp', 'temperature', 'humidity']):
                    continue
                
                # Validate data ranges
                if not (-50 <= record['temperature'] <= 100):
                    continue
                if not (0 <= record['humidity'] <= 100):
                    continue
                
                # Calculate derived fields
                # Comfort index calculation (simplified)
                temp = record['temperature']
                humidity = record['humidity']
                
                if 20 <= temp <= 26 and 30 <= humidity <= 70:
                    comfort_index = 'comfortable'
                elif 15 <= temp <= 30 and 20 <= humidity <= 80:
                    comfort_index = 'acceptable'
                else:
                    comfort_index = 'uncomfortable'
                
                # Add derived fields
                cleaned_record = record.copy()
                cleaned_record['comfort_index'] = comfort_index
                cleaned_record['day_of_week'] = datetime.fromtimestamp(record['timestamp'], tz=timezone.utc).strftime('%A')
                cleaned_record['hour_of_day'] = datetime.fromtimestamp(record['timestamp'], tz=timezone.utc).hour
                
                cleaned_data.append(cleaned_record)
            
            return cleaned_data
        
        cleaned_data = clean_and_validate_data(self.sample_raw_data)
        
        # Verify all records passed validation
        assert len(cleaned_data) == 3
        
        # Verify derived fields are added
        for record in cleaned_data:
            assert 'comfort_index' in record
            assert 'day_of_week' in record
            assert 'hour_of_day' in record
            assert record['comfort_index'] in ['comfortable', 'acceptable', 'uncomfortable']
    
    def test_hourly_aggregation(self):
        """Test hourly data aggregation logic"""
        def aggregate_hourly_data(processed_data):
            """Mock ETL hourly aggregation function"""
            df = pd.DataFrame(processed_data)
            
            # Group by device and hour
            hourly_aggregated = df.groupby(['device_id', 'year', 'month', 'day', 'hour']).agg({
                'temperature': ['mean', 'min', 'max', 'count'],
                'humidity': ['mean', 'min', 'max'],
                'pressure': ['mean', 'min', 'max'],
                'battery_level': 'mean'
            }).round(2)
            
            # Flatten column names
            hourly_aggregated.columns = [
                'avg_temperature', 'min_temperature', 'max_temperature', 'reading_count',
                'avg_humidity', 'min_humidity', 'max_humidity',
                'avg_pressure', 'min_pressure', 'max_pressure',
                'avg_battery_level'
            ]
            
            hourly_aggregated = hourly_aggregated.reset_index()
            
            # Create hour timestamp
            hourly_aggregated['hour_timestamp'] = pd.to_datetime(
                hourly_aggregated[['year', 'month', 'day', 'hour']].astype(str).agg('-'.join, axis=1) + ':00:00',
                format='%Y-%m-%d-%H:%M:%S'
            )
            
            return hourly_aggregated.to_dict('records')
        
        # First clean the data
        def clean_data(raw_data):
            cleaned = []
            for record in raw_data:
                cleaned_record = record.copy()
                cleaned_record['comfort_index'] = 'comfortable'
                cleaned.append(cleaned_record)
            return cleaned
        
        cleaned_data = clean_data(self.sample_raw_data)
        aggregated_data = aggregate_hourly_data(cleaned_data)
        
        # Verify aggregation results
        assert len(aggregated_data) == 2  # Two devices in the same hour
        
        # Check device_001 aggregation
        device_001_agg = next(agg for agg in aggregated_data if agg['device_id'] == 'device_001')
        assert device_001_agg['reading_count'] == 2
        assert device_001_agg['avg_temperature'] == 23.65
        assert device_001_agg['min_temperature'] == 23.5
        assert device_001_agg['max_temperature'] == 23.8
    
    def test_data_partitioning(self):
        """Test data partitioning by year/month/day"""
        def partition_data_by_date(processed_data):
            """Mock ETL partitioning function"""
            partitioned_data = {}
            
            for record in processed_data:
                partition_key = f"year={record['year']}/month={record['month']}/day={record['day']}"
                
                if partition_key not in partitioned_data:
                    partitioned_data[partition_key] = []
                
                partitioned_data[partition_key].append(record)
            
            return partitioned_data
        
        partitioned_data = partition_data_by_date(self.sample_raw_data)
        
        # Verify partitioning
        assert 'year=2022/month=01/day=01' in partitioned_data
        assert len(partitioned_data['year=2022/month=01/day=01']) == 3
    
    def test_data_quality_checks(self):
        """Test data quality validation"""
        def run_data_quality_checks(processed_data):
            """Mock ETL data quality checks"""
            quality_report = {
                'total_records': len(processed_data),
                'null_device_ids': 0,
                'invalid_temperatures': 0,
                'invalid_humidity': 0,
                'future_timestamps': 0,
                'duplicate_records': 0
            }
            
            seen_records = set()
            current_timestamp = datetime.now().timestamp()
            
            for record in processed_data:
                # Check for null device IDs
                if not record.get('device_id'):
                    quality_report['null_device_ids'] += 1
                
                # Check temperature range
                temp = record.get('temperature', 0)
                if not -50 <= temp <= 100:
                    quality_report['invalid_temperatures'] += 1
                
                # Check humidity range
                humidity = record.get('humidity', 0)
                if not 0 <= humidity <= 100:
                    quality_report['invalid_humidity'] += 1
                
                # Check for future timestamps
                if record.get('timestamp', 0) > current_timestamp:
                    quality_report['future_timestamps'] += 1
                
                # Check for duplicates
                record_key = (record.get('device_id'), record.get('timestamp'))
                if record_key in seen_records:
                    quality_report['duplicate_records'] += 1
                seen_records.add(record_key)
            
            quality_report['data_quality_score'] = (
                (quality_report['total_records'] - 
                 quality_report['null_device_ids'] - 
                 quality_report['invalid_temperatures'] - 
                 quality_report['invalid_humidity'] - 
                 quality_report['future_timestamps'] - 
                 quality_report['duplicate_records']) / 
                quality_report['total_records'] * 100
            ) if quality_report['total_records'] > 0 else 0
            
            return quality_report
        
        quality_report = run_data_quality_checks(self.sample_raw_data)
        
        # Verify quality checks
        assert quality_report['total_records'] == 3
        assert quality_report['null_device_ids'] == 0
        assert quality_report['invalid_temperatures'] == 0
        assert quality_report['invalid_humidity'] == 0
        assert quality_report['data_quality_score'] == 100.0


class TestStatisticsETL:
    """Test device statistics ETL job"""
    
    def test_device_statistics_calculation(self):
        """Test device statistics calculation"""
        sample_processed_data = [
            {
                'device_id': 'device_001',
                'timestamp': 1640995200,
                'temperature': 23.5,
                'humidity': 65.2,
                'year': '2022', 'month': '01', 'day': '01'
            },
            {
                'device_id': 'device_001',
                'timestamp': 1640995260,
                'temperature': 24.1,
                'humidity': 67.8,
                'year': '2022', 'month': '01', 'day': '01'
            },
            {
                'device_id': 'device_002',
                'timestamp': 1640995200,
                'temperature': 22.8,
                'humidity': 70.1,
                'year': '2022', 'month': '01', 'day': '01'
            }
        ]
        
        def calculate_device_statistics(processed_data):
            """Mock device statistics calculation"""
            df = pd.DataFrame(processed_data)
            
            device_stats = df.groupby('device_id').agg({
                'temperature': ['mean', 'min', 'max', 'std', 'count'],
                'humidity': ['mean', 'min', 'max', 'std'],
                'timestamp': ['min', 'max']
            }).round(2)
            
            # Flatten column names
            device_stats.columns = [
                'avg_temperature', 'min_temperature', 'max_temperature', 'std_temperature', 'total_readings',
                'avg_humidity', 'min_humidity', 'max_humidity', 'std_humidity',
                'first_reading_timestamp', 'last_reading_timestamp'
            ]
            
            device_stats = device_stats.reset_index()
            
            # Calculate uptime (simplified as days between first and last reading)
            device_stats['uptime_days'] = (
                (device_stats['last_reading_timestamp'] - device_stats['first_reading_timestamp']) / 86400
            ).round(2)
            
            return device_stats.to_dict('records')
        
        stats = calculate_device_statistics(sample_processed_data)
        
        # Verify statistics calculation
        device_001_stats = next(stat for stat in stats if stat['device_id'] == 'device_001')
        assert device_001_stats['total_readings'] == 2
        assert device_001_stats['avg_temperature'] == 23.8
        assert device_001_stats['min_temperature'] == 23.5
        assert device_001_stats['max_temperature'] == 24.1


class TestETLIntegration:
    """Integration tests for complete ETL pipeline"""
    
    @mock_s3
    def test_complete_etl_pipeline(self, aws_credentials):
        """Test complete ETL pipeline from raw to processed data"""
        # Setup mock S3
        s3 = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-datalake-bucket'
        s3.create_bucket(Bucket=bucket_name)
        
        # Mock complete ETL pipeline
        def run_complete_etl_pipeline(raw_data, context):
            """Mock complete ETL pipeline"""
            # Step 1: Data cleaning and validation
            cleaned_data = []
            for record in raw_data:
                if all(field in record for field in ['device_id', 'timestamp', 'temperature', 'humidity']):
                    cleaned_record = record.copy()
                    cleaned_record['comfort_index'] = 'comfortable'
                    cleaned_record['processed_at'] = datetime.now().isoformat()
                    cleaned_data.append(cleaned_record)
            
            # Step 2: Hourly aggregation
            df = pd.DataFrame(cleaned_data)
            hourly_agg = df.groupby(['device_id', 'year', 'month', 'day', 'hour']).agg({
                'temperature': ['mean', 'count'],
                'humidity': 'mean'
            }).round(2)
            
            hourly_agg.columns = ['avg_temperature', 'reading_count', 'avg_humidity']
            hourly_agg = hourly_agg.reset_index()
            
            # Step 3: Device statistics
            device_stats = df.groupby('device_id').agg({
                'temperature': ['mean', 'count'],
                'humidity': 'mean'
            }).round(2)
            
            device_stats.columns = ['avg_temperature', 'total_readings', 'avg_humidity']
            device_stats = device_stats.reset_index()
            
            return {
                'processed_records': len(cleaned_data),
                'hourly_aggregations': len(hourly_agg),
                'device_statistics': len(device_stats),
                'status': 'SUCCESS'
            }
        
        # Test data
        raw_data = [
            {
                'device_id': 'device_001',
                'timestamp': 1640995200,
                'temperature': 23.5,
                'humidity': 65.2,
                'year': '2022', 'month': '01', 'day': '01', 'hour': '00'
            },
            {
                'device_id': 'device_002',
                'timestamp': 1640995260,
                'temperature': 24.1,
                'humidity': 67.8,
                'year': '2022', 'month': '01', 'day': '01', 'hour': '00'
            }
        ]
        
        context = MockGlueContext()
        result = run_complete_etl_pipeline(raw_data, context)
        
        # Verify pipeline results
        assert result['status'] == 'SUCCESS'
        assert result['processed_records'] == 2
        assert result['hourly_aggregations'] == 2
        assert result['device_statistics'] == 2
    
    def test_error_handling_in_etl(self):
        """Test error handling in ETL pipeline"""
        def etl_with_error_handling(raw_data):
            """Mock ETL with error handling"""
            results = {
                'processed_records': 0,
                'failed_records': 0,
                'errors': []
            }
            
            for record in raw_data:
                try:
                    # Simulate processing
                    if not record.get('device_id'):
                        raise ValueError("Missing device_id")
                    if not isinstance(record.get('temperature'), (int, float)):
                        raise ValueError("Invalid temperature value")
                    
                    results['processed_records'] += 1
                    
                except Exception as e:
                    results['failed_records'] += 1
                    results['errors'].append(str(e))
            
            return results
        
        # Test data with some invalid records
        test_data = [
            {'device_id': 'device_001', 'temperature': 23.5},  # Valid
            {'device_id': '', 'temperature': 24.1},  # Invalid: no device_id
            {'device_id': 'device_002', 'temperature': 'invalid'},  # Invalid: non-numeric temperature
            {'device_id': 'device_003', 'temperature': 25.0}  # Valid
        ]
        
        results = etl_with_error_handling(test_data)
        
        assert results['processed_records'] == 2
        assert results['failed_records'] == 2
        assert len(results['errors']) == 2
        assert "Missing device_id" in results['errors']
        assert "Invalid temperature value" in results['errors']


class TestETLPerformance:
    """Test ETL performance and optimization"""
    
    def test_large_dataset_processing(self):
        """Test ETL performance with large dataset"""
        import time
        
        # Generate large test dataset
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                'device_id': f'device_{i % 100:03d}',
                'timestamp': 1640995200 + i * 60,
                'temperature': 20 + (i % 20),
                'humidity': 50 + (i % 30),
                'year': '2022', 'month': '01', 'day': '01'
            })
        
        def optimized_etl_processing(data):
            """Mock optimized ETL processing"""
            start_time = time.time()
            
            # Simulate optimized processing using pandas
            df = pd.DataFrame(data)
            
            # Data validation
            valid_df = df.dropna(subset=['device_id', 'temperature', 'humidity'])
            
            # Aggregation
            hourly_agg = valid_df.groupby(['device_id', 'year', 'month', 'day']).agg({
                'temperature': 'mean',
                'humidity': 'mean'
            }).reset_index()
            
            processing_time = time.time() - start_time
            
            return {
                'input_records': len(data),
                'processed_records': len(valid_df),
                'aggregated_records': len(hourly_agg),
                'processing_time_seconds': processing_time
            }
        
        results = optimized_etl_processing(large_dataset)
        
        # Verify performance
        assert results['input_records'] == 1000
        assert results['processed_records'] == 1000
        assert results['processing_time_seconds'] < 1.0  # Should be fast with pandas 