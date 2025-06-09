#!/usr/bin/env python3
"""
Production IoT PoC Deployment Manager
Uses AWS SDK instead of CLI for production deployment and management
"""

import boto3
import json
import time
import logging
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError, BotoCoreError
from dataclasses import dataclass
from pathlib import Path


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DeploymentConfig:
    """Deployment configuration"""
    stack_name: str = "IotPocStack"
    region: str = "us-west-2"
    environment: str = "production"
    # Legacy Kafka parameters (not used in SQS pipeline)
    kafka_instance_type: str = "kafka.m5.large"
    kafka_nodes: int = 3
    kafka_storage_size: int = 100  # GB
    lambda_memory: int = 512  # MB
    lambda_timeout: int = 60  # seconds


class ModelSrvError(Exception):
    """Custom error for deployment service operations"""
    pass


class DeploymentManager:
    """
    Production deployment manager using AWS SDK
    """
    
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.session = boto3.Session()
        
        # Initialize AWS clients
        try:
            self.cloudformation = self.session.client('cloudformation', region_name=config.region)
            self.sqs = self.session.client('sqs', region_name=config.region)
            self.lambda_client = self.session.client('lambda', region_name=config.region)
            self.iot = self.session.client('iot', region_name=config.region)
            self.timestream_write = self.session.client('timestream-write', region_name=config.region)
            self.s3 = self.session.client('s3', region_name=config.region)
            self.sts = self.session.client('sts', region_name=config.region)
        except Exception as e:
            raise ModelSrvError(f"Failed to initialize AWS clients: {e}")
    
    def get_caller_identity(self) -> Dict[str, str]:
        """Get AWS caller identity"""
        try:
            response = self.sts.get_caller_identity()
            return {
                'account': response['Account'],
                'user_id': response['UserId'],
                'arn': response['Arn']
            }
        except ClientError as e:
            raise ModelSrvError(f"Failed to get caller identity: {e}")
    
    def deploy_stack(self, template_path: str, parameters: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Deploy CloudFormation stack
        
        Args:
            template_path: Path to CloudFormation template
            parameters: Stack parameters
            
        Returns:
            Deployment result
        """
        try:
            # Read template
            with open(template_path, 'r') as f:
                template_body = f.read()
            
            # Prepare parameters
            cf_parameters = []
            if parameters:
                for key, value in parameters.items():
                    cf_parameters.append({
                        'ParameterKey': key,
                        'ParameterValue': str(value)
                    })
            
            # Check if stack exists
            stack_exists = self._stack_exists()
            
            if stack_exists:
                logger.info(f"Updating existing stack: {self.config.stack_name}")
                response = self.cloudformation.update_stack(
                    StackName=self.config.stack_name,
                    TemplateBody=template_body,
                    Parameters=cf_parameters,
                    Capabilities=['CAPABILITY_IAM']
                )
                action = 'UPDATE'
            else:
                logger.info(f"Creating new stack: {self.config.stack_name}")
                response = self.cloudformation.create_stack(
                    StackName=self.config.stack_name,
                    TemplateBody=template_body,
                    Parameters=cf_parameters,
                    Capabilities=['CAPABILITY_IAM'],
                    Tags=[
                        {'Key': 'Environment', 'Value': self.config.environment},
                        {'Key': 'Project', 'Value': 'IoT-PoC'},
                        {'Key': 'ManagedBy', 'Value': 'AWS-CDK'}
                    ]
                )
                action = 'CREATE'
            
            # Wait for completion
            stack_id = response['StackId']
            self._wait_for_stack_completion(action)
            
            return {
                'action': action,
                'stack_id': stack_id,
                'outputs': self.get_stack_outputs()
            }
            
        except ClientError as e:
            raise ModelSrvError(f"Failed to deploy stack: {e}")
    
    def _stack_exists(self) -> bool:
        """Check if CloudFormation stack exists"""
        try:
            self.cloudformation.describe_stacks(StackName=self.config.stack_name)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                return False
            raise
    
    def _wait_for_stack_completion(self, action: str) -> None:
        """Wait for CloudFormation stack operation to complete"""
        if action == 'CREATE':
            waiter = self.cloudformation.get_waiter('stack_create_complete')
        elif action == 'UPDATE':
            waiter = self.cloudformation.get_waiter('stack_update_complete')
        else:
            raise ValueError(f"Unknown action: {action}")
        
        logger.info(f"Waiting for stack {action.lower()} to complete...")
        try:
            waiter.wait(
                StackName=self.config.stack_name,
                WaiterConfig={'Delay': 30, 'MaxAttempts': 60}  # 30 minutes max
            )
            logger.info(f"Stack {action.lower()} completed successfully")
        except Exception as e:
            raise ModelSrvError(f"Stack {action.lower()} failed: {e}")
    
    def get_stack_outputs(self) -> Dict[str, str]:
        """Get CloudFormation stack outputs"""
        try:
            response = self.cloudformation.describe_stacks(StackName=self.config.stack_name)
            stack = response['Stacks'][0]
            
            outputs = {}
            for output in stack.get('Outputs', []):
                outputs[output['OutputKey']] = output['OutputValue']
            
            return outputs
        except ClientError as e:
            raise ModelSrvError(f"Failed to get stack outputs: {e}")
    
    def get_sqs_queue_status(self, queue_url: str) -> Dict[str, Any]:
        """
        Get SQS queue status and attributes
        
        Args:
            queue_url: SQS queue URL
            
        Returns:
            Queue status information
        """
        try:
            response = self.sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['All']
            )
            attributes = response['Attributes']
            
            return {
                'queue_url': queue_url,
                'approximate_number_of_messages': int(attributes.get('ApproximateNumberOfMessages', 0)),
                'approximate_number_of_messages_not_visible': int(attributes.get('ApproximateNumberOfMessagesNotVisible', 0)),
                'created_timestamp': attributes.get('CreatedTimestamp'),
                'visibility_timeout': int(attributes.get('VisibilityTimeout', 0)),
                'message_retention_period': int(attributes.get('MessageRetentionPeriod', 0)),
                'receive_message_wait_time': int(attributes.get('ReceiveMessageWaitTimeSeconds', 0)),
                'dead_letter_target_arn': attributes.get('RedrivePolicy', {})
            }
        except ClientError as e:
            raise ModelSrvError(f"Failed to get SQS queue status: {e}")
    
    def send_test_sqs_message(self, queue_url: str, message: Dict[str, Any]) -> bool:
        """
        Send test message to SQS queue
        
        Args:
            queue_url: SQS queue URL
            message: Message payload
            
        Returns:
            True if successful
        """
        try:
            response = self.sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message)
            )
            
            logger.info(f"Successfully sent message to SQS: {response.get('MessageId')}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to send SQS message: {e}")
            return False
    
    def test_lambda_function(self, function_name: str, test_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test Lambda function with sample payload
        
        Args:
            function_name: Lambda function name
            test_payload: Test payload
            
        Returns:
            Function response
        """
        try:
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(test_payload)
            )
            
            result = {
                'status_code': response['StatusCode'],
                'payload': json.loads(response['Payload'].read())
            }
            
            if 'FunctionError' in response:
                result['error'] = response['FunctionError']
            
            return result
            
        except ClientError as e:
            raise ModelSrvError(f"Failed to test Lambda function: {e}")
    
    def send_test_iot_message(self, topic: str, message: Dict[str, Any]) -> bool:
        """
        Send test message to IoT Core
        
        Args:
            topic: IoT topic
            message: Message payload
            
        Returns:
            True if successful
        """
        try:
            # Get IoT endpoint
            endpoint_response = self.iot.describe_endpoint(endpointType='iot:Data-ATS')
            endpoint = endpoint_response['endpointAddress']
            
            # Create IoT data client
            iot_data = self.session.client('iot-data', endpoint_url=f'https://{endpoint}')
            
            # Publish message
            iot_data.publish(
                topic=topic,
                payload=json.dumps(message)
            )
            
            logger.info(f"Successfully published message to topic: {topic}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to send IoT message: {e}")
            return False
    
    def query_timestream(self, query: str) -> List[Dict[str, Any]]:
        """
        Query TimeStream database
        
        Args:
            query: SQL query string
            
        Returns:
            Query results
        """
        try:
            # Create TimeStream query client
            timestream_query = self.session.client('timestream-query', region_name=self.config.region)
            
            response = timestream_query.query(QueryString=query)
            
            # Parse results
            results = []
            for row in response['Rows']:
                record = {}
                for i, col in enumerate(response['ColumnInfo']):
                    col_name = col['Name']
                    col_value = row['Data'][i].get('ScalarValue', '')
                    record[col_name] = col_value
                results.append(record)
            
            return results
            
        except ClientError as e:
            raise ModelSrvError(f"Failed to query TimeStream: {e}")
    
    def cleanup_stack(self) -> bool:
        """
        Clean up CloudFormation stack and associated resources
        
        Returns:
            True if successful
        """
        try:
            # Get stack outputs before deletion
            outputs = self.get_stack_outputs()
            
            # Empty S3 bucket if exists
            bucket_name = outputs.get('S3BucketName')
            if bucket_name:
                self._empty_s3_bucket(bucket_name)
            
            # Delete CloudFormation stack
            logger.info(f"Deleting CloudFormation stack: {self.config.stack_name}")
            self.cloudformation.delete_stack(StackName=self.config.stack_name)
            
            # Wait for deletion
            waiter = self.cloudformation.get_waiter('stack_delete_complete')
            waiter.wait(
                StackName=self.config.stack_name,
                WaiterConfig={'Delay': 30, 'MaxAttempts': 60}
            )
            
            logger.info("Stack deletion completed successfully")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to cleanup stack: {e}")
            return False
    
    def _empty_s3_bucket(self, bucket_name: str) -> None:
        """Empty S3 bucket before deletion"""
        try:
            # List and delete all objects
            paginator = self.s3.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name):
                if 'Contents' in page:
                    objects = [{'Key': obj['Key']} for obj in page['Contents']]
                    self.s3.delete_objects(
                        Bucket=bucket_name,
                        Delete={'Objects': objects}
                    )
            logger.info(f"Emptied S3 bucket: {bucket_name}")
        except ClientError as e:
            logger.warning(f"Failed to empty S3 bucket {bucket_name}: {e}")


def main():
    """Main deployment workflow"""
    config = DeploymentConfig()
    manager = DeploymentManager(config)
    
    try:
        # Get caller identity
        identity = manager.get_caller_identity()
        logger.info(f"Deploying as: {identity['arn']}")
        
        # Deploy stack (assuming CDK synthesized template exists)
        template_path = "cdk.out/IotPocStack.template.json"
        if not Path(template_path).exists():
            raise ModelSrvError(f"Template not found: {template_path}. Run 'cdk synth' first.")
        
        result = manager.deploy_stack(template_path)
        logger.info(f"Deployment {result['action']} completed")
        
        # Get outputs
        outputs = result['outputs']
        logger.info("Stack outputs:")
        for key, value in outputs.items():
            logger.info(f"  {key}: {value}")
        
        # Verify SQS queue if created
        sqs_url = outputs.get('SQSQueueUrl')
        if sqs_url:
            status = manager.get_sqs_queue_status(sqs_url)
            logger.info(f"SQS queue status: {status}")
        
        logger.info("🎉 Production deployment completed successfully!")
        
    except ModelSrvError as e:
        logger.error(f"Deployment failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 