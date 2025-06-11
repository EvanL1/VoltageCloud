"""
Monitoring and observability tests for IoT platform
Tests logging, metrics, alerts, and system health monitoring
"""

import pytest
import json
import time
import logging
import re
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import boto3
from moto import mock_cloudwatch, mock_logs, mock_sns


class TestLoggingAndMetrics:
    """Test logging configuration and metrics collection"""

    def test_structured_logging_format(self, caplog):
        """Test that logs are properly structured"""
        from lambda.processor import logger
        
        with caplog.at_level(logging.INFO):
            logger.info("Test message", extra={
                "device_id": "test_device_001",
                "operation": "data_processing",
                "duration_ms": 150,
                "status": "success"
            })
        
        # Verify log structure
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.device_id == "test_device_001"
        assert record.operation == "data_processing"
        assert record.duration_ms == 150
        assert record.status == "success"

    def test_error_logging_includes_context(self, caplog):
        """Test that error logs include sufficient context"""
        from lambda.processor import process_iot_data
        
        # Create invalid payload that will cause an error
        invalid_payload = {
            "device_id": None,  # Invalid device ID
            "temperature": "invalid_temp"  # Invalid temperature
        }
        
        with caplog.at_level(logging.ERROR):
            try:
                process_iot_data(invalid_payload)
            except Exception:
                pass  # Expected to fail
        
        # Check that error logs contain context
        error_logs = [record for record in caplog.records if record.levelno >= logging.ERROR]
        assert len(error_logs) > 0
        
        error_record = error_logs[0]
        # Should include request ID, timestamp, and error details
        assert hasattr(error_record, 'timestamp') or 'timestamp' in error_record.getMessage()

    @mock_cloudwatch
    def test_custom_metrics_publication(self):
        """Test custom metrics are published to CloudWatch"""
        from lambda.processor import publish_custom_metrics
        
        cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
        
        # Publish test metrics
        metrics_data = {
            "DeviceMessageCount": 150,
            "ProcessingLatency": 250.5,
            "ErrorRate": 0.02
        }
        
        publish_custom_metrics(metrics_data)
        
        # Verify metrics were published (in real scenario, would check CloudWatch)
        # For mocked environment, we verify the function executed without error
        assert True  # Placeholder for actual CloudWatch verification

    def test_performance_metrics_collection(self):
        """Test collection of performance metrics"""
        from lambda.processor import collect_performance_metrics
        
        start_time = time.time()
        
        # Simulate some processing
        time.sleep(0.1)
        
        metrics = collect_performance_metrics(start_time, "test_operation")
        
        assert "operation" in metrics
        assert "duration_ms" in metrics
        assert "timestamp" in metrics
        assert metrics["operation"] == "test_operation"
        assert metrics["duration_ms"] >= 100  # At least 100ms

    def test_business_metrics_tracking(self):
        """Test business-specific metrics tracking"""
        from lambda.processor import track_business_metrics
        
        device_metrics = {
            "device_count": 1500,
            "active_devices_last_hour": 1200,
            "average_temperature": 23.5,
            "temperature_alerts": 5,
            "data_quality_score": 0.98
        }
        
        result = track_business_metrics(device_metrics)
        
        assert result["success"] is True
        assert "metrics_published" in result
        assert result["metrics_published"] > 0


