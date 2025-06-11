"""
Data Lake Stack
Implements a comprehensive data lake architecture for IoT data analytics
"""

from aws_cdk import (
    Stack, Duration, CfnOutput,
    aws_s3 as s3,
    aws_glue as glue,
    aws_athena as athena,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_logs as logs,
    aws_apigateway as apigateway,
    aws_quicksight as quicksight,
    aws_lakeformation as lakeformation,
    aws_events as events,
    aws_events_targets as targets,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
)
from constructs import Construct


class DataLakeStack(Stack):
    """
    Data Lake Infrastructure Stack
    Implements a complete data lake with multiple layers and analytics capabilities
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1️⃣ Data Lake S3 Buckets (Multi-layer architecture)
        
        # Raw Data Layer
        raw_data_bucket = s3.Bucket(
            self, "RawDataBucket",
            bucket_name=f"iot-datalake-raw-{self.account}-{self.region}",
            versioned=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90)
                        )
                    ]
                )
            ]
        )

        # Processed Data Layer
        processed_data_bucket = s3.Bucket(
            self, "ProcessedDataBucket",
            bucket_name=f"iot-datalake-processed-{self.account}-{self.region}",
            versioned=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(60)
                        )
                    ]
                )
            ]
        )

        # Curated Data Layer
        curated_data_bucket = s3.Bucket(
            self, "CuratedDataBucket",
            bucket_name=f"iot-datalake-curated-{self.account}-{self.region}",
            versioned=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL
        )

        # Analytics Results Bucket
        analytics_bucket = s3.Bucket(
            self, "AnalyticsBucket",
            bucket_name=f"iot-datalake-analytics-{self.account}-{self.region}",
            versioned=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL
        )

        # 2️⃣ AWS Glue Data Catalog
        
        # Glue Database
        glue_database = glue.CfnDatabase(
            self, "IoTDataLakeDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="iot_data_lake",
                description="IoT Data Lake Database for storing device and sensor data"
            )
        )

        # Raw Data Table
        raw_data_table = glue.CfnTable(
            self, "RawDataTable",
            catalog_id=self.account,
            database_name=glue_database.database_input.name,
            table_input=glue.CfnTable.TableInputProperty(
                name="raw_iot_data",
                description="Raw IoT sensor data",
                table_type="EXTERNAL_TABLE",
                storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                    columns=[
                        glue.CfnTable.ColumnProperty(name="device_id", type="string"),
                        glue.CfnTable.ColumnProperty(name="timestamp", type="bigint"),
                        glue.CfnTable.ColumnProperty(name="temperature", type="double"),
                        glue.CfnTable.ColumnProperty(name="humidity", type="double"),
                        glue.CfnTable.ColumnProperty(name="source_topic", type="string"),
                        glue.CfnTable.ColumnProperty(name="event_time", type="bigint")
                    ],
                    location=f"s3://{raw_data_bucket.bucket_name}/raw/",
                    input_format="org.apache.hadoop.mapred.TextInputFormat",
                    output_format="org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                    serde_info=glue.CfnTable.SerdeInfoProperty(
                        serialization_library="org.openx.data.jsonserde.JsonSerDe"
                    )
                ),
                partition_keys=[
                    glue.CfnTable.ColumnProperty(name="year", type="string"),
                    glue.CfnTable.ColumnProperty(name="month", type="string"),
                    glue.CfnTable.ColumnProperty(name="day", type="string")
                ]
            )
        )
        raw_data_table.add_dependency(glue_database)

        # 3️⃣ Glue ETL Jobs
        
        # ETL Job Role
        glue_role = iam.Role(
            self, "GlueETLRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")
            ],
            inline_policies={
                "DataLakeAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                                "s3:ListBucket"
                            ],
                            resources=[
                                raw_data_bucket.bucket_arn,
                                f"{raw_data_bucket.bucket_arn}/*",
                                processed_data_bucket.bucket_arn,
                                f"{processed_data_bucket.bucket_arn}/*",
                                curated_data_bucket.bucket_arn,
                                f"{curated_data_bucket.bucket_arn}/*"
                            ]
                        )
                    ]
                )
            }
        )

        # ETL Job: Raw to Processed
        raw_to_processed_job = glue.CfnJob(
            self, "RawToProcessedJob",
            name="iot-raw-to-processed",
            role=glue_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                python_version="3",
                script_location=f"s3://{analytics_bucket.bucket_name}/scripts/raw_to_processed.py"
            ),
            default_arguments={
                "--job-language": "python",
                "--job-bookmark-option": "job-bookmark-enable",
                "--enable-metrics": "true",
                "--enable-continuous-cloudwatch-log": "true",
                "--SOURCE_DATABASE": glue_database.database_input.name,
                "--SOURCE_TABLE": raw_data_table.table_input.name,
                "--TARGET_BUCKET": processed_data_bucket.bucket_name
            },
            max_retries=1,
            timeout=60,
            glue_version="4.0"
        )

        # 4️⃣ Amazon Athena Setup
        
        # Athena Workgroup
        athena_workgroup = athena.CfnWorkGroup(
            self, "IoTAnalyticsWorkGroup",
            name="iot-analytics",
            description="Workgroup for IoT data analytics",
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{analytics_bucket.bucket_name}/athena-results/"
                ),
                enforce_work_group_configuration=True,
                publish_cloud_watch_metrics=True
            )
        )

        # 5️⃣ Data Lake API Lambda Function
        data_lake_api = _lambda.Function(
            self, "DataLakeAPI",
            function_name="iot-data-lake-api",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="data_lake_api.handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.minutes(5),
            memory_size=1024,
            environment={
                "RAW_BUCKET": raw_data_bucket.bucket_name,
                "PROCESSED_BUCKET": processed_data_bucket.bucket_name,
                "CURATED_BUCKET": curated_data_bucket.bucket_name,
                "ANALYTICS_BUCKET": analytics_bucket.bucket_name,
                "GLUE_DATABASE": glue_database.database_input.name,
                "ATHENA_WORKGROUP": athena_workgroup.name,
                "REGION": self.region
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )

        # Grant permissions to Data Lake API
        raw_data_bucket.grant_read_write(data_lake_api)
        processed_data_bucket.grant_read_write(data_lake_api)
        curated_data_bucket.grant_read_write(data_lake_api)
        analytics_bucket.grant_read_write(data_lake_api)

        # Athena and Glue permissions
        data_lake_api.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "athena:StartQueryExecution",
                    "athena:GetQueryExecution",
                    "athena:GetQueryResults",
                    "athena:StopQueryExecution",
                    "athena:ListQueryExecutions",
                    "glue:GetTable",
                    "glue:GetTables",
                    "glue:GetDatabase",
                    "glue:GetDatabases",
                    "glue:GetPartitions",
                    "glue:BatchCreatePartition",
                    "glue:BatchGetPartition"
                ],
                resources=["*"]
            )
        )

        # 6️⃣ Data Processing Workflow (Step Functions)
        
        # Trigger Glue Job
        trigger_etl_job = sfn_tasks.GlueStartJobRun(
            self, "TriggerETLJob",
            glue_job_name=raw_to_processed_job.name,
            integration_pattern=sfn.IntegrationPattern.RUN_JOB
        )

        # Update Glue Catalog
        update_catalog = sfn_tasks.LambdaInvoke(
            self, "UpdateGlueCatalog",
            lambda_function=data_lake_api,
            payload=sfn.TaskInput.from_object({
                "action": "update_partitions",
                "database": glue_database.database_input.name,
                "table": raw_data_table.table_input.name
            })
        )

        # Data Processing Workflow
        data_processing_workflow = sfn.StateMachine(
            self, "DataProcessingWorkflow",
            definition=update_catalog.next(trigger_etl_job),
            timeout=Duration.hours(2),
            state_machine_name="iot-data-processing"
        )

        # 7️⃣ EventBridge Rule for automated processing
        data_processing_rule = events.Rule(
            self, "DataProcessingRule",
            schedule=events.Schedule.rate(Duration.hours(6)),  # Run every 6 hours
            description="Trigger data processing workflow"
        )

        data_processing_rule.add_target(
            targets.SfnStateMachine(data_processing_workflow)
        )

        # 8️⃣ API Gateway for Data Lake Access
        data_lake_api_gateway = apigateway.RestApi(
            self, "DataLakeAPI",
            rest_api_name="IoT Data Lake API",
            description="API for accessing IoT data lake",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"]
            )
        )

        # Lambda integration
        data_lake_integration = apigateway.LambdaIntegration(
            data_lake_api,
            request_templates={
                "application/json": '{"statusCode": "200"}'
            }
        )

        # API Resources
        # Query endpoints
        query_resource = data_lake_api_gateway.root.add_resource("query")
        sql_resource = query_resource.add_resource("sql")
        tables_resource = query_resource.add_resource("tables")
        
        # Data access endpoints
        data_resource = data_lake_api_gateway.root.add_resource("data")
        raw_resource = data_resource.add_resource("raw")
        processed_resource = data_resource.add_resource("processed")
        curated_resource = data_resource.add_resource("curated")
        
        # Analytics endpoints
        analytics_resource = data_lake_api_gateway.root.add_resource("analytics")
        dashboards_resource = analytics_resource.add_resource("dashboards")
        reports_resource = analytics_resource.add_resource("reports")

        # Add methods
        sql_resource.add_method("POST", data_lake_integration)  # Execute SQL
        tables_resource.add_method("GET", data_lake_integration)  # List tables
        
        raw_resource.add_method("GET", data_lake_integration)  # Query raw data
        processed_resource.add_method("GET", data_lake_integration)  # Query processed data
        curated_resource.add_method("GET", data_lake_integration)  # Query curated data
        
        dashboards_resource.add_method("GET", data_lake_integration)  # List dashboards
        reports_resource.add_method("GET", data_lake_integration)  # Generate reports

        # 9️⃣ Lake Formation Setup (Optional - for advanced permissions)
        data_lake_settings = lakeformation.CfnDataLakeSettings(
            self, "DataLakeSettings",
            admins=[
                lakeformation.CfnDataLakeSettings.DataLakePrincipalProperty(
                    data_lake_principal_identifier=data_lake_api.role.role_arn
                )
            ]
        )

        # 📤 Stack Outputs
        CfnOutput(
            self, "RawDataBucketName",
            value=raw_data_bucket.bucket_name,
            description="S3 bucket for raw IoT data"
        )

        CfnOutput(
            self, "ProcessedDataBucketName",
            value=processed_data_bucket.bucket_name,
            description="S3 bucket for processed IoT data"
        )

        CfnOutput(
            self, "CuratedDataBucketName",
            value=curated_data_bucket.bucket_name,
            description="S3 bucket for curated IoT data"
        )

        CfnOutput(
            self, "AnalyticsBucketName",
            value=analytics_bucket.bucket_name,
            description="S3 bucket for analytics results"
        )

        CfnOutput(
            self, "GlueDatabaseName",
            value=glue_database.database_input.name,
            description="Glue database for IoT data catalog"
        )

        CfnOutput(
            self, "AthenaWorkGroupName",
            value=athena_workgroup.name,
            description="Athena workgroup for analytics"
        )

        CfnOutput(
            self, "DataLakeAPIEndpoint",
            value=data_lake_api_gateway.url,
            description="Data Lake API Gateway endpoint"
        )

        CfnOutput(
            self, "DataProcessingWorkflowArn",
            value=data_processing_workflow.state_machine_arn,
            description="Step Functions workflow for data processing"
        )

        # Export resources for other stacks
        self.raw_data_bucket = raw_data_bucket
        self.processed_data_bucket = processed_data_bucket
        self.curated_data_bucket = curated_data_bucket
        self.glue_database = glue_database
        self.data_lake_api = data_lake_api 