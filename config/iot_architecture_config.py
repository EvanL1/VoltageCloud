"""
AWS IoT架构配置文件
包含所有服务的配置参数
"""

# AWS基础配置
AWS_CONFIG = {
    "region": "us-east-1",
    "profile": None,  # 可选：指定AWS配置文件
    "resource_prefix": "iot-demo",
    "tags": {
        "Environment": "Production",
        "Project": "IoT-Demo",
        "ManagedBy": "Python-SDK"
    }
}

# S3存储桶配置
S3_CONFIG = {
    "buckets": {
        "data_lake": {
            "versioning": True,
            "lifecycle_rules": [{
                "id": "archive-old-data",
                "transitions": [
                    {"days": 30, "storage_class": "STANDARD_IA"},
                    {"days": 90, "storage_class": "GLACIER"}
                ]
            }]
        },
        "ota_updates": {
            "versioning": True,
            "lifecycle_rules": []
        },
        "airflow_dags": {
            "versioning": True,
            "lifecycle_rules": []
        }
    }
}

# IoT Core配置
IOT_CONFIG = {
    "thing_type": {
        "name": "device-type",
        "properties": {
            "description": "IoT设备类型",
            "searchable_attributes": ["deviceType", "firmware", "location"]
        }
    },
    "policy": {
        "name": "device-policy",
        "statements": [
            {
                "effect": "Allow",
                "actions": ["iot:Connect", "iot:Publish", "iot:Subscribe", "iot:Receive"],
                "resources": ["*"]
            },
            {
                "effect": "Allow",
                "actions": ["iot:GetThingShadow", "iot:UpdateThingShadow", "iot:DeleteThingShadow"],
                "resources": ["arn:aws:iot:*:*:thing/*"]
            }
        ]
    },
    "rules": [
        {
            "name": "process_device_data",
            "sql": "SELECT *, topic(2) as deviceId FROM 'device/+/telemetry'",
            "description": "Process device telemetry data",
            "actions": ["lambda"]
        }
    ]
}

# Lambda配置
LAMBDA_CONFIG = {
    "functions": {
        "data_processor": {
            "name": "iot-data-processor",
            "runtime": "python3.9",
            "handler": "lambda_function.lambda_handler",
            "timeout": 60,
            "memory_size": 256,
            "description": "Process IoT data and store in TimeStream and S3"
        }
    }
}

# TimeStream配置
TIMESTREAM_CONFIG = {
    "database": {
        "name": "iot_db",
        "tables": [{
            "name": "device_metrics",
            "memory_retention_hours": 24,
            "magnetic_retention_days": 365,
            "enable_magnetic_writes": True
        }]
    }
}

# Greengrass配置
GREENGRASS_CONFIG = {
    "components": [{
        "name": "EdgeProcessor",
        "version": "1.0.0",
        "description": "Edge data processor for IoT devices",
        "platform": "linux",
        "lifecycle": {
            "run": "python3 -u {artifacts:path}/edge_processor.py"
        }
    }]
}

# EMR配置
EMR_CONFIG = {
    "cluster": {
        "name": "iot-analytics-cluster",
        "release_label": "emr-6.9.0",
        "applications": ["Spark", "Hadoop", "Hive"],
        "instance_groups": [
            {
                "name": "Master",
                "role": "MASTER",
                "instance_type": "m5.xlarge",
                "instance_count": 1,
                "market": "ON_DEMAND"
            },
            {
                "name": "Worker",
                "role": "CORE",
                "instance_type": "m5.xlarge",
                "instance_count": 2,
                "market": "SPOT"
            }
        ],
        "auto_terminate": True
    }
}

# Airflow (MWAA)配置
AIRFLOW_CONFIG = {
    "environment": {
        "name": "iot-airflow",
        "airflow_version": "2.5.1",
        "environment_class": "mw1.small",
        "max_workers": 10,
        "min_workers": 1,
        "schedulers": 2,
        "webserver_access_mode": "PUBLIC_ONLY"
    },
    "dag_processing": {
        "interval_seconds": 30,
        "max_failures": 3
    }
}