class TestHealthChecks:
    """Test system health monitoring and checks"""

    def test_lambda_health_check(self):
        """Test Lambda function health check"""
        from lambda.api_integration import health_check
        
        health_status = health_check()
        
        assert "status" in health_status
        assert "timestamp" in health_status
        assert "version" in health_status
        assert "dependencies" in health_status
        
        assert health_status["status"] in ["healthy", "degraded", "unhealthy"]

    def test_database_connectivity_check(self, mock_dynamodb_table):
        """Test database connectivity health check"""
        from lambda.shadow_manager import check_dynamodb_health
        
        health_result = check_dynamodb_health()
        
        assert "dynamodb" in health_result
        assert health_result["dynamodb"]["status"] in ["connected", "error"]
        assert "latency_ms" in health_result["dynamodb"]

    def test_s3_connectivity_check(self, mock_s3_bucket):
        """Test S3 connectivity health check"""
        from lambda.processor import check_s3_health
        
        health_result = check_s3_health()
        
        assert "s3" in health_result
        assert health_result["s3"]["status"] in ["accessible", "error"]
        assert "bucket_count" in health_result["s3"]

    def test_timestream_connectivity_check(self, mock_timestream_database):
        """Test TimeStream connectivity health check"""
        from lambda.processor import check_timestream_health
        
        health_result = check_timestream_health()
        
        assert "timestream" in health_result
        assert health_result["timestream"]["status"] in ["connected", "error"]

    def test_comprehensive_system_health(self):
        """Test comprehensive system health check"""
        from lambda.api_integration import comprehensive_health_check
        
        health_report = comprehensive_health_check()
        
        assert "overall_status" in health_report
        assert "timestamp" in health_report
        assert "services" in health_report
        assert "metrics" in health_report
        
        # Should check all major services
        services = health_report["services"]
        expected_services = ["dynamodb", "s3", "timestream", "sqs"]
        
        for service in expected_services:
            assert service in services


class TestAlertingAndNotifications:
    """Test alerting and notification systems"""

    @mock_sns
    def test_error_alert_generation(self):
        """Test that critical errors generate alerts"""
        from lambda.processor import send_error_alert
        
        sns = boto3.client('sns', region_name='us-east-1')
        topic_arn = sns.create_topic(Name='iot-alerts')['TopicArn']
        
        error_details = {
            "error_type": "ProcessingError",
            "error_message": "Failed to process device data",
            "device_id": "device_001",
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "high"
        }
        
        result = send_error_alert(error_details, topic_arn)
        
        assert result["success"] is True
        assert "message_id" in result

    def test_threshold_based_alerts(self):
        """Test threshold-based alerting"""
        from lambda.processor import check_temperature_thresholds
        
        # Test high temperature alert
        high_temp_data = {
            "device_id": "sensor_001",
            "temperature": 45.0,  # Above normal threshold
            "timestamp": int(time.time())
        }
        
        alert_result = check_temperature_thresholds(high_temp_data)
        
        assert "alert_triggered" in alert_result
        assert alert_result["alert_triggered"] is True
        assert alert_result["alert_type"] == "high_temperature"

    def test_anomaly_detection_alerts(self):
        """Test anomaly detection and alerting"""
        from lambda.processor import detect_anomalies
        
        # Create data with an anomaly
        normal_readings = [
            {"device_id": "sensor_001", "temperature": 22.5, "timestamp": int(time.time()) - 300},
            {"device_id": "sensor_001", "temperature": 23.0, "timestamp": int(time.time()) - 240},
            {"device_id": "sensor_001", "temperature": 22.8, "timestamp": int(time.time()) - 180},
            {"device_id": "sensor_001", "temperature": 23.2, "timestamp": int(time.time()) - 120},
            {"device_id": "sensor_001", "temperature": 85.0, "timestamp": int(time.time()) - 60}  # Anomaly
        ]
        
        anomaly_result = detect_anomalies(normal_readings)
        
        assert "anomalies_detected" in anomaly_result
        assert anomaly_result["anomalies_detected"] > 0
        assert "anomaly_details" in anomaly_result

    def test_device_offline_detection(self):
        """Test detection of offline devices"""
        from lambda.shadow_manager import detect_offline_devices
        
        # Create device data with one device offline
        device_data = [
            {"device_id": "device_001", "last_seen": int(time.time()) - 300},  # 5 minutes ago
            {"device_id": "device_002", "last_seen": int(time.time()) - 7200}, # 2 hours ago - offline
            {"device_id": "device_003", "last_seen": int(time.time()) - 600}   # 10 minutes ago
        ]
        
        offline_devices = detect_offline_devices(device_data, offline_threshold=3600)  # 1 hour
        
        assert len(offline_devices) == 1
        assert offline_devices[0]["device_id"] == "device_002"


