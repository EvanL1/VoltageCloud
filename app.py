#!/usr/bin/env python3
"""
IoT Platform CDK App
Deploys complete IoT solution with authentication, device management, and edge computing
"""

import aws_cdk as cdk
from iot_poc.iot_poc_stack import IotPocStack
from iot_poc.device_shadow_stack import DeviceShadowStack
from iot_poc.auth_stack import AuthStack
from iot_poc.ecs_api_stack import EcsApiStack
from iot_poc.ota_stack import OtaStack
from iot_poc.data_lake_stack import DataLakeStack


app = cdk.App()

# Environment configuration
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1"
)

# 1️⃣ Core IoT data processing stack
iot_poc_stack = IotPocStack(
    app, "IotPocStack",
    env=env,
    description="Core IoT data processing pipeline with SQS, Lambda, TimeStream and S3"
)

# 2️⃣ Device Shadow management stack
shadow_stack = DeviceShadowStack(
    app, "DeviceShadowStack",
    env=env,
    description="IoT Device Shadow management with DynamoDB caching and API Gateway"
)

# 3️⃣ Authentication and authorization stack
auth_stack = AuthStack(
    app, "AuthStack",
    env=env,
    description="User authentication and authorization with Cognito and device permissions"
)

# 4️⃣ ECS API services stack
ecs_api_stack = EcsApiStack(
    app, "EcsApiStack",
    # domain_name="your-domain.com",  # Uncomment and set your domain
    env=env,
    description="Containerized API services with ECS Fargate, ALB, and API Gateway"
)

# 5️⃣ OTA update management stack
ota_stack = OtaStack(
    app, "OtaStack",
    env=env,
    description="Over-the-Air device firmware update management with job tracking and rollback"
)

# 6️⃣ Data Lake and Analytics stack
data_lake_stack = DataLakeStack(
    app, "DataLakeStack",
    env=env,
    description="Comprehensive data lake with multi-layer storage, Glue ETL, Athena queries, and analytics APIs"
)

# Add dependencies
shadow_stack.add_dependency(iot_poc_stack)
ecs_api_stack.add_dependency(auth_stack)
ota_stack.add_dependency(shadow_stack)
data_lake_stack.add_dependency(iot_poc_stack)

# Tags for all resources
cdk.Tags.of(app).add("Project", "IoT-Platform")
cdk.Tags.of(app).add("Environment", "development")
cdk.Tags.of(app).add("Owner", "IoT-Team")

app.synth()