# OTA配置
OTA_CONFIG = {
    "job_template": {
        "name": "ota-template",
        "rollout_config": {
            "maximum_per_minute": 10,
            "exponential_rate": {
                "base_rate": 2,
                "increment_factor": 2.0,
                "rate_increase_criteria": {
                    "notified_things": 10,
                    "succeeded_things": 5
                }
            }
        },
        "abort_config": {
            "failure_threshold_percentage": 10.0,
            "min_executed_things": 10
        },
        "timeout_minutes": 60
    }
}

# 设备影子默认配置
DEVICE_SHADOW_CONFIG = {
    "classic": {
        "desired": {
            "welcome": "aws-iot",
            "color": "green",
            "temperature": 20,
            "firmware_version": "1.0.0"
        }
    },
    "named_shadows": {
        "config": {
            "desired": {
                "sample_rate": 60,
                "reporting_interval": 300,
                "debug_mode": False
            }
        },
        "status": {
            "reported": {
                "online": True,
                "battery_level": 85,
                "signal_strength": -65
            }
        }
    }
}

# IAM角色配置
IAM_CONFIG = {
    "roles": {
        "iot_rule": {
            "name": "iot-rule-role",
            "trust_service": "iot.amazonaws.com",
            "policies": ["arn:aws:iam::aws:policy/service-role/AWSIoTRuleActions"]
        },
        "lambda_execution": {
            "name": "lambda-execution-role",
            "trust_service": "lambda.amazonaws.com",
            "policies": [
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                "arn:aws:iam::aws:policy/AWSIoTFullAccess",
                "arn:aws:iam::aws:policy/AmazonS3FullAccess",
                "arn:aws:iam::aws:policy/AmazonTimestreamFullAccess"
            ]
        },
        "greengrass": {
            "name": "greengrass-role",
            "trust_service": "greengrass.amazonaws.com",
            "policies": ["arn:aws:iam::aws:policy/service-role/AWSGreengrassResourceAccessRolePolicy"]
        }
    }
}

# 监控和告警配置
MONITORING_CONFIG = {
    "cloudwatch": {
        "log_retention_days": 30,
        "metrics_namespace": "IoT/Production",
        "alarms": [
            {
                "name": "high-error-rate",
                "metric": "Errors",
                "threshold": 10,
                "evaluation_periods": 2,
                "datapoints_to_alarm": 2
            },
            {
                "name": "low-message-rate",
                "metric": "MessageCount",
                "threshold": 100,
                "comparison": "LessThanThreshold",
                "evaluation_periods": 5,
                "datapoints_to_alarm": 3
            }
        ]
    }
}

# 安全配置
SECURITY_CONFIG = {
    "encryption": {
        "s3": {
            "enabled": True,
            "algorithm": "AES256"
        },
        "timestream": {
            "enabled": True,
            "kms_key_id": None  # 使用默认AWS管理的密钥
        }
    },
    "network": {
        "vpc_endpoints": {
            "s3": True,
            "iot": True,
            "lambda": True
        }
    },
    "shield": {
        "standard": True,  # 自动启用
        "advanced": False  # 需要手动订阅
    }
}

# 成本优化配置
COST_OPTIMIZATION = {
    "spot_instances": {
        "enabled": True,
        "max_price_percentage": 80  # 最高出价为按需价格的80%
    },
    "auto_scaling": {
        "enabled": True,
        "min_capacity": 1,
        "max_capacity": 10,
        "target_utilization": 70
    },
    "data_lifecycle": {
        "retention_policies": {
            "hot_data_days": 7,
            "warm_data_days": 30,
            "cold_data_days": 90,
            "archive_after_days": 365
        }
    }
}

# 示例设备配置模板
DEVICE_TEMPLATE = {
    "thing_name": "device-{id}",
    "attributes": {
        "deviceType": "sensor",
        "location": "unknown",
        "firmware": "1.0.0",
        "serialNumber": "SN-{id}"
    },
    "certificate": {
        "auto_generate": True,
        "activate": True
    },
    "policy": {
        "attach": True,
        "name": "device-policy"
    }
}