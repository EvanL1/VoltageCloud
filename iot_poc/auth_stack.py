"""
Authentication and Authorization Stack
Implements user authentication, authorization, and management for IoT platform
"""

from aws_cdk import (
    Stack, Duration, CfnOutput,
    aws_cognito as cognito,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_logs as logs,
    aws_dynamodb as dynamodb,
    aws_apigateway as apigateway,
)
from constructs import Construct


class AuthStack(Stack):
    """
    Authentication and Authorization Infrastructure Stack
    Manages user authentication, permissions, and access control
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1️⃣ Cognito User Pool for authentication
        user_pool = cognito.UserPool(
            self, "IoTUserPool",
            user_pool_name="iot-platform-users",
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=True
            ),
            self_sign_up_enabled=True,
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True
            ),
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(
                sms=True,
                otp=True
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=Stack.of(self).removal_policy
        )

        # User Pool Client for web/mobile apps
        user_pool_client = cognito.UserPoolClient(
            self, "IoTUserPoolClient",
            user_pool=user_pool,
            user_pool_client_name="iot-platform-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                admin_user_password=True
            ),
            generate_secret=False,  # For web apps, set to True for server-side apps
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30)
        )

        # 2️⃣ Identity Pool for AWS resource access
        identity_pool = cognito.CfnIdentityPool(
            self, "IoTIdentityPool",
            identity_pool_name="iot-platform-identity-pool",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=user_pool_client.user_pool_client_id,
                    provider_name=user_pool.user_pool_provider_name,
                    server_side_token_check=False
                )
            ]
        )

        # 3️⃣ DynamoDB table for user profiles and permissions
        user_profile_table = dynamodb.Table(
            self, "UserProfileTable",
            table_name="user-profiles",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=Stack.of(self).removal_policy
        )

        # Add GSI for role-based queries
        user_profile_table.add_global_secondary_index(
            index_name="role-index",
            partition_key=dynamodb.Attribute(
                name="role",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            )
        )

        # 4️⃣ Device permissions table
        device_permissions_table = dynamodb.Table(
            self, "DevicePermissionsTable",
            table_name="device-permissions",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="device_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=Stack.of(self).removal_policy
        )

        # 5️⃣ Lambda authorizer function
        auth_lambda = _lambda.Function(
            self, "AuthLambda",
            function_name="iot-auth-manager",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="auth_manager.handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "USER_PROFILE_TABLE": user_profile_table.table_name,
                "DEVICE_PERMISSIONS_TABLE": device_permissions_table.table_name,
                "USER_POOL_ID": user_pool.user_pool_id,
                "REGION": self.region
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )

        # Grant permissions to Lambda
        user_profile_table.grant_read_write_data(auth_lambda)
        device_permissions_table.grant_read_write_data(auth_lambda)
        
        # Cognito permissions
        auth_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminListGroupsForUser",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminRemoveUserFromGroup"
                ],
                resources=[user_pool.user_pool_arn]
            )
        )

        # 6️⃣ IAM roles for different user types
        # Admin role
        admin_role = iam.Role(
            self, "AdminRole",
            assumed_by=iam.FederatedPrincipal(
                federated="cognito-identity.amazonaws.com",
                conditions={
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    }
                }
            ),
            inline_policies={
                "AdminPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "iot:*",
                                "timestream:*",
                                "s3:*",
                                "sqs:*"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        # Regular user role
        user_role = iam.Role(
            self, "UserRole",
            assumed_by=iam.FederatedPrincipal(
                federated="cognito-identity.amazonaws.com",
                conditions={
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    }
                }
            ),
            inline_policies={
                "UserPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "iot:GetThingShadow",
                                "iot:UpdateThingShadow",
                                "iot:Publish"
                            ],
                            resources=[
                                f"arn:aws:iot:{self.region}:{self.account}:thing/${{cognito-identity.amazonaws.com:sub}}*",
                                f"arn:aws:iot:{self.region}:{self.account}:topic/devices/${{cognito-identity.amazonaws.com:sub}}/*"
                            ]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "timestream:Select",
                                "timestream:DescribeTable",
                                "timestream:DescribeDatabase"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        # 7️⃣ Identity Pool Role Mapping
        cognito.CfnIdentityPoolRoleAttachment(
            self, "IdentityPoolRoleAttachment",
            identity_pool_id=identity_pool.ref,
            roles={
                "authenticated": user_role.role_arn
            },
            role_mappings={
                "cognito-identity-provider": cognito.CfnIdentityPoolRoleAttachment.RoleMappingProperty(
                    type="Rules",
                    ambiguous_role_resolution="AuthenticatedRole",
                    rules_configuration=cognito.CfnIdentityPoolRoleAttachment.RulesConfigurationProperty(
                        rules=[
                            cognito.CfnIdentityPoolRoleAttachment.MappingRuleProperty(
                                claim="custom:role",
                                match_type="Equals",
                                value="admin",
                                role_arn=admin_role.role_arn
                            ),
                            cognito.CfnIdentityPoolRoleAttachment.MappingRuleProperty(
                                claim="custom:role",
                                match_type="Equals",
                                value="user",
                                role_arn=user_role.role_arn
                            )
                        ]
                    )
                )
            }
        )

        # 8️⃣ API Gateway with Cognito authorizer
        auth_api = apigateway.RestApi(
            self, "AuthAPI",
            rest_api_name="IoT Authentication API",
            description="API for user authentication and authorization",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"]
            )
        )

        # Cognito authorizer
        cognito_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self, "CognitoAuthorizer",
            cognito_user_pools=[user_pool],
            authorizer_name="IoTCognitoAuthorizer"
        )

        # Lambda integration
        auth_integration = apigateway.LambdaIntegration(
            auth_lambda,
            request_templates={
                "application/json": '{"statusCode": "200"}'
            }
        )

        # API resources
        users_resource = auth_api.root.add_resource("users")
        user_resource = users_resource.add_resource("{user_id}")
        permissions_resource = user_resource.add_resource("permissions")
        devices_resource = permissions_resource.add_resource("devices")

        # Add methods with Cognito authorization
        users_resource.add_method(
            "GET", 
            auth_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        user_resource.add_method(
            "GET", 
            auth_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        permissions_resource.add_method(
            "GET", 
            auth_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        devices_resource.add_method(
            "POST", 
            auth_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )

        # 📤 Stack Outputs
        CfnOutput(
            self, "UserPoolId",
            value=user_pool.user_pool_id,
            description="Cognito User Pool ID"
        )

        CfnOutput(
            self, "UserPoolClientId",
            value=user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID"
        )

        CfnOutput(
            self, "IdentityPoolId",
            value=identity_pool.ref,
            description="Cognito Identity Pool ID"
        )

        CfnOutput(
            self, "AuthAPIEndpoint",
            value=auth_api.url,
            description="Authentication API endpoint"
        )

        CfnOutput(
            self, "UserProfileTableName",
            value=user_profile_table.table_name,
            description="User profiles DynamoDB table"
        )

        CfnOutput(
            self, "DevicePermissionsTableName",
            value=device_permissions_table.table_name,
            description="Device permissions DynamoDB table"
        ) 