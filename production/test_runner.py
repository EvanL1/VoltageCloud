#!/usr/bin/env python3
"""
Production IoT PoC Test Runner
Runs comprehensive tests using AWS SDK instead of CLI
"""

import boto3
import json
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from deployment_manager import DeploymentManager, DeploymentConfig, ModelSrvError


logger = logging.getLogger(__name__)


@dataclass
class TestConfig:
    """Test configuration"""
    test_device_count: int = 5
    test_duration_minutes: int = 10
    test_message_interval_seconds: int = 30
    validate_timestream: bool = True
    validate_s3: bool = True


class ProductionTestRunner:
    """
    Comprehensive test runner for production IoT PoC deployment
    """
    
    def __init__(self, deployment_manager: DeploymentManager, test_config: TestConfig):
        self.manager = deployment_manager
        self.config = test_config
        self.test_results = {
            'start_time': None,
            'end_time': None,
            'tests_passed': 0,
            'tests_failed': 0,
            'test_details': []
        }
    
    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """
        Run comprehensive production tests
        
        Returns:
            Test results summary
        """
        self.test_results['start_time'] = datetime.utcnow().isoformat()
        logger.info("🧪 Starting comprehensive production tests...")
        
        # Get stack outputs
        try:
            outputs = self.manager.get_stack_outputs()
        except ModelSrvError as e:
            self._add_test_result("get_stack_outputs", False, str(e))
            return self.test_results
        
        # Test 1: Validate infrastructure
        self._test_infrastructure_health(outputs)
        
        # Test 2: Test IoT Core connectivity
        self._test_iot_connectivity(outputs)
        
        # Test 3: Test SQS integration
        self._test_sqs_integration(outputs)
        
        # Test 4: Test Lambda function
        self._test_lambda_function(outputs)
        
        # Test 5: Send test messages
        self._test_message_flow(outputs)
        
        # Test 6: Validate data in TimeStream
        if self.config.validate_timestream:
            self._test_timestream_data(outputs)
        
        # Test 7: Validate data in S3
        if self.config.validate_s3:
            self._test_s3_data(outputs)
        
        # Test 8: Performance test
        self._test_performance(outputs)
        
        self.test_results['end_time'] = datetime.utcnow().isoformat()
        
        # Generate summary
        total_tests = self.test_results['tests_passed'] + self.test_results['tests_failed']
        success_rate = (self.test_results['tests_passed'] / total_tests * 100) if total_tests > 0 else 0
        
        logger.info(f"🎯 Tests completed: {self.test_results['tests_passed']}/{total_tests} passed ({success_rate:.1f}%)")
        
        return self.test_results
    
    def _add_test_result(self, test_name: str, passed: bool, details: str = "") -> None:
        """Add test result to summary"""
        if passed:
            self.test_results['tests_passed'] += 1
            logger.info(f"✅ {test_name}: PASSED")
        else:
            self.test_results['tests_failed'] += 1
            logger.error(f"❌ {test_name}: FAILED - {details}")
        
        self.test_results['test_details'].append({
            'test_name': test_name,
            'passed': passed,
            'details': details,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def _test_infrastructure_health(self, outputs: Dict[str, str]) -> None:
        """Test infrastructure health"""
        logger.info("🏗️ Testing infrastructure health...")
        
        # Test SQS queue
        sqs_url = outputs.get('SQSQueueUrl')
        if sqs_url:
            try:
                status = self.manager.get_sqs_queue_status(sqs_url)
                self._add_test_result("sqs_queue_available", True, f"Messages: {status['approximate_number_of_messages']}")
            except Exception as e:
                self._add_test_result("sqs_queue_available", False, str(e))
        else:
            self._add_test_result("sqs_queue_url", False, "SQS queue URL not found")
        
        # Test Lambda function
        lambda_name = outputs.get('LambdaFunctionName')
        if lambda_name:
            try:
                response = self.manager.lambda_client.get_function(FunctionName=lambda_name)
                state = response['Configuration']['State']
                if state == 'Active':
                    self._add_test_result("lambda_function_active", True)
                else:
                    self._add_test_result("lambda_function_active", False, f"State: {state}")
            except Exception as e:
                self._add_test_result("lambda_function_active", False, str(e))
        else:
            self._add_test_result("lambda_function_name", False, "Lambda function name not found")
    
    def _test_iot_connectivity(self, outputs: Dict[str, str]) -> None:
        """Test IoT Core connectivity"""
        logger.info("📡 Testing IoT Core connectivity...")
        
        try:
            # Get IoT endpoint
            endpoint_response = self.manager.iot.describe_endpoint(endpointType='iot:Data-ATS')
            endpoint = endpoint_response['endpointAddress']
            self._add_test_result("iot_endpoint_available", True, f"Endpoint: {endpoint}")
        except Exception as e:
            self._add_test_result("iot_endpoint_available", False, str(e))
            return
        
        # Test topic rule
        try:
            rule_response = self.manager.iot.get_topic_rule(ruleName='iot_poc_to_sqs')
            if rule_response['rule']['ruleDisabled'] == False:
                self._add_test_result("iot_topic_rule_enabled", True)
            else:
                self._add_test_result("iot_topic_rule_enabled", False, "Rule is disabled")
        except Exception as e:
            self._add_test_result("iot_topic_rule_enabled", False, str(e))
    
    def _test_sqs_integration(self, outputs: Dict[str, str]) -> None:
        """Test SQS integration"""
        logger.info("🔄 Testing SQS integration...")
        
        lambda_name = outputs.get('LambdaFunctionName')
        if not lambda_name:
            self._add_test_result("sqs_event_source", False, "Lambda function name not found")
            return
        
        try:
            # Check event source mappings
            response = self.manager.lambda_client.list_event_source_mappings(FunctionName=lambda_name)
            sqs_sources = [esm for esm in response['EventSourceMappings'] if 'sqs' in esm.get('EventSourceArn', '').lower()]
            
            if sqs_sources:
                for esm in sqs_sources:
                    if esm['State'] == 'Enabled':
                        self._add_test_result("sqs_event_source", True, f"State: {esm['State']}")
                    else:
                        self._add_test_result("sqs_event_source", False, f"State: {esm['State']}")
            else:
                self._add_test_result("sqs_event_source", False, "No SQS event source mappings found")
        except Exception as e:
            self._add_test_result("sqs_event_source", False, str(e))
    
    def _test_lambda_function(self, outputs: Dict[str, str]) -> None:
        """Test Lambda function directly"""
        logger.info("⚡ Testing Lambda function...")
        
        lambda_name = outputs.get('LambdaFunctionName')
        if not lambda_name:
            self._add_test_result("lambda_direct_test", False, "Lambda function name not found")
            return
        
        # Create test SQS event payload
        test_payload = {
            "Records": [
                {
                    "messageId": "test-message-id",
                    "body": json.dumps({
                        "ts": int(time.time() * 1000),
                        "temp": 25.5,
                        "humidity": 60.0,
                        "device_id": "test-device",
                        "test_mode": True
                    })
                }
            ]
        }
        
        try:
            result = self.manager.test_lambda_function(lambda_name, test_payload)
            if result['status_code'] == 200 and 'error' not in result:
                payload = result['payload']
                if payload.get('successful_records', 0) > 0:
                    self._add_test_result("lambda_direct_test", True, f"Processed {payload['successful_records']} records")
                else:
                    self._add_test_result("lambda_direct_test", False, f"No records processed: {payload}")
            else:
                self._add_test_result("lambda_direct_test", False, f"Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self._add_test_result("lambda_direct_test", False, str(e))
    
    def _test_message_flow(self, outputs: Dict[str, str]) -> None:
        """Test end-to-end message flow"""
        logger.info("📨 Testing end-to-end message flow...")
        
        messages_sent = 0
        messages_failed = 0
        
        for i in range(self.config.test_device_count):
            device_id = f"test-device-{i:03d}"
            topic = f"devices/{device_id}/data"
            
            message = {
                "ts": int(time.time() * 1000),
                "temp": 20.0 + (i * 2.5),
                "humidity": 50.0 + (i * 5),
                "voltage": 220 + (i * 2),
                "test_run": True,
                "device_id": device_id
            }
            
            try:
                success = self.manager.send_test_iot_message(topic, message)
                if success:
                    messages_sent += 1
                else:
                    messages_failed += 1
                
                # Wait between messages to avoid throttling
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to send message for device {device_id}: {e}")
                messages_failed += 1
        
        if messages_sent > 0:
            self._add_test_result("message_flow", True, f"Sent {messages_sent}/{self.config.test_device_count} messages")
        else:
            self._add_test_result("message_flow", False, f"Failed to send any messages ({messages_failed} failed)")
        
        # Wait for messages to be processed
        logger.info("⏳ Waiting for messages to be processed...")
        time.sleep(30)
    
    def _test_timestream_data(self, outputs: Dict[str, str]) -> None:
        """Test TimeStream data"""
        logger.info("📊 Testing TimeStream data...")
        
        query = "SELECT COUNT(*) as record_count FROM iot_poc.metrics WHERE time > ago(5m)"
        
        try:
            results = self.manager.query_timestream(query)
            if results and len(results) > 0:
                record_count = int(results[0].get('record_count', 0))
                if record_count > 0:
                    self._add_test_result("timestream_data", True, f"Found {record_count} records")
                else:
                    self._add_test_result("timestream_data", False, "No records found in TimeStream")
            else:
                self._add_test_result("timestream_data", False, "No query results")
        except Exception as e:
            self._add_test_result("timestream_data", False, str(e))
    
    def _test_s3_data(self, outputs: Dict[str, str]) -> None:
        """Test S3 data"""
        logger.info("💾 Testing S3 data...")
        
        bucket_name = outputs.get('S3BucketName')
        if not bucket_name:
            self._add_test_result("s3_data", False, "S3 bucket name not found")
            return
        
        try:
            # List objects in raw/ prefix
            response = self.manager.s3.list_objects_v2(
                Bucket=bucket_name,
                Prefix='raw/',
                MaxKeys=10
            )
            
            object_count = response.get('KeyCount', 0)
            if object_count > 0:
                self._add_test_result("s3_data", True, f"Found {object_count} objects in S3")
            else:
                self._add_test_result("s3_data", False, "No objects found in S3")
        except Exception as e:
            self._add_test_result("s3_data", False, str(e))
    
    def _test_performance(self, outputs: Dict[str, str]) -> None:
        """Test basic performance metrics"""
        logger.info("🚀 Testing performance...")
        
        lambda_name = outputs.get('LambdaFunctionName')
        if not lambda_name:
            self._add_test_result("performance_test", False, "Lambda function name not found")
            return
        
        try:
            # Get CloudWatch metrics for Lambda
            cloudwatch = self.manager.session.client('cloudwatch', region_name=self.manager.config.region)
            
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=10)
            
            # Get duration metrics
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Duration',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': lambda_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average', 'Maximum']
            )
            
            if response['Datapoints']:
                avg_duration = sum(dp['Average'] for dp in response['Datapoints']) / len(response['Datapoints'])
                max_duration = max(dp['Maximum'] for dp in response['Datapoints'])
                
                # Consider performance good if average duration < 5 seconds
                if avg_duration < 5000:  # milliseconds
                    self._add_test_result("performance_test", True, f"Avg: {avg_duration:.0f}ms, Max: {max_duration:.0f}ms")
                else:
                    self._add_test_result("performance_test", False, f"High latency - Avg: {avg_duration:.0f}ms")
            else:
                self._add_test_result("performance_test", False, "No CloudWatch metrics available")
                
        except Exception as e:
            self._add_test_result("performance_test", False, str(e))
    



def main():
    """Run production tests"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Initialize managers
        deployment_config = DeploymentConfig()
        deployment_manager = DeploymentManager(deployment_config)
        
        test_config = TestConfig()
        test_runner = ProductionTestRunner(deployment_manager, test_config)
        
        # Run tests
        results = test_runner.run_comprehensive_tests()
        
        # Print final results
        logger.info("=" * 60)
        logger.info("🎯 FINAL TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Total tests: {results['tests_passed'] + results['tests_failed']}")
        logger.info(f"Passed: {results['tests_passed']}")
        logger.info(f"Failed: {results['tests_failed']}")
        
        if results['tests_failed'] == 0:
            logger.info("🎉 All tests passed! Production deployment is healthy.")
            return 0
        else:
            logger.error("❌ Some tests failed. Check the logs above for details.")
            return 1
            
    except Exception as e:
        logger.error(f"Test runner failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main()) 