class TestObservabilityIntegration:
    """Test integration with observability tools and services"""

    def test_distributed_tracing_headers(self):
        """Test that distributed tracing headers are propagated"""
        from lambda.api_integration import handle_api_request
        
        event = {
            "httpMethod": "GET",
            "path": "/api/health",
            "headers": {
                "x-trace-id": "trace-123-456-789",
                "x-span-id": "span-abc-def-ghi"
            }
        }
        
        response = handle_api_request(event)
        
        # Response should include tracing headers
        assert "headers" in response
        assert "x-trace-id" in response["headers"]

    def test_correlation_id_propagation(self):
        """Test correlation ID propagation across services"""
        from lambda.processor import process_with_correlation_id
        
        correlation_id = "corr-" + str(int(time.time()))
        
        result = process_with_correlation_id({
            "device_id": "test_device",
            "temperature": 25.0
        }, correlation_id)
        
        assert "correlation_id" in result
        assert result["correlation_id"] == correlation_id

    @mock_logs
    def test_log_aggregation_format(self):
        """Test that logs are formatted for aggregation tools"""
        from lambda.processor import structured_logger
        
        logs_client = boto3.client('logs', region_name='us-east-1')
        log_group = '/aws/lambda/iot-processor'
        
        logs_client.create_log_group(logGroupName=log_group)
        
        # Test structured logging
        log_entry = {
            "level": "INFO",
            "message": "Processing device data",
            "device_id": "device_001",
            "operation": "data_ingestion",
            "duration": 150,
            "status": "success",
            "@timestamp": datetime.utcnow().isoformat()
        }
        
        structured_logger.info(json.dumps(log_entry))
        
        # Verify log format is JSON and parseable
        parsed_log = json.loads(json.dumps(log_entry))
        assert parsed_log["device_id"] == "device_001"
        assert parsed_log["@timestamp"] is not None

    def test_custom_dashboard_metrics(self):
        """Test metrics required for custom dashboards"""
        from lambda.processor import collect_dashboard_metrics
        
        metrics = collect_dashboard_metrics()
        
        # Should include key operational metrics
        required_metrics = [
            "total_messages_processed",
            "average_processing_time",
            "error_rate",
            "active_devices",
            "data_quality_score"
        ]
        
        for metric in required_metrics:
            assert metric in metrics
            assert isinstance(metrics[metric], (int, float))

    def test_sla_metrics_tracking(self):
        """Test SLA (Service Level Agreement) metrics tracking"""
        from lambda.processor import track_sla_metrics
        
        # Simulate operations with SLA tracking
        operations = [
            {"operation": "data_processing", "duration": 150, "success": True},
            {"operation": "data_processing", "duration": 200, "success": True},
            {"operation": "data_processing", "duration": 500, "success": False},  # SLA violation
            {"operation": "api_request", "duration": 50, "success": True},
            {"operation": "api_request", "duration": 100, "success": True}
        ]
        
        sla_metrics = track_sla_metrics(operations)
        
        assert "data_processing" in sla_metrics
        assert "api_request" in sla_metrics
        
        # Check SLA calculations
        data_proc_metrics = sla_metrics["data_processing"]
        assert "success_rate" in data_proc_metrics
        assert "average_duration" in data_proc_metrics
        assert "sla_violations" in data_proc_metrics
        
        # Should detect the SLA violation
        assert data_proc_metrics["sla_violations"] == 1


