"""
Device Shadow Management Stack
Implements AWS IoT Device Shadow service for device state management
"""

from aws_cdk import (
    Stack, Duration, CfnOutput,
    aws_iot as iot,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_logs as logs,
    aws_dynamodb as dynamodb,
    aws_apigateway as apigateway,
)
from constructs import Construct


class DeviceShadowStack(Stack):
    """
    Device Shadow Management Infrastructure Stack
    Manages device state, desired configuration, and reported status
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1️⃣ DynamoDB table for device shadow cache
        shadow_cache_table = dynamodb.Table(
            self, "ShadowCacheTable",
            table_name="device-shadow-cache",
            partition_key=dynamodb.Attribute(
                name="device_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="shadow_type",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            point_in_time_recovery=True,
            removal_policy=Stack.of(self).removal_policy
        )

        # Add GSI for querying by status
        shadow_cache_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="last_updated",
                type=dynamodb.AttributeType.STRING
            )
        )

        # 2️⃣ Lambda function for device shadow operations
        shadow_manager = _lambda.Function(
            self, "ShadowManager",
            function_name="iot-device-shadow-manager",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="shadow_manager.handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "SHADOW_CACHE_TABLE": shadow_cache_table.table_name,
                "REGION": self.region
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )

        # Grant permissions to Lambda
        shadow_cache_table.grant_read_write_data(shadow_manager)
        
        # IoT Device Shadow permissions
        shadow_manager.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iot:GetThingShadow",
                    "iot:UpdateThingShadow",
                    "iot:DeleteThingShadow",
                    "iot:ListNamedShadowsForThing"
                ],
                resources=[f"arn:aws:iot:{self.region}:{self.account}:thing/*"]
            )
        )

        # 3️⃣ API Gateway for shadow management
        shadow_api = apigateway.RestApi(
            self, "ShadowAPI",
            rest_api_name="IoT Device Shadow API",
            description="API for managing IoT device shadows",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"]
            )
        )

        # Lambda integration
        shadow_integration = apigateway.LambdaIntegration(
            shadow_manager,
            request_templates={
                "application/json": '{"statusCode": "200"}'
            }
        )

        # API resources
        devices_resource = shadow_api.root.add_resource("devices")
        device_resource = devices_resource.add_resource("{device_id}")
        shadow_resource = device_resource.add_resource("shadow")
        named_shadow_resource = shadow_resource.add_resource("{shadow_name}")

        # Add methods
        shadow_resource.add_method("GET", shadow_integration)  # Get default shadow
        shadow_resource.add_method("PUT", shadow_integration)  # Update default shadow
        shadow_resource.add_method("DELETE", shadow_integration)  # Delete default shadow
        
        named_shadow_resource.add_method("GET", shadow_integration)  # Get named shadow
        named_shadow_resource.add_method("PUT", shadow_integration)  # Update named shadow
        named_shadow_resource.add_method("DELETE", shadow_integration)  # Delete named shadow

        # Batch operations
        batch_resource = shadow_api.root.add_resource("batch")
        batch_resource.add_method("POST", shadow_integration)  # Batch shadow operations

        # 4️⃣ IoT rules for shadow updates
        shadow_update_rule = iot.CfnTopicRule(
            self, "ShadowUpdateRule",
            rule_name="shadow_update_cache",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql="SELECT *, topic() as source_topic, timestamp() as event_time FROM '$aws/things/+/shadow/update/accepted'",
                aws_iot_sql_version="2016-03-23",
                rule_disabled=False,
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        lambda_=iot.CfnTopicRule.LambdaActionProperty(
                            function_arn=shadow_manager.function_arn
                        )
                    )
                ]
            )
        )

        # Lambda permission for IoT rule
        _lambda.CfnPermission(
            self, "ShadowRuleLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=shadow_manager.function_name,
            principal="iot.amazonaws.com",
            source_arn=shadow_update_rule.attr_arn
        )

        # 📤 Stack Outputs
        CfnOutput(
            self, "ShadowCacheTableName",
            value=shadow_cache_table.table_name,
            description="DynamoDB table for device shadow cache"
        )

        CfnOutput(
            self, "ShadowAPIEndpoint",
            value=shadow_api.url,
            description="API Gateway endpoint for device shadow management"
        )

        CfnOutput(
            self, "ShadowManagerFunctionName",
            value=shadow_manager.function_name,
            description="Lambda function for shadow management"
        )

        CfnOutput(
            self, "ShadowUpdateRuleName",
            value=shadow_update_rule.rule_name,
            description="IoT rule for shadow update notifications"
        ) 