#!/usr/bin/env python3
"""
Production Configuration Management
Environment-based configuration for production deployments
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from environs import Env


env = Env()

@dataclass
class AWSConfig:
    """AWS-specific configuration"""
    region: str = env.str("AWS_REGION", "us-west-2")
    account_id: str = env.str("AWS_ACCOUNT_ID", "")
    profile: Optional[str] = env.str("AWS_PROFILE", None)
    
    # IAM roles
    execution_role_arn: Optional[str] = env.str("AWS_EXECUTION_ROLE_ARN", None)
    cross_account_role_arn: Optional[str] = env.str("AWS_CROSS_ACCOUNT_ROLE_ARN", None)

@dataclass 
class SQSConfig:
    """SQS configuration"""
    queue_name: str = env.str("SQS_QUEUE_NAME", "iot-data-queue")
    visibility_timeout_seconds: int = env.int("SQS_VISIBILITY_TIMEOUT", 300)
    message_retention_days: int = env.int("SQS_MESSAGE_RETENTION_DAYS", 14)
    receive_message_wait_time_seconds: int = env.int("SQS_RECEIVE_WAIT_TIME", 20)
    
    # Dead Letter Queue configuration
    dlq_name: str = env.str("SQS_DLQ_NAME", "iot-data-dlq")
    max_receive_count: int = env.int("SQS_MAX_RECEIVE_COUNT", 3)


@dataclass
class LambdaConfig:
    """Lambda function configuration"""
    memory_mb: int = env.int("LAMBDA_MEMORY_MB", 512)
    timeout_seconds: int = env.int("LAMBDA_TIMEOUT_SECONDS", 60)
    runtime: str = env.str("LAMBDA_RUNTIME", "python3.12")
    
    # Environment variables for Lambda
    log_level: str = env.str("LAMBDA_LOG_LEVEL", "INFO")
    batch_size: int = env.int("LAMBDA_BATCH_SIZE", 100)
    max_batching_window_seconds: int = env.int("LAMBDA_MAX_BATCHING_WINDOW_SECONDS", 5)


@dataclass
class TimestreamConfig:
    """TimeStream configuration"""
    database_name: str = env.str("TIMESTREAM_DATABASE_NAME", "iot_poc")
    table_name: str = env.str("TIMESTREAM_TABLE_NAME", "metrics")
    
    # Retention configuration
    memory_retention_hours: int = env.int("TIMESTREAM_MEMORY_RETENTION_HOURS", 24)
    magnetic_retention_days: int = env.int("TIMESTREAM_MAGNETIC_RETENTION_DAYS", 30)


@dataclass
class S3Config:
    """S3 configuration"""
    bucket_prefix: str = env.str("S3_BUCKET_PREFIX", "iot-poc")
    
    # Lifecycle configuration
    transition_to_ia_days: int = env.int("S3_TRANSITION_TO_IA_DAYS", 30)
    transition_to_glacier_days: int = env.int("S3_TRANSITION_TO_GLACIER_DAYS", 90)
    expiration_days: int = env.int("S3_EXPIRATION_DAYS", 365)


@dataclass
class MonitoringConfig:
    """Monitoring and alerting configuration"""
    enable_cloudwatch_logs: bool = env.bool("ENABLE_CLOUDWATCH_LOGS", True)
    log_retention_days: int = env.int("LOG_RETENTION_DAYS", 30)
    
    # Alerting
    alert_email: Optional[str] = env.str("ALERT_EMAIL", None)
    slack_webhook_url: Optional[str] = env.str("SLACK_WEBHOOK_URL", None)
    
    # Metrics
    enable_detailed_monitoring: bool = env.bool("ENABLE_DETAILED_MONITORING", True)
    enable_x_ray_tracing: bool = env.bool("ENABLE_X_RAY_TRACING", True)


@dataclass
class SecurityConfig:
    """Security configuration"""
    enable_encryption_at_rest: bool = env.bool("ENABLE_ENCRYPTION_AT_REST", True)
    enable_encryption_in_transit: bool = env.bool("ENABLE_ENCRYPTION_IN_TRANSIT", True)
    
    # KMS
    kms_key_id: Optional[str] = env.str("KMS_KEY_ID", None)
    
    # VPC Security
    allowed_cidr_blocks: list = field(default_factory=lambda: 
        env.list("ALLOWED_CIDR_BLOCKS", ["10.0.0.0/8"], subcast=str))
    
    # Certificate management
    certificate_arn: Optional[str] = env.str("CERTIFICATE_ARN", None)


@dataclass
class ProductionConfig:
    """Complete production configuration"""
    
    # Environment
    environment: str = env.str("ENVIRONMENT", "production")
    stack_name: str = env.str("STACK_NAME", "IotPocStack")
    project_name: str = env.str("PROJECT_NAME", "IoT-PoC")
    
    # Component configurations
    aws: AWSConfig = field(default_factory=AWSConfig)
    sqs: SQSConfig = field(default_factory=SQSConfig)
    lambda_config: LambdaConfig = field(default_factory=LambdaConfig)
    timestream: TimestreamConfig = field(default_factory=TimestreamConfig)
    s3: S3Config = field(default_factory=S3Config)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # Tags for all resources
    default_tags: Dict[str, str] = field(default_factory=lambda: {
        "Environment": env.str("ENVIRONMENT", "production"),
        "Project": env.str("PROJECT_NAME", "IoT-PoC"),
        "Owner": env.str("RESOURCE_OWNER", "platform-team"),
        "CostCenter": env.str("COST_CENTER", "engineering"),
        "ManagedBy": "AWS-CDK"
    })
    
    def to_cdk_parameters(self) -> Dict[str, str]:
        """
        Convert configuration to CDK parameters
        
        Returns:
            Dictionary of CDK parameters
        """
        return {
            # Basic parameters
            "Environment": self.environment,
            "ProjectName": self.project_name,
            
            # SQS parameters
            "SQSQueueName": self.sqs.queue_name,
            "SQSVisibilityTimeout": str(self.sqs.visibility_timeout_seconds),
            "SQSMessageRetentionDays": str(self.sqs.message_retention_days),
            "SQSReceiveWaitTime": str(self.sqs.receive_message_wait_time_seconds),
            
            # Lambda parameters
            "LambdaMemory": str(self.lambda_config.memory_mb),
            "LambdaTimeout": str(self.lambda_config.timeout_seconds),
            "LambdaBatchSize": str(self.lambda_config.batch_size),
            
            # TimeStream parameters
            "TimestreamDatabaseName": self.timestream.database_name,
            "TimestreamTableName": self.timestream.table_name,
            "TimestreamMemoryRetentionHours": str(self.timestream.memory_retention_hours),
            "TimestreamMagneticRetentionDays": str(self.timestream.magnetic_retention_days),
            
            # S3 parameters
            "S3BucketPrefix": self.s3.bucket_prefix,
            
            # Security parameters
            "EnableEncryptionAtRest": str(self.security.enable_encryption_at_rest).lower(),
            "EnableEncryptionInTransit": str(self.security.enable_encryption_in_transit).lower(),
            "KMSKeyId": self.security.kms_key_id or "",
            
            # Monitoring parameters
            "EnableDetailedMonitoring": str(self.monitoring.enable_detailed_monitoring).lower(),
            "EnableXRayTracing": str(self.monitoring.enable_x_ray_tracing).lower(),
            "LogRetentionDays": str(self.monitoring.log_retention_days),
            "AlertEmail": self.monitoring.alert_email or "",
        }
    
    def validate(self) -> list[str]:
        """
        Validate configuration for production deployment
        
        Returns:
            List of validation errors
        """
        errors = []
        
        # Validate AWS configuration
        if not self.aws.region:
            errors.append("AWS region is required")
        
        if not self.aws.account_id:
            errors.append("AWS account ID is required for production")
        
        # Validate SQS configuration for production
        if self.sqs.visibility_timeout_seconds < 60:
            errors.append("SQS visibility timeout should be at least 60 seconds for production")
        
        if self.sqs.max_receive_count < 3:
            errors.append("SQS max receive count should be at least 3 for proper error handling")
        
        # Validate Lambda configuration
        if self.lambda_config.memory_mb < 256:
            errors.append("Lambda memory must be at least 256MB")
        
        if self.lambda_config.timeout_seconds > 900:
            errors.append("Lambda timeout cannot exceed 900 seconds")
        
        # Validate security configuration
        if self.environment == "production":
            if not self.security.enable_encryption_at_rest:
                errors.append("Encryption at rest is required for production")
            
            if not self.security.enable_encryption_in_transit:
                errors.append("Encryption in transit is required for production")
        
        # Validate monitoring configuration
        if self.environment == "production" and not self.monitoring.alert_email:
            errors.append("Alert email is required for production environment")
        
        return errors
    
    @classmethod
    def from_environment(cls, env_file: Optional[str] = None) -> 'ProductionConfig':
        """
        Load configuration from environment variables
        
        Args:
            env_file: Optional path to .env file
            
        Returns:
            Production configuration instance
        """
        if env_file and os.path.exists(env_file):
            env.read_env(env_file)
        
        return cls()
    
    def get_deployment_context(self) -> Dict[str, Any]:
        """
        Get deployment context information
        
        Returns:
            Deployment context
        """
        return {
            "config_summary": {
                "environment": self.environment,
                "region": self.aws.region,
                "sqs_queue_name": self.sqs.queue_name,
                "sqs_retention_days": self.sqs.message_retention_days,
                "lambda_memory": self.lambda_config.memory_mb,
                "encryption_enabled": self.security.enable_encryption_at_rest,
                "monitoring_enabled": self.monitoring.enable_detailed_monitoring
            },
            "estimated_monthly_cost": self._estimate_monthly_cost(),
            "validation_errors": self.validate()
        }
    
    def _estimate_monthly_cost(self) -> Dict[str, float]:
        """
        Estimate monthly costs for production deployment
        
        Returns:
            Cost breakdown by service
        """
        # Rough cost estimates (USD per month)
        costs = {
            "sqs_requests": 5.0,  # Estimated based on message volume (~1M messages)
            "lambda_execution": 30.0,  # Estimated based on usage
            "timestream": 100.0,  # Estimated based on ingestion rate
            "s3_storage": 20.0,  # Estimated based on data volume
            "cloudwatch_logs": 15.0,
            "data_transfer": 10.0  # Lower with SQS
        }
        
        costs["total"] = sum(costs.values())
        return costs
    



def load_production_config(env_file: Optional[str] = None) -> ProductionConfig:
    """
    Load production configuration
    
    Args:
        env_file: Optional environment file path
        
    Returns:
        Production configuration
    """
    return ProductionConfig.from_environment(env_file)


# Example environment configurations
STAGING_ENV = {
    "ENVIRONMENT": "staging",
    "SQS_QUEUE_NAME": "iot-data-queue-staging",
    "SQS_MESSAGE_RETENTION_DAYS": "7",
    "LAMBDA_MEMORY_MB": "256",
    "ENABLE_DETAILED_MONITORING": "false",
    "TIMESTREAM_MAGNETIC_RETENTION_DAYS": "7"
}

PRODUCTION_ENV = {
    "ENVIRONMENT": "production", 
    "SQS_QUEUE_NAME": "iot-data-queue-production",
    "SQS_MESSAGE_RETENTION_DAYS": "14",
    "LAMBDA_MEMORY_MB": "512",
    "ENABLE_DETAILED_MONITORING": "true",
    "ENABLE_X_RAY_TRACING": "true",
    "TIMESTREAM_MAGNETIC_RETENTION_DAYS": "30"
} 