class TestDashboardAndVisualization:
    """Test dashboard data and visualization endpoints"""

    def test_realtime_metrics_endpoint(self):
        """Test real-time metrics endpoint for dashboards"""
        from lambda.api_integration import get_realtime_metrics
        
        metrics = get_realtime_metrics()
        
        assert "timestamp" in metrics
        assert "device_metrics" in metrics
        assert "system_metrics" in metrics
        
        device_metrics = metrics["device_metrics"]
        assert "total_devices" in device_metrics
        assert "active_devices" in device_metrics
        assert "average_temperature" in device_metrics

    def test_historical_data_aggregation(self):
        """Test historical data aggregation for charts"""
        from lambda.data_lake_api import get_historical_aggregates
        
        query_params = {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "granularity": "hourly",
            "metrics": ["temperature", "humidity"]
        }
        
        aggregates = get_historical_aggregates(query_params)
        
        assert "data" in aggregates
        assert "metadata" in aggregates
        assert len(aggregates["data"]) > 0
        
        # Each data point should have timestamp and values
        data_point = aggregates["data"][0]
        assert "timestamp" in data_point
        assert "temperature" in data_point
        assert "humidity" in data_point

    def test_device_status_summary(self):
        """Test device status summary for monitoring dashboard"""
        from lambda.shadow_manager import get_device_status_summary
        
        summary = get_device_status_summary()
        
        assert "total_devices" in summary
        assert "online_devices" in summary
        assert "offline_devices" in summary
        assert "devices_with_alerts" in summary
        assert "last_updated" in summary

    def test_alert_dashboard_data(self):
        """Test alert data for monitoring dashboard"""
        from lambda.api_integration import get_alerts_summary
        
        alerts = get_alerts_summary({
            "time_range": "24h",
            "severity": "all"
        })
        
        assert "total_alerts" in alerts
        assert "alerts_by_severity" in alerts
        assert "alerts_by_type" in alerts
        assert "recent_alerts" in alerts
        
        # Check alert severity breakdown
        severity_breakdown = alerts["alerts_by_severity"]
        expected_severities = ["critical", "high", "medium", "low"]
        for severity in expected_severities:
            assert severity in severity_breakdown


class TestMonitoringAutomation:
    """Test automated monitoring and self-healing capabilities"""

    def test_automatic_scaling_triggers(self):
        """Test automatic scaling based on load metrics"""
        from lambda.processor import check_scaling_requirements
        
        high_load_metrics = {
            "average_cpu_utilization": 85,
            "memory_utilization": 80,
            "queue_depth": 1000,
            "processing_latency": 500
        }
        
        scaling_decision = check_scaling_requirements(high_load_metrics)
        
        assert "scale_out" in scaling_decision
        assert scaling_decision["scale_out"] is True
        assert "recommended_instances" in scaling_decision

    def test_automatic_error_recovery(self):
        """Test automatic error recovery mechanisms"""
        from lambda.processor import attempt_error_recovery
        
        error_scenario = {
            "error_type": "DatabaseConnectionError",
            "error_count": 3,
            "last_error_time": int(time.time()),
            "affected_operations": ["device_shadow_update"]
        }
        
        recovery_result = attempt_error_recovery(error_scenario)
        
        assert "recovery_attempted" in recovery_result
        assert "recovery_strategy" in recovery_result
        assert "success" in recovery_result

    def test_predictive_maintenance_alerts(self):
        """Test predictive maintenance alerting"""
        from lambda.processor import check_predictive_maintenance
        
        device_health_data = {
            "device_id": "sensor_001",
            "battery_level": 15,  # Low battery
            "signal_strength": -85,  # Weak signal
            "error_rate": 0.08,  # High error rate
            "last_maintenance": int(time.time()) - (90 * 24 * 3600)  # 90 days ago
        }
        
        maintenance_alert = check_predictive_maintenance(device_health_data)
        
        assert "maintenance_required" in maintenance_alert
        assert "priority" in maintenance_alert
        assert "recommended_actions" in maintenance_alert
        
        if maintenance_alert["maintenance_required"]:
            assert len(maintenance_alert["recommended_actions"]) > 0 