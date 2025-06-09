#!/usr/bin/env python3
"""
IoT PoC CDK Application Entry Point
MQTT → IoT Core → Kinesis → Lambda (Python/Rust) → TimeStream & S3
"""

import aws_cdk as cdk
from iot_poc.iot_poc_stack import IotPocStack

app = cdk.App()

# 从环境变量或上下文获取AWS账户信息
account = app.node.try_get_context("account") or None
region = app.node.try_get_context("region") or "us-west-2"

IotPocStack(
    app, 
    "IotPocStack",
    env=cdk.Environment(account=account, region=region),
    description="IoT PoC: MQTT → IoT Core → Kinesis → Lambda → TimeStream & S3"
)

app.synth() 