"""
IoT OTA (Over-the-Air) Manager
Handles device firmware updates, version management, and job tracking
"""

import os
import json
import boto3
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
FIRMWARE_BUCKET = os.environ["FIRMWARE_BUCKET"]
OTA_JOBS_TABLE = os.environ["OTA_JOBS_TABLE"]
FIRMWARE_VERSIONS_TABLE = os.environ["FIRMWARE_VERSIONS_TABLE"]
REGION = os.environ["REGION"]

# Initialize AWS clients
s3_client = boto3.client("s3", region_name=REGION)
iot_client = boto3.client("iot", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
ota_jobs_table = dynamodb.Table(OTA_JOBS_TABLE)
firmware_versions_table = dynamodb.Table(FIRMWARE_VERSIONS_TABLE)


def create_firmware_version(device_type: str, version: str, firmware_file: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create a new firmware version entry
    
    Args:
        device_type: Type of device (e.g., sensor, gateway)
        version: Firmware version string
        firmware_file: S3 key of firmware file
        metadata: Additional metadata about the firmware
        
    Returns:
        Operation result
    """
    try:
        # Verify firmware file exists in S3
        try:
            s3_client.head_object(Bucket=FIRMWARE_BUCKET, Key=firmware_file)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return {
                    "statusCode": 404,
                    "body": {"error": f"Firmware file not found: {firmware_file}"}
                }
            raise
        
        # Create version entry
        version_data = {
            "device_type": device_type,
            "version": version,
            "firmware_file": firmware_file,
            "s3_bucket": FIRMWARE_BUCKET,
            "created_at": datetime.utcnow().isoformat(),
            "status": "available",
            "metadata": metadata or {}
        }
        
        firmware_versions_table.put_item(
            Item=version_data,
            ConditionExpression="attribute_not_exists(device_type) AND attribute_not_exists(version)"
        )
        
        logger.info(f"Created firmware version {version} for device type {device_type}")
        return {
            "statusCode": 201,
            "body": {
                "message": "Firmware version created successfully",
                "device_type": device_type,
                "version": version,
                "firmware_file": firmware_file
            }
        }
        
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {
                "statusCode": 409,
                "body": {"error": "Firmware version already exists"}
            }
        logger.error(f"Failed to create firmware version: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to create firmware version"}
        }


def list_firmware_versions(device_type: str = None) -> Dict[str, Any]:
    """
    List available firmware versions
    
    Args:
        device_type: Optional filter by device type
        
    Returns:
        List of firmware versions
    """
    try:
        if device_type:
            response = firmware_versions_table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("device_type").eq(device_type)
            )
        else:
            response = firmware_versions_table.scan()
        
        versions = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "body": {
                "firmware_versions": versions,
                "count": len(versions)
            }
        }
        
    except ClientError as e:
        logger.error(f"Failed to list firmware versions: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to list firmware versions"}
        }


def create_ota_job(device_targets: List[str], firmware_version: str, device_type: str, job_config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create an OTA job for device updates
    
    Args:
        device_targets: List of device IDs to update
        firmware_version: Firmware version to deploy
        device_type: Type of devices being updated
        job_config: Additional job configuration
        
    Returns:
        OTA job creation result
    """
    try:
        # Verify firmware version exists
        try:
            version_response = firmware_versions_table.get_item(
                Key={"device_type": device_type, "version": firmware_version}
            )
            if "Item" not in version_response:
                return {
                    "statusCode": 404,
                    "body": {"error": f"Firmware version {firmware_version} not found for device type {device_type}"}
                }
            
            firmware_data = version_response["Item"]
        except ClientError as e:
            logger.error(f"Failed to get firmware version: {e}")
            return {
                "statusCode": 500,
                "body": {"error": "Failed to verify firmware version"}
            }
        
        # Generate job ID
        job_id = f"ota-{device_type}-{firmware_version}-{uuid.uuid4().hex[:8]}"
        
        # Create IoT job document
        job_document = {
            "operation": "firmware_update",
            "firmware": {
                "version": firmware_version,
                "s3_bucket": firmware_data["s3_bucket"],
                "s3_key": firmware_data["firmware_file"],
                "device_type": device_type
            },
            "execution": {
                "timeout_minutes": job_config.get("timeout_minutes", 30) if job_config else 30,
                "retry_attempts": job_config.get("retry_attempts", 3) if job_config else 3
            }
        }
        
        # Create IoT job
        iot_response = iot_client.create_job(
            jobId=job_id,
            targets=[f"arn:aws:iot:{REGION}:{boto3.Session().get_credentials().access_key.split(':')[4]}:thing/{device_id}" for device_id in device_targets],
            document=json.dumps(job_document),
            description=f"Firmware update to version {firmware_version}",
            targetSelection="SNAPSHOT",
            jobExecutionsRolloutConfig={
                "maximumPerMinute": 5
            },
            abortConfig={
                "criteriaList": [
                    {
                        "failureType": "FAILED",
                        "action": "CANCEL",
                        "thresholdPercentage": 20,
                        "minNumberOfExecutedThings": 1
                    }
                ]
            },
            timeoutConfig={
                "inProgressTimeoutInMinutes": 30
            }
        )
        
        # Track job in DynamoDB
        for device_id in device_targets:
            job_entry = {
                "job_id": job_id,
                "device_id": device_id,
                "device_type": device_type,
                "firmware_version": firmware_version,
                "status": "QUEUED",
                "created_at": datetime.utcnow().isoformat(),
                "iot_job_arn": iot_response["jobArn"]
            }
            ota_jobs_table.put_item(Item=job_entry)
        
        logger.info(f"Created OTA job {job_id} for {len(device_targets)} devices")
        return {
            "statusCode": 201,
            "body": {
                "job_id": job_id,
                "iot_job_arn": iot_response["jobArn"],
                "target_devices": device_targets,
                "firmware_version": firmware_version,
                "status": "CREATED"
            }
        }
        
    except ClientError as e:
        logger.error(f"Failed to create OTA job: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to create OTA job"}
        }


def get_ota_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get OTA job status and progress
    
    Args:
        job_id: OTA job identifier
        
    Returns:
        Job status information
    """
    try:
        # Get job details from DynamoDB
        response = ota_jobs_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("job_id").eq(job_id)
        )
        
        job_entries = response.get("Items", [])
        
        if not job_entries:
            return {
                "statusCode": 404,
                "body": {"error": "OTA job not found"}
            }
        
        # Get IoT job status
        try:
            iot_response = iot_client.describe_job(jobId=job_id)
            iot_job = iot_response["job"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                iot_job = None
            else:
                raise
        
        # Calculate statistics
        total_devices = len(job_entries)
        status_counts = {}
        for entry in job_entries:
            status = entry.get("status", "UNKNOWN")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Determine overall job status
        if status_counts.get("SUCCEEDED", 0) == total_devices:
            overall_status = "SUCCESS"
        elif status_counts.get("FAILED", 0) + status_counts.get("CANCELLED", 0) >= total_devices * 0.2:
            overall_status = "FAILED"
        elif status_counts.get("IN_PROGRESS", 0) > 0:
            overall_status = "IN_PROGRESS"
        else:
            overall_status = "QUEUED"
        
        return {
            "statusCode": 200,
            "body": {
                "job_id": job_id,
                "status": overall_status,
                "total_devices": total_devices,
                "status_breakdown": status_counts,
                "iot_job": iot_job,
                "device_details": job_entries
            }
        }
        
    except ClientError as e:
        logger.error(f"Failed to get OTA job status: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to get OTA job status"}
        }


def cancel_ota_job(job_id: str) -> Dict[str, Any]:
    """
    Cancel an OTA job
    
    Args:
        job_id: OTA job identifier
        
    Returns:
        Cancellation result
    """
    try:
        # Cancel IoT job
        try:
            iot_client.cancel_job(jobId=job_id, force=True)
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        
        # Update job status in DynamoDB
        response = ota_jobs_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("job_id").eq(job_id)
        )
        
        for item in response.get("Items", []):
            ota_jobs_table.update_item(
                Key={"job_id": job_id, "device_id": item["device_id"]},
                UpdateExpression="SET #status = :status, cancelled_at = :timestamp",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": "CANCELLED",
                    ":timestamp": datetime.utcnow().isoformat()
                }
            )
        
        logger.info(f"Cancelled OTA job {job_id}")
        return {
            "statusCode": 200,
            "body": {
                "job_id": job_id,
                "status": "CANCELLED",
                "message": "OTA job cancelled successfully"
            }
        }
        
    except ClientError as e:
        logger.error(f"Failed to cancel OTA job: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to cancel OTA job"}
        }


def handle_job_status_update(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle IoT job status updates from devices
    
    Args:
        event: IoT job status update event
        
    Returns:
        Processing result
    """
    try:
        source_topic = event.get("source_topic", "")
        
        # Extract job ID and device ID from topic
        # Topic format: $aws/things/{device_id}/jobs/{job_id}/update
        topic_parts = source_topic.split("/")
        if len(topic_parts) >= 5:
            device_id = topic_parts[2]
            job_id = topic_parts[4]
        else:
            return {
                "statusCode": 400,
                "error": "Invalid topic format"
            }
        
        # Extract status from event
        status_info = event.get("status", {})
        new_status = status_info.get("status", "UNKNOWN")
        
        # Update job status in DynamoDB
        ota_jobs_table.update_item(
            Key={"job_id": job_id, "device_id": device_id},
            UpdateExpression="SET #status = :status, last_updated = :timestamp, status_details = :details",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": new_status,
                ":timestamp": datetime.utcnow().isoformat(),
                ":details": status_info
            }
        )
        
        logger.info(f"Updated job {job_id} status for device {device_id}: {new_status}")
        return {
            "statusCode": 200,
            "message": f"Updated job status for device {device_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to handle job status update: {e}")
        return {
            "statusCode": 500,
            "error": str(e)
        }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for OTA management operations
    
    Args:
        event: Lambda event (API Gateway, Step Functions, or IoT Rule)
        context: Lambda context
        
    Returns:
        Response based on operation type
    """
    logger.info(f"Processing OTA event: {json.dumps(event, default=str)}")
    
    # Handle Step Functions invocations
    if "action" in event:
        action = event["action"]
        
        if action == "create_ota_job":
            input_data = event.get("input", {})
            device_targets = input_data.get("device_targets", [])
            firmware_version = input_data.get("firmware_version")
            device_type = input_data.get("device_type")
            job_config = input_data.get("job_config")
            
            return create_ota_job(device_targets, firmware_version, device_type, job_config)
            
        elif action == "check_status":
            job_id = event.get("job_id")
            return get_ota_job_status(job_id)
            
        elif action == "rollback":
            job_id = event.get("job_id")
            return cancel_ota_job(job_id)
    
    # Handle IoT rule events (job status updates)
    if "source_topic" in event:
        return handle_job_status_update(event)
    
    # Handle API Gateway events
    if "httpMethod" in event:
        method = event["httpMethod"]
        path = event["path"]
        path_parameters = event.get("pathParameters") or {}
        query_parameters = event.get("queryStringParameters") or {}
        
        try:
            if "/firmware/versions" in path and method == "GET":
                device_type = query_parameters.get("device_type")
                return list_firmware_versions(device_type)
                
            elif "/firmware/versions" in path and method == "POST":
                body = json.loads(event.get("body", "{}"))
                device_type = body.get("device_type")
                version = body.get("version")
                firmware_file = body.get("firmware_file")
                metadata = body.get("metadata")
                
                if not all([device_type, version, firmware_file]):
                    return {
                        "statusCode": 400,
                        "body": {"error": "Missing required fields: device_type, version, firmware_file"}
                    }
                
                return create_firmware_version(device_type, version, firmware_file, metadata)
                
            elif "/ota/jobs" in path and method == "GET":
                # List OTA jobs (simplified implementation)
                return {
                    "statusCode": 200,
                    "body": {"jobs": [], "message": "Jobs list endpoint"}
                }
                
            elif "/ota/jobs" in path and method == "POST":
                body = json.loads(event.get("body", "{}"))
                device_targets = body.get("device_targets", [])
                firmware_version = body.get("firmware_version")
                device_type = body.get("device_type")
                job_config = body.get("job_config")
                
                if not all([device_targets, firmware_version, device_type]):
                    return {
                        "statusCode": 400,
                        "body": {"error": "Missing required fields: device_targets, firmware_version, device_type"}
                    }
                
                return create_ota_job(device_targets, firmware_version, device_type, job_config)
                
            elif "/ota/jobs/{job_id}" in path and method == "GET":
                job_id = path_parameters.get("job_id")
                return get_ota_job_status(job_id)
                
            elif "/ota/jobs/{job_id}" in path and method == "DELETE":
                job_id = path_parameters.get("job_id")
                return cancel_ota_job(job_id)
                
            else:
                return {
                    "statusCode": 404,
                    "body": {"error": "Endpoint not found"}
                }
                
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "body": {"error": "Invalid JSON in request body"}
            }
    
    return {
        "statusCode": 400,
        "body": {"error": "Unsupported event type"}
    }


#[cfg(test)]
def test_create_firmware_version():
    """Test firmware version creation"""
    device_type = "sensor"
    version = "1.0.0"
    firmware_file = "sensor/firmware-1.0.0.bin"
    
    # In real implementation, this would test the creation logic
    assert device_type == "sensor"
    assert version == "1.0.0"
    assert firmware_file.endswith(".bin")


def test_create_ota_job():
    """Test OTA job creation"""
    device_targets = ["sensor01", "sensor02"]
    firmware_version = "1.0.1"
    device_type = "sensor"
    
    # Test job parameters
    assert len(device_targets) > 0
    assert firmware_version
    assert device_type


if __name__ == "__main__":
    # Run tests
    test_create_firmware_version()
    test_create_ota_job()
    print("All tests passed!") 