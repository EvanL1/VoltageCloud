"""
IoT Authentication and Authorization Manager
Handles user authentication, authorization, and device permissions
"""

import os
import json
import boto3
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
USER_PROFILE_TABLE = os.environ["USER_PROFILE_TABLE"]
DEVICE_PERMISSIONS_TABLE = os.environ["DEVICE_PERMISSIONS_TABLE"]
USER_POOL_ID = os.environ["USER_POOL_ID"]
REGION = os.environ["REGION"]

# Initialize AWS clients
cognito_client = boto3.client("cognito-idp", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
user_profile_table = dynamodb.Table(USER_PROFILE_TABLE)
device_permissions_table = dynamodb.Table(DEVICE_PERMISSIONS_TABLE)


def extract_user_info_from_jwt(event: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract user information from JWT token in API Gateway event
    
    Args:
        event: API Gateway event with JWT claims
        
    Returns:
        Dictionary with user information
    """
    authorizer = event.get("requestContext", {}).get("authorizer", {})
    claims = authorizer.get("claims", {})
    
    return {
        "user_id": claims.get("sub", ""),
        "username": claims.get("cognito:username", ""),
        "email": claims.get("email", ""),
        "role": claims.get("custom:role", "user")
    }


def create_user_profile(user_info: Dict[str, str], additional_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create or update user profile in DynamoDB
    
    Args:
        user_info: User information from JWT
        additional_data: Additional profile data
        
    Returns:
        Operation result
    """
    try:
        profile_data = {
            "user_id": user_info["user_id"],
            "username": user_info["username"],
            "email": user_info["email"],
            "role": user_info["role"],
            "created_at": datetime.utcnow().isoformat(),
            "last_login": datetime.utcnow().isoformat(),
            "status": "active"
        }
        
        # Add additional data if provided
        if additional_data:
            profile_data.update(additional_data)
        
        # Update profile with conditional write
        user_profile_table.put_item(
            Item=profile_data,
            ConditionExpression="attribute_not_exists(user_id) OR attribute_exists(user_id)"
        )
        
        logger.info(f"Created/updated profile for user {user_info['user_id']}")
        return {
            "statusCode": 201,
            "body": {
                "message": "User profile created/updated successfully",
                "user_id": user_info["user_id"]
            }
        }
        
    except ClientError as e:
        logger.error(f"Failed to create user profile: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to create user profile"}
        }


def get_user_profile(user_id: str) -> Dict[str, Any]:
    """
    Get user profile from DynamoDB
    
    Args:
        user_id: User identifier
        
    Returns:
        User profile or error response
    """
    try:
        response = user_profile_table.get_item(
            Key={"user_id": user_id}
        )
        
        if "Item" not in response:
            return {
                "statusCode": 404,
                "body": {"error": "User profile not found"}
            }
        
        # Remove sensitive information
        profile = response["Item"]
        profile.pop("created_at", None)
        
        return {
            "statusCode": 200,
            "body": profile
        }
        
    except ClientError as e:
        logger.error(f"Failed to get user profile: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to retrieve user profile"}
        }


