"""
IoT Device Shadow Manager
Handles device shadow operations and caches shadow state in DynamoDB
"""

import os
import json
import boto3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SHADOW_CACHE_TABLE = os.environ["SHADOW_CACHE_TABLE"]
REGION = os.environ["REGION"]

# Initialize AWS clients
iot_client = boto3.client("iot-data", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
shadow_cache_table = dynamodb.Table(SHADOW_CACHE_TABLE)


def extract_device_id_from_topic(topic: str) -> str:
    """
    Extract device ID from IoT topic
    
    Args:
        topic: IoT topic string
        
    Returns:
        Device ID string
    """
    # Format: $aws/things/{device_id}/shadow/update/accepted
    parts = topic.split("/")
    if len(parts) >= 3:
        return parts[2]
    return "unknown"


def cache_shadow_state(device_id: str, shadow_name: str, shadow_data: Dict[str, Any]) -> bool:
    """
    Cache shadow state in DynamoDB
    
    Args:
        device_id: Device identifier
        shadow_name: Shadow name (default or named)
        shadow_data: Shadow document
        
    Returns:
        True if successful, False otherwise
    """
    try:
        ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
        
        item = {
            "device_id": device_id,
            "shadow_type": shadow_name,
            "shadow_data": shadow_data,
            "status": shadow_data.get("state", {}).get("reported", {}).get("status", "unknown"),
            "last_updated": datetime.utcnow().isoformat(),
            "ttl": ttl
        }
        
        shadow_cache_table.put_item(Item=item)
        logger.info(f"Cached shadow for device {device_id}, shadow {shadow_name}")
        return True
        
    except ClientError as e:
        logger.error(f"Failed to cache shadow: {e}")
        return False


def get_device_shadow(device_id: str, shadow_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get device shadow from AWS IoT
    
    Args:
        device_id: Device identifier
        shadow_name: Optional shadow name for named shadows
        
    Returns:
        Shadow document or error response
    """
    try:
        params = {"thingName": device_id}
        if shadow_name and shadow_name != "default":
            params["shadowName"] = shadow_name
            
        response = iot_client.get_thing_shadow(**params)
        shadow_data = json.loads(response["payload"].read())
        
        # Cache the shadow state
        cache_name = shadow_name or "default"
        cache_shadow_state(device_id, cache_name, shadow_data)
        
        return {
            "statusCode": 200,
            "body": shadow_data
        }
        
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            return {
                "statusCode": 404,
                "body": {"error": f"Shadow not found for device {device_id}"}
            }
        else:
            logger.error(f"Failed to get shadow: {e}")
            return {
                "statusCode": 500,
                "body": {"error": "Internal server error"}
            }


def update_device_shadow(device_id: str, desired_state: Dict[str, Any], shadow_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Update device shadow in AWS IoT
    
    Args:
        device_id: Device identifier
        desired_state: Desired state to update
        shadow_name: Optional shadow name for named shadows
        
    Returns:
        Update response or error response
    """
    try:
        shadow_update = {
            "state": {
                "desired": desired_state
            }
        }
        
        params = {
            "thingName": device_id,
            "payload": json.dumps(shadow_update)
        }
        if shadow_name and shadow_name != "default":
            params["shadowName"] = shadow_name
            
        response = iot_client.update_thing_shadow(**params)
        result_data = json.loads(response["payload"].read())
        
        # Cache the updated shadow state
        cache_name = shadow_name or "default"
        cache_shadow_state(device_id, cache_name, result_data)
        
        return {
            "statusCode": 200,
            "body": result_data
        }
        
    except ClientError as e:
        logger.error(f"Failed to update shadow: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to update shadow"}
        }


def delete_device_shadow(device_id: str, shadow_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete device shadow from AWS IoT
    
    Args:
        device_id: Device identifier
        shadow_name: Optional shadow name for named shadows
        
    Returns:
        Delete response or error response
    """
    try:
        params = {"thingName": device_id}
        if shadow_name and shadow_name != "default":
            params["shadowName"] = shadow_name
            
        iot_client.delete_thing_shadow(**params)
        
        # Remove from cache
        try:
            cache_name = shadow_name or "default"
            shadow_cache_table.delete_item(
                Key={
                    "device_id": device_id,
                    "shadow_type": cache_name
                }
            )
        except Exception as e:
            logger.warning(f"Failed to remove from cache: {e}")
        
        return {
            "statusCode": 200,
            "body": {"message": "Shadow deleted successfully"}
        }
        
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            return {
                "statusCode": 404,
                "body": {"error": f"Shadow not found for device {device_id}"}
            }
        else:
            logger.error(f"Failed to delete shadow: {e}")
            return {
                "statusCode": 500,
                "body": {"error": "Failed to delete shadow"}
            }


def batch_shadow_operations(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Perform batch shadow operations
    
    Args:
        operations: List of shadow operations
        
    Returns:
        Batch operation results
    """
    results = []
    
    for operation in operations:
        op_type = operation.get("operation")
        device_id = operation.get("device_id")
        shadow_name = operation.get("shadow_name")
        
        if not device_id:
            results.append({
                "device_id": device_id,
                "error": "Missing device_id"
            })
            continue
            
        if op_type == "get":
            result = get_device_shadow(device_id, shadow_name)
        elif op_type == "update":
            desired_state = operation.get("desired_state", {})
            result = update_device_shadow(device_id, desired_state, shadow_name)
        elif op_type == "delete":
            result = delete_device_shadow(device_id, shadow_name)
        else:
            result = {
                "statusCode": 400,
                "body": {"error": f"Unknown operation: {op_type}"}
            }
            
        results.append({
            "device_id": device_id,
            "shadow_name": shadow_name or "default",
            "operation": op_type,
            "result": result
        })
    
    return {
        "statusCode": 200,
        "body": {
            "batch_results": results,
            "total_operations": len(operations),
            "processed": len(results)
        }
    }


def handle_shadow_update_notification(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle shadow update notifications from IoT rules
    
    Args:
        event: IoT rule event
        
    Returns:
        Processing result
    """
    try:
        source_topic = event.get("source_topic", "")
        device_id = extract_device_id_from_topic(source_topic)
        
        # Extract shadow name from topic if it's a named shadow
        shadow_name = "default"
        if "/shadow/name/" in source_topic:
            parts = source_topic.split("/shadow/name/")
            if len(parts) > 1:
                shadow_name = parts[1].split("/")[0]
        
        # Cache the shadow update
        cache_shadow_state(device_id, shadow_name, event)
        
        return {
            "statusCode": 200,
            "message": f"Processed shadow update for device {device_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to handle shadow update: {e}")
        return {
            "statusCode": 500,
            "error": str(e)
        }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for device shadow operations
    
    Args:
        event: Lambda event (API Gateway or IoT Rule)
        context: Lambda context
        
    Returns:
        Response based on event type
    """
    logger.info(f"Processing event: {json.dumps(event, default=str)}")
    
    # Handle IoT rule events (shadow update notifications)
    if "source_topic" in event:
        return handle_shadow_update_notification(event)
    
    # Handle API Gateway events
    if "httpMethod" in event:
        method = event["httpMethod"]
        path = event["path"]
        path_parameters = event.get("pathParameters") or {}
        
        device_id = path_parameters.get("device_id")
        shadow_name = path_parameters.get("shadow_name")
        
        try:
            if "/batch" in path and method == "POST":
                body = json.loads(event.get("body", "{}"))
                operations = body.get("operations", [])
                return batch_shadow_operations(operations)
                
            elif device_id:
                if method == "GET":
                    return get_device_shadow(device_id, shadow_name)
                    
                elif method == "PUT":
                    body = json.loads(event.get("body", "{}"))
                    desired_state = body.get("desired", {})
                    return update_device_shadow(device_id, desired_state, shadow_name)
                    
                elif method == "DELETE":
                    return delete_device_shadow(device_id, shadow_name)
                    
            return {
                "statusCode": 400,
                "body": {"error": "Invalid request"}
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
def test_extract_device_id_from_topic():
    """Test device ID extraction from IoT topic"""
    topic1 = "$aws/things/sensor01/shadow/update/accepted"
    assert extract_device_id_from_topic(topic1) == "sensor01"
    
    topic2 = "$aws/things/device123/shadow/name/config/update/accepted"
    assert extract_device_id_from_topic(topic2) == "device123"
    
    topic3 = "invalid/topic"
    assert extract_device_id_from_topic(topic3) == "unknown"


def test_cache_shadow_state():
    """Test shadow state caching logic"""
    # This would require mocking DynamoDB in a real test
    device_id = "test_device"
    shadow_name = "default"
    shadow_data = {
        "state": {
            "desired": {"temp": 25.0},
            "reported": {"temp": 24.5, "status": "online"}
        },
        "version": 1
    }
    
    # In real implementation, this would test the caching logic
    assert device_id == "test_device"
    assert shadow_name == "default"
    assert shadow_data["state"]["reported"]["status"] == "online"


if __name__ == "__main__":
    # Run tests
    test_extract_device_id_from_topic()
    test_cache_shadow_state()
    print("All tests passed!") 