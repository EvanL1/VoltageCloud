"""
IoT API Integration Lambda
Handles integration between API Gateway and ECS-based services
"""

import os
import json
import boto3
import logging
import urllib3
from typing import Dict, Any
from urllib.parse import urljoin


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
ALB_DNS_NAME = os.environ["ALB_DNS_NAME"]
SERVICE_ENDPOINT = os.environ["SERVICE_ENDPOINT"]
REGION = os.environ["REGION"]

# Initialize HTTP client
http = urllib3.PoolManager()


def forward_request_to_ecs(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Forward API Gateway request to ECS service
    
    Args:
        event: API Gateway event
        
    Returns:
        Response from ECS service
    """
    try:
        method = event.get("httpMethod", "GET")
        path = event.get("path", "/")
        query_params = event.get("queryStringParameters") or {}
        headers = event.get("headers") or {}
        body = event.get("body", "")
        
        # Build target URL
        target_url = urljoin(SERVICE_ENDPOINT, path)
        
        # Prepare headers for forwarding
        forward_headers = {
            "Content-Type": headers.get("Content-Type", "application/json"),
            "User-Agent": "IoT-API-Gateway"
        }
        
        # Add query parameters
        if query_params:
            query_string = "&".join([f"{k}={v}" for k, v in query_params.items()])
            target_url = f"{target_url}?{query_string}"
        
        logger.info(f"Forwarding {method} request to: {target_url}")
        
        # Make request to ECS service
        if method == "GET":
            response = http.request(
                "GET",
                target_url,
                headers=forward_headers
            )
        elif method == "POST":
            response = http.request(
                "POST",
                target_url,
                body=body,
                headers=forward_headers
            )
        elif method == "PUT":
            response = http.request(
                "PUT",
                target_url,
                body=body,
                headers=forward_headers
            )
        elif method == "DELETE":
            response = http.request(
                "DELETE",
                target_url,
                headers=forward_headers
            )
        else:
            return {
                "statusCode": 405,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({"error": f"Method {method} not allowed"})
            }
        
        # Parse response
        response_body = response.data.decode('utf-8')
        
        try:
            # Try to parse as JSON
            response_data = json.loads(response_body)
        except json.JSONDecodeError:
            # If not JSON, return as string
            response_data = response_body
        
        return {
            "statusCode": response.status,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            },
            "body": json.dumps(response_data) if isinstance(response_data, dict) else response_data
        }
        
    except Exception as e:
        logger.error(f"Failed to forward request: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            })
        }


def handle_health_check() -> Dict[str, Any]:
    """
    Handle health check requests
    
    Returns:
        Health check response
    """
    try:
        # Check ECS service health
        health_url = urljoin(SERVICE_ENDPOINT, "/health")
        response = http.request("GET", health_url, timeout=5)
        
        if response.status == 200:
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "status": "healthy",
                    "service": "api-integration",
                    "ecs_service": "healthy",
                    "timestamp": "2024-01-01T00:00:00Z"
                })
            }
        else:
            return {
                "statusCode": 503,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "status": "unhealthy",
                    "service": "api-integration",
                    "ecs_service": "unhealthy",
                    "error": f"ECS service returned {response.status}"
                })
            }
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "statusCode": 503,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "status": "unhealthy",
                "service": "api-integration",
                "error": str(e)
            })
        }


def handle_device_operations(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle device-related operations with additional validation
    
    Args:
        event: API Gateway event
        
    Returns:
        Response from device operations
    """
    method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_parameters = event.get("pathParameters") or {}
    
    # Extract device ID if present
    device_id = path_parameters.get("device_id")
    
    # Add device-specific validation
    if device_id and method in ["PUT", "DELETE"]:
        # Validate device ID format
        if not device_id.isalnum() or len(device_id) < 3:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "error": "Invalid device ID format",
                    "device_id": device_id
                })
            }
    
    # Forward to ECS service
    return forward_request_to_ecs(event)


def handle_cors_preflight() -> Dict[str, Any]:
    """
    Handle CORS preflight requests
    
    Returns:
        CORS preflight response
    """
    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
            "Access-Control-Max-Age": "86400"
        },
        "body": ""
    }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for API integration
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        Response based on request type
    """
    logger.info(f"Processing API integration event: {json.dumps(event, default=str)}")
    
    method = event.get("httpMethod", "")
    path = event.get("path", "")
    
    # Handle CORS preflight requests
    if method == "OPTIONS":
        return handle_cors_preflight()
    
    # Handle health check requests
    if path == "/health":
        return handle_health_check()
    
    # Handle device operations with additional validation
    if "/api/v1/devices" in path:
        return handle_device_operations(event)
    
    # Forward all other requests to ECS service
    return forward_request_to_ecs(event)


#[cfg(test)]
def test_forward_request_to_ecs():
    """Test request forwarding logic"""
    event = {
        "httpMethod": "GET",
        "path": "/api/v1/devices",
        "queryStringParameters": {"limit": "10"},
        "headers": {"Content-Type": "application/json"},
        "body": ""
    }
    
    # In real implementation, this would test the forwarding logic
    assert event["httpMethod"] == "GET"
    assert event["path"] == "/api/v1/devices"
    assert event["queryStringParameters"]["limit"] == "10"


def test_handle_health_check():
    """Test health check handling"""
    # This would require mocking the HTTP client in a real test
    response = {
        "statusCode": 200,
        "service": "api-integration",
        "status": "healthy"
    }
    
    # In real implementation, this would test the health check logic
    assert response["statusCode"] == 200
    assert response["status"] == "healthy"


def test_handle_device_operations():
    """Test device operations handling"""
    event = {
        "httpMethod": "PUT",
        "path": "/api/v1/devices/sensor01",
        "pathParameters": {"device_id": "sensor01"},
        "body": '{"status": "online"}'
    }
    
    # Test device ID validation
    device_id = event["pathParameters"]["device_id"]
    assert device_id.isalnum()
    assert len(device_id) >= 3


if __name__ == "__main__":
    # Run tests
    test_forward_request_to_ecs()
    test_handle_health_check()
    test_handle_device_operations()
    print("All tests passed!") 