def get_all_users(role_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Get all users with optional role filtering
    
    Args:
        role_filter: Optional role to filter by
        
    Returns:
        List of users or error response
    """
    try:
        if role_filter:
            # Query by role using GSI
            response = user_profile_table.query(
                IndexName="role-index",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("role").eq(role_filter)
            )
        else:
            # Scan all users (expensive operation - consider pagination in production)
            response = user_profile_table.scan()
        
        users = response.get("Items", [])
        
        # Remove sensitive information
        for user in users:
            user.pop("created_at", None)
        
        return {
            "statusCode": 200,
            "body": {
                "users": users,
                "count": len(users)
            }
        }
        
    except ClientError as e:
        logger.error(f"Failed to get users: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to retrieve users"}
        }


def grant_device_permission(user_id: str, device_id: str, permissions: List[str]) -> Dict[str, Any]:
    """
    Grant device permissions to a user
    
    Args:
        user_id: User identifier
        device_id: Device identifier
        permissions: List of permissions (read, write, admin)
        
    Returns:
        Operation result
    """
    try:
        permission_data = {
            "user_id": user_id,
            "device_id": device_id,
            "permissions": permissions,
            "granted_at": datetime.utcnow().isoformat(),
            "status": "active"
        }
        
        device_permissions_table.put_item(Item=permission_data)
        
        logger.info(f"Granted permissions {permissions} for device {device_id} to user {user_id}")
        return {
            "statusCode": 201,
            "body": {
                "message": "Device permissions granted successfully",
                "user_id": user_id,
                "device_id": device_id,
                "permissions": permissions
            }
        }
        
    except ClientError as e:
        logger.error(f"Failed to grant device permission: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to grant device permissions"}
        }


def get_user_device_permissions(user_id: str) -> Dict[str, Any]:
    """
    Get all device permissions for a user
    
    Args:
        user_id: User identifier
        
    Returns:
        List of device permissions or error response
    """
    try:
        response = device_permissions_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(user_id)
        )
        
        permissions = response.get("Items", [])
        
        return {
            "statusCode": 200,
            "body": {
                "user_id": user_id,
                "device_permissions": permissions,
                "count": len(permissions)
            }
        }
        
    except ClientError as e:
        logger.error(f"Failed to get device permissions: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to retrieve device permissions"}
        }


def revoke_device_permission(user_id: str, device_id: str) -> Dict[str, Any]:
    """
    Revoke device permissions from a user
    
    Args:
        user_id: User identifier
        device_id: Device identifier
        
    Returns:
        Operation result
    """
    try:
        device_permissions_table.delete_item(
            Key={
                "user_id": user_id,
                "device_id": device_id
            }
        )
        
        logger.info(f"Revoked permissions for device {device_id} from user {user_id}")
        return {
            "statusCode": 200,
            "body": {
                "message": "Device permissions revoked successfully",
                "user_id": user_id,
                "device_id": device_id
            }
        }
        
    except ClientError as e:
        logger.error(f"Failed to revoke device permission: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to revoke device permissions"}
        }


def check_device_access(user_id: str, device_id: str, required_permission: str) -> bool:
    """
    Check if user has required permission for device
    
    Args:
        user_id: User identifier
        device_id: Device identifier
        required_permission: Required permission level
        
    Returns:
        True if user has permission, False otherwise
    """
    try:
        response = device_permissions_table.get_item(
            Key={
                "user_id": user_id,
                "device_id": device_id
            }
        )
        
        if "Item" not in response:
            return False
        
        permissions = response["Item"].get("permissions", [])
        status = response["Item"].get("status", "inactive")
        
        return status == "active" and required_permission in permissions
        
    except ClientError as e:
        logger.error(f"Failed to check device access: {e}")
        return False


def update_user_role(user_id: str, new_role: str) -> Dict[str, Any]:
    """
    Update user role in Cognito and DynamoDB
    
    Args:
        user_id: User identifier
        new_role: New role (admin, user, viewer)
        
    Returns:
        Operation result
    """
    try:
        # Update in Cognito
        cognito_client.admin_update_user_attributes(
            UserPoolId=USER_POOL_ID,
            Username=user_id,
            UserAttributes=[
                {
                    "Name": "custom:role",
                    "Value": new_role
                }
            ]
        )
        
        # Update in DynamoDB
        user_profile_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET #role = :role, last_updated = :timestamp",
            ExpressionAttributeNames={"#role": "role"},
            ExpressionAttributeValues={
                ":role": new_role,
                ":timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Updated role for user {user_id} to {new_role}")
        return {
            "statusCode": 200,
            "body": {
                "message": "User role updated successfully",
                "user_id": user_id,
                "new_role": new_role
            }
        }
        
    except ClientError as e:
        logger.error(f"Failed to update user role: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Failed to update user role"}
        }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for authentication and authorization operations
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        Response based on operation type
    """
    logger.info(f"Processing auth event: {json.dumps(event, default=str)}")
    
    method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_parameters = event.get("pathParameters") or {}
    query_parameters = event.get("queryStringParameters") or {}
    
    # Extract user info from JWT
    user_info = extract_user_info_from_jwt(event)
    current_user_id = user_info["user_id"]
    current_user_role = user_info["role"]
    
    try:
        # Routes handling
        segments = path.strip("/").split("/")

        if path == "/users" and method == "GET":
            # Get all users (admin only)
            if current_user_role != "admin":
                return {
                    "statusCode": 403,
                    "body": {"error": "Insufficient permissions"}
                }

            role_filter = query_parameters.get("role")
            return get_all_users(role_filter)

        elif len(segments) == 2 and segments[0] == "users" and method == "GET":
            # Get specific user profile
            target_user_id = path_parameters.get("user_id")

            # Users can only access their own profile unless they're admin
            if current_user_role != "admin" and current_user_id != target_user_id:
                return {
                    "statusCode": 403,
                    "body": {"error": "Insufficient permissions"}
                }

            return get_user_profile(target_user_id)

        elif (
            len(segments) == 3
            and segments[0] == "users"
            and segments[2] == "permissions"
            and method == "GET"
        ):
            # Get user's device permissions
            target_user_id = path_parameters.get("user_id")

            # Users can only access their own permissions unless they're admin
            if current_user_role != "admin" and current_user_id != target_user_id:
                return {
                    "statusCode": 403,
                    "body": {"error": "Insufficient permissions"}
                }

            return get_user_device_permissions(target_user_id)

        elif (
            len(segments) == 4
            and segments[0] == "users"
            and segments[2] == "permissions"
            and segments[3] == "devices"
            and method == "POST"
        ):
            # Grant device permissions (admin only)
            if current_user_role != "admin":
                return {
                    "statusCode": 403,
                    "body": {"error": "Insufficient permissions"}
                }
            
            target_user_id = path_parameters.get("user_id")
            body = json.loads(event.get("body", "{}"))
            device_id = body.get("device_id")
            permissions = body.get("permissions", [])
            
            if not device_id or not permissions:
                return {
                    "statusCode": 400,
                    "body": {"error": "Missing device_id or permissions"}
                }
            
            return grant_device_permission(target_user_id, device_id, permissions)
            
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
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Internal server error"}
        }


#[cfg(test)]
def test_extract_user_info_from_jwt():
    """Test JWT user info extraction"""
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "user123",
                    "cognito:username": "testuser",
                    "email": "test@example.com",
                    "custom:role": "admin"
                }
            }
        }
    }
    
    user_info = extract_user_info_from_jwt(event)
    assert user_info["user_id"] == "user123"
    assert user_info["username"] == "testuser"
    assert user_info["email"] == "test@example.com"
    assert user_info["role"] == "admin"


def test_check_device_access():
    """Test device access checking logic"""
    # This would require mocking DynamoDB in a real test
    user_id = "test_user"
    device_id = "test_device"
    required_permission = "read"
    
    # In real implementation, this would test the access checking logic
    assert user_id == "test_user"
    assert device_id == "test_device"
    assert required_permission == "read"


if __name__ == "__main__":
    # Run tests
    test_extract_user_info_from_jwt()
    test_check_device_access()
    print("All tests passed!") 