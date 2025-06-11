"""
OTA (Over-the-Air) Update Stack
Implements device firmware update functionality using AWS IoT Device Management
"""

from aws_cdk import (
    Stack, Duration, CfnOutput,
    aws_iot as iot,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_logs as logs,
    aws_dynamodb as dynamodb,
    aws_apigateway as apigateway,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
)
from constructs import Construct


class OtaStack(Stack):
    """
    OTA Update Infrastructure Stack
    Manages device firmware updates with version control and rollback capabilities
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1️⃣ S3 bucket for firmware storage
        firmware_bucket = s3.Bucket(
            self, "FirmwareBucket",
            bucket_name=f"iot-firmware-{self.account}-{self.region}",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldVersions",
                    noncurrent_version_expiration=Duration.days(90),
                    enabled=True
                )
            ]
        )

        # 2️⃣ DynamoDB table for OTA job tracking
        ota_jobs_table = dynamodb.Table(
            self, "OtaJobsTable",
            table_name="ota-jobs",
            partition_key=dynamodb.Attribute(
                name="job_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="device_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=Stack.of(self).removal_policy
        )

        # Add GSI for device-based queries
        ota_jobs_table.add_global_secondary_index(
            index_name="device-index",
            partition_key=dynamodb.Attribute(
                name="device_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            )
        )

        # 3️⃣ Firmware versions table
        firmware_versions_table = dynamodb.Table(
            self, "FirmwareVersionsTable",
            table_name="firmware-versions",
            partition_key=dynamodb.Attribute(
                name="device_type",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="version",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=Stack.of(self).removal_policy
        )

        # 4️⃣ Lambda function for OTA management
        ota_manager = _lambda.Function(
            self, "OtaManager",
            function_name="iot-ota-manager",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="ota_manager.handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "FIRMWARE_BUCKET": firmware_bucket.bucket_name,
                "OTA_JOBS_TABLE": ota_jobs_table.table_name,
                "FIRMWARE_VERSIONS_TABLE": firmware_versions_table.table_name,
                "REGION": self.region
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )

        # Grant permissions to Lambda
        firmware_bucket.grant_read_write(ota_manager)
        ota_jobs_table.grant_read_write_data(ota_manager)
        firmware_versions_table.grant_read_write_data(ota_manager)

        # IoT permissions
        ota_manager.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iot:CreateOTAUpdate",
                    "iot:DeleteOTAUpdate",
                    "iot:DescribeOTAUpdate",
                    "iot:ListOTAUpdates",
                    "iot:GetOTAUpdate",
                    "iot:CreateJob",
                    "iot:DescribeJob",
                    "iot:CancelJob",
                    "iot:DeleteJob",
                    "iot:ListJobs",
                    "iot:CreateStream",
                    "iot:DeleteStream",
                    "iot:DescribeStream",
                    "iot:ListStreams"
                ],
                resources=["*"]
            )
        )

        # 5️⃣ IoT role for OTA updates
        ota_role = iam.Role(
            self, "OtaRole",
            assumed_by=iam.ServicePrincipal("iot.amazonaws.com"),
            inline_policies={
                "OtaPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:GetObjectVersion"
                            ],
                            resources=[f"{firmware_bucket.bucket_arn}/*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "iot:CreateStream",
                                "iot:DeleteStream",
                                "iot:DescribeStream"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        # 6️⃣ Step Functions for OTA workflow
        # Define OTA workflow tasks
        create_ota_job = sfn_tasks.LambdaInvoke(
            self, "CreateOtaJob",
            lambda_function=ota_manager,
            payload=sfn.TaskInput.from_object({
                "action": "create_ota_job",
                "input.$": "$"
            }),
            result_path="$.ota_result"
        )

        wait_for_deployment = sfn.Wait(
            self, "WaitForDeployment",
            time=sfn.WaitTime.duration(Duration.minutes(2))
        )

        check_deployment_status = sfn_tasks.LambdaInvoke(
            self, "CheckDeploymentStatus",
            lambda_function=ota_manager,
            payload=sfn.TaskInput.from_object({
                "action": "check_status",
                "job_id.$": "$.ota_result.Payload.job_id"
            }),
            result_path="$.status_result"
        )

        deployment_success = sfn.Succeed(
            self, "DeploymentSuccess",
            comment="OTA deployment completed successfully"
        )

        deployment_failed = sfn.Fail(
            self, "DeploymentFailed",
            cause="OTA deployment failed",
            error="OTA_DEPLOYMENT_ERROR"
        )

        rollback_deployment = sfn_tasks.LambdaInvoke(
            self, "RollbackDeployment",
            lambda_function=ota_manager,
            payload=sfn.TaskInput.from_object({
                "action": "rollback",
                "job_id.$": "$.ota_result.Payload.job_id"
            })
        )

        # Define workflow
        definition = create_ota_job.next(
            wait_for_deployment.next(
                check_deployment_status.next(
                    sfn.Choice(self, "DeploymentComplete?")
                    .when(
                        sfn.Condition.string_equals("$.status_result.Payload.status", "SUCCESS"),
                        deployment_success
                    )
                    .when(
                        sfn.Condition.string_equals("$.status_result.Payload.status", "FAILED"),
                        rollback_deployment.next(deployment_failed)
                    )
                    .otherwise(wait_for_deployment)
                )
            )
        )

        # Create state machine
        ota_workflow = sfn.StateMachine(
            self, "OtaWorkflow",
            definition=definition,
            timeout=Duration.minutes(30),
            state_machine_name="iot-ota-workflow"
        )

        # 7️⃣ API Gateway for OTA management
        ota_api = apigateway.RestApi(
            self, "OtaAPI",
            rest_api_name="IoT OTA Management API",
            description="API for managing device firmware updates",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"]
            )
        )

        # Lambda integration
        ota_integration = apigateway.LambdaIntegration(
            ota_manager,
            request_templates={
                "application/json": '{"statusCode": "200"}'
            }
        )

        # API resources
        firmware_resource = ota_api.root.add_resource("firmware")
        versions_resource = firmware_resource.add_resource("versions")
        version_resource = versions_resource.add_resource("{version}")

        ota_resource = ota_api.root.add_resource("ota")
        jobs_resource = ota_resource.add_resource("jobs")
        job_resource = jobs_resource.add_resource("{job_id}")

        devices_resource = ota_resource.add_resource("devices")
        device_resource = devices_resource.add_resource("{device_id}")
        device_jobs_resource = device_resource.add_resource("jobs")

        # Add methods
        # Firmware management
        versions_resource.add_method("GET", ota_integration)  # List versions
        versions_resource.add_method("POST", ota_integration)  # Upload new version
        version_resource.add_method("GET", ota_integration)  # Get version details
        version_resource.add_method("DELETE", ota_integration)  # Delete version

        # OTA job management
        jobs_resource.add_method("GET", ota_integration)  # List jobs
        jobs_resource.add_method("POST", ota_integration)  # Create job
        job_resource.add_method("GET", ota_integration)  # Get job details
        job_resource.add_method("DELETE", ota_integration)  # Cancel job

        # Device-specific operations
        device_jobs_resource.add_method("GET", ota_integration)  # Get device jobs
        device_jobs_resource.add_method("POST", ota_integration)  # Start device update

        # 8️⃣ IoT rules for OTA status updates
        ota_status_rule = iot.CfnTopicRule(
            self, "OtaStatusRule",
            rule_name="ota_status_updates",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql="SELECT *, topic() as source_topic, timestamp() as event_time FROM '$aws/things/+/jobs/+/update'",
                aws_iot_sql_version="2016-03-23",
                rule_disabled=False,
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        lambda_=iot.CfnTopicRule.LambdaActionProperty(
                            function_arn=ota_manager.function_arn
                        )
                    )
                ]
            )
        )

        # Lambda permission for IoT rule
        _lambda.CfnPermission(
            self, "OtaRuleLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=ota_manager.function_name,
            principal="iot.amazonaws.com",
            source_arn=ota_status_rule.attr_arn
        )

        # 📤 Stack Outputs
        CfnOutput(
            self, "FirmwareBucketName",
            value=firmware_bucket.bucket_name,
            description="S3 bucket for firmware storage"
        )

        CfnOutput(
            self, "OtaAPIEndpoint",
            value=ota_api.url,
            description="OTA management API endpoint"
        )

        CfnOutput(
            self, "OtaWorkflowArn",
            value=ota_workflow.state_machine_arn,
            description="Step Functions state machine for OTA workflow"
        )

        CfnOutput(
            self, "OtaJobsTableName",
            value=ota_jobs_table.table_name,
            description="DynamoDB table for OTA job tracking"
        )

        CfnOutput(
            self, "FirmwareVersionsTableName",
            value=firmware_versions_table.table_name,
            description="DynamoDB table for firmware versions"
        )

        CfnOutput(
            self, "OtaRoleArn",
            value=ota_role.role_arn,
            description="IAM role for OTA operations"
        ) 