"""
IoT PoC Stack: MQTT → IoT Core → SQS → Lambda → TimeStream & S3
Complete infrastructure setup for IoT data pipeline with Amazon SQS
"""

from aws_cdk import (
    Stack, Duration, CfnOutput,
    aws_iot as iot,
    aws_sqs as sqs,
    aws_lambda as _lambda,
    aws_timestream as ts,
    aws_s3 as s3,
    aws_iam as iam,
    aws_logs as logs,
    aws_lambda_event_sources as event_sources,
)
from constructs import Construct
import os


class IotPocStack(Stack):
    """
    Main IoT PoC Infrastructure Stack
    Creates all necessary resources for the IoT data pipeline with SQS
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1️⃣ SQS Queue for IoT messages
        iot_queue = sqs.Queue(
            self, "IoTDataQueue",
            queue_name="iot-data-queue",
            visibility_timeout=Duration.minutes(5),
            retention_period=Duration.days(14),
            receive_message_wait_time=Duration.seconds(20),  # Long polling
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=sqs.Queue(
                    self, "IoTDataDLQ",
                    queue_name="iot-data-dlq",
                    retention_period=Duration.days(14)
                )
            )
        )

        # 2️⃣ S3 Bucket for cold data storage
        raw_bucket = s3.Bucket(
            self, "RawBucket",
            bucket_name=f"iot-poc-raw-data-{self.account}-{self.region}",
            versioned=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldData",
                    expiration=Duration.days(30),
                    enabled=True
                )
            ]
        )

        # 3️⃣ TimeStream Database and Table for time-series data
        ts_database = ts.CfnDatabase(
            self, "TSDB",
            database_name="iot_poc"
        )

        ts_table = ts.CfnTable(
            self, "TSTable",
            database_name=ts_database.database_name,
            table_name="metrics",
            retention_properties={
                "MemoryStoreRetentionPeriodInHours": "24",
                "MagneticStoreRetentionPeriodInDays": "365"
            }
        )
        ts_table.node.add_dependency(ts_database)

        # 4️⃣ IAM Role for IoT Core to write to SQS
        iot_role = iam.Role(
            self, "IoTSQSRole",
            assumed_by=iam.ServicePrincipal("iot.amazonaws.com"),
            inline_policies={
                "SQSWritePolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sqs:SendMessage"
                            ],
                            resources=[iot_queue.queue_arn]
                        )
                    ]
                )
            }
        )

        # 5️⃣ Lambda Function for processing SQS messages
        processor_lambda = _lambda.Function(
            self, "SQSProcessor",
            function_name="iot-poc-sqs-processor",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="processor.handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                "TDB": ts_database.database_name,
                "TBL": ts_table.table_name,
                "BUCKET": raw_bucket.bucket_name,
                "REGION": self.region,
                "SQS_QUEUE_URL": iot_queue.queue_url
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )

        # Grant permissions to Lambda
        raw_bucket.grant_write(processor_lambda)
        iot_queue.grant_consume_messages(processor_lambda)
        
        # TimeStream write permissions
        processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "timestream:WriteRecords",
                    "timestream:DescribeEndpoints"
                ],
                resources=["*"]  # TimeStream requires wildcard for WriteRecords
            )
        )

        # Add SQS event source to Lambda
        processor_lambda.add_event_source(
            event_sources.SqsEventSource(
                queue=iot_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(5),
                report_batch_item_failures=True
            )
        )

        # 6️⃣ IoT Topic Rule: MQTT → SQS
        topic_rule = iot.CfnTopicRule(
            self, "RuleToSQS",
            rule_name="iot_poc_to_sqs",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql="SELECT *, topic() as source_topic, timestamp() as event_time FROM 'devices/+/data'",
                aws_iot_sql_version="2016-03-23",
                rule_disabled=False,
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        sqs=iot.CfnTopicRule.SqsActionProperty(
                            queue_url=iot_queue.queue_url,
                            role_arn=iot_role.role_arn,
                            use_base64=False
                        )
                    )
                ]
            )
        )

        # 📤 Stack Outputs
        CfnOutput(
            self, "SQSQueueUrl",
            value=iot_queue.queue_url,
            description="SQS Queue URL for IoT data"
        )

        CfnOutput(
            self, "SQSQueueArn",
            value=iot_queue.queue_arn,
            description="SQS Queue ARN for IoT data"
        )

        CfnOutput(
            self, "DLQUrl",
            value=iot_queue.dead_letter_queue.queue.queue_url,
            description="Dead Letter Queue URL"
        )

        CfnOutput(
            self, "S3BucketName",
            value=raw_bucket.bucket_name,
            description="S3 Bucket for raw data storage"
        )

        CfnOutput(
            self, "TimeStreamDatabase",
            value=ts_database.database_name,
            description="TimeStream Database Name"
        )

        CfnOutput(
            self, "TimeStreamTable",
            value=ts_table.table_name,
            description="TimeStream Table Name"
        )

        CfnOutput(
            self, "LambdaFunctionName",
            value=processor_lambda.function_name,
            description="Lambda Function Name for processing"
        )

        CfnOutput(
            self, "IoTTopicRule",
            value=topic_rule.rule_name,
            description="IoT Topic Rule Name"
        ) 