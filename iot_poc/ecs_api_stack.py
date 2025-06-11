"""
ECS API Service Stack
Implements containerized API services using AWS ECS Fargate
"""

from aws_cdk import (
    Stack, Duration, CfnOutput,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    aws_iam as iam,
    aws_route53 as route53,
    aws_certificatemanager as acm,
    aws_servicediscovery as servicediscovery,
    aws_apigateway as apigateway,
    aws_lambda as _lambda,
)
from constructs import Construct


class EcsApiStack(Stack):
    """
    ECS API Service Infrastructure Stack
    Deploys containerized API services with load balancing and service discovery
    """

    def __init__(self, scope: Construct, construct_id: str, domain_name: str = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1️⃣ VPC for ECS services
        vpc = ec2.Vpc(
            self, "IoTVPC",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PublicSubnet",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="PrivateSubnet",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ]
        )

        # 2️⃣ ECS Cluster
        cluster = ecs.Cluster(
            self, "IoTCluster",
            vpc=vpc,
            container_insights=True,
            cluster_name="iot-api-cluster"
        )

        # 3️⃣ Service Discovery Namespace
        namespace = servicediscovery.PrivateDnsNamespace(
            self, "IoTNamespace",
            name="iot.local",
            vpc=vpc,
            description="Service discovery namespace for IoT services"
        )

        # 4️⃣ Application Load Balancer
        alb = elbv2.ApplicationLoadBalancer(
            self, "IoTALB",
            vpc=vpc,
            internet_facing=True,
            load_balancer_name="iot-api-alb"
        )

        # 5️⃣ SSL Certificate (if domain provided)
        certificate = None
        if domain_name:
            certificate = acm.Certificate(
                self, "IoTCertificate",
                domain_name=domain_name,
                validation=acm.CertificateValidation.from_dns()
            )

        # 6️⃣ Task Execution Role
        execution_role = iam.Role(
            self, "EcsExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )

        # 7️⃣ Task Role with IoT permissions
        task_role = iam.Role(
            self, "EcsTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            inline_policies={
                "IoTApiPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "iot:*",
                                "timestream:*",
                                "s3:GetObject",
                                "s3:PutObject",
                                "dynamodb:GetItem",
                                "dynamodb:PutItem",
                                "dynamodb:UpdateItem",
                                "dynamodb:DeleteItem",
                                "dynamodb:Query",
                                "dynamodb:Scan",
                                "sqs:ReceiveMessage",
                                "sqs:SendMessage",
                                "cognito-idp:*"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        # 8️⃣ Task Definition for API Service
        api_task_definition = ecs.FargateTaskDefinition(
            self, "ApiTaskDefinition",
            memory_limit_mib=1024,
            cpu=512,
            execution_role=execution_role,
            task_role=task_role
        )

        # 9️⃣ Container Definition
        api_container = api_task_definition.add_container(
            "ApiContainer",
            image=ecs.ContainerImage.from_registry("python:3.12-slim"),
            memory_limit_mib=1024,
            environment={
                "REGION": self.region,
                "CLUSTER_NAME": cluster.cluster_name
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="iot-api",
                log_retention=logs.RetentionDays.ONE_WEEK
            ),
            # Override to run a simple API server
            command=[
                "sh", "-c",
                """
                pip install fastapi uvicorn boto3 &&
                python -c "
                from fastapi import FastAPI
                import uvicorn
                
                app = FastAPI(title='IoT API Service')
                
                @app.get('/health')
                def health_check():
                    return {'status': 'healthy', 'service': 'iot-api'}
                
                @app.get('/api/v1/devices')
                def list_devices():
                    return {'devices': [], 'message': 'Device list endpoint'}
                
                @app.get('/api/v1/devices/{device_id}')
                def get_device(device_id: str):
                    return {'device_id': device_id, 'status': 'online'}
                
                uvicorn.run(app, host='0.0.0.0', port=8080)
                "
                """
            ]
        )

        api_container.add_port_mappings(
            ecs.PortMapping(
                container_port=8080,
                protocol=ecs.Protocol.TCP
            )
        )

        # 🔟 ECS Service
        api_service = ecs.FargateService(
            self, "ApiService",
            cluster=cluster,
            task_definition=api_task_definition,
            desired_count=2,
            assign_public_ip=False,
            service_name="iot-api-service",
            cloud_map_options=ecs.CloudMapOptions(
                cloud_map_namespace=namespace,
                name="api"
            )
        )

        # 1️⃣1️⃣ Target Group
        target_group = elbv2.ApplicationTargetGroup(
            self, "ApiTargetGroup",
            vpc=vpc,
            port=8080,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/health",
                healthy_http_codes="200",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3
            )
        )

        # Attach service to target group
        api_service.attach_to_application_target_group(target_group)

        # 1️⃣2️⃣ ALB Listener
        if certificate:
            listener = alb.add_listener(
                "HttpsListener",
                port=443,
                protocol=elbv2.ApplicationProtocol.HTTPS,
                certificates=[certificate],
                default_target_groups=[target_group]
            )
            
            # Redirect HTTP to HTTPS
            alb.add_listener(
                "HttpListener",
                port=80,
                protocol=elbv2.ApplicationProtocol.HTTP,
                default_action=elbv2.ListenerAction.redirect(
                    protocol="HTTPS",
                    port="443",
                    permanent=True
                )
            )
        else:
            listener = alb.add_listener(
                "HttpListener",
                port=80,
                protocol=elbv2.ApplicationProtocol.HTTP,
                default_target_groups=[target_group]
            )

        # 1️⃣3️⃣ Auto Scaling
        scaling = api_service.auto_scale_task_count(
            max_capacity=10,
            min_capacity=2
        )

        # CPU-based scaling
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.minutes(2)
        )

        # Memory-based scaling
        scaling.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.minutes(2)
        )

        # 1️⃣4️⃣ API Gateway Integration Lambda
        api_integration_lambda = _lambda.Function(
            self, "ApiIntegrationLambda",
            function_name="iot-api-integration",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="api_integration.handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "ALB_DNS_NAME": alb.load_balancer_dns_name,
                "SERVICE_ENDPOINT": f"http://{alb.load_balancer_dns_name}",
                "REGION": self.region
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )

        # 1️⃣5️⃣ API Gateway for external access
        api_gateway = apigateway.RestApi(
            self, "IoTGateway",
            rest_api_name="IoT Platform Gateway",
            description="Unified API Gateway for IoT platform services",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"]
            )
        )

        # Lambda integration
        integration = apigateway.LambdaIntegration(
            api_integration_lambda,
            request_templates={
                "application/json": '{"statusCode": "200"}'
            }
        )

        # API resources
        api_resource = api_gateway.root.add_resource("api")
        v1_resource = api_resource.add_resource("v1")
        
        # Device management endpoints
        devices_resource = v1_resource.add_resource("devices")
        device_resource = devices_resource.add_resource("{device_id}")
        
        # Add methods
        devices_resource.add_method("GET", integration)
        devices_resource.add_method("POST", integration)
        device_resource.add_method("GET", integration)
        device_resource.add_method("PUT", integration)
        device_resource.add_method("DELETE", integration)

        # Health check endpoint
        health_resource = api_gateway.root.add_resource("health")
        health_resource.add_method("GET", integration)

        # 1️⃣6️⃣ Route53 Record (if domain provided)
        if domain_name and certificate:
            hosted_zone = route53.HostedZone.from_lookup(
                self, "HostedZone",
                domain_name=domain_name
            )
            
            route53.ARecord(
                self, "AliasRecord",
                zone=hosted_zone,
                record_name="api",
                target=route53.RecordTarget.from_alias(
                    route53_targets.LoadBalancerTarget(alb)
                )
            )

        # 📤 Stack Outputs
        CfnOutput(
            self, "VpcId",
            value=vpc.vpc_id,
            description="VPC ID for ECS services"
        )

        CfnOutput(
            self, "ClusterArn",
            value=cluster.cluster_arn,
            description="ECS Cluster ARN"
        )

        CfnOutput(
            self, "LoadBalancerDNS",
            value=alb.load_balancer_dns_name,
            description="Application Load Balancer DNS name"
        )

        CfnOutput(
            self, "ApiGatewayUrl",
            value=api_gateway.url,
            description="API Gateway URL"
        )

        CfnOutput(
            self, "ServiceDiscoveryNamespace",
            value=namespace.namespace_name,
            description="Service discovery namespace"
        )

        # Export key resources for other stacks
        self.vpc = vpc
        self.cluster = cluster
        self.alb = alb
        self.api_gateway = api_gateway 