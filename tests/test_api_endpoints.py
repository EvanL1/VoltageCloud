"""
API endpoint tests for IoT platform
Tests REST API endpoints, authentication, and data access
"""

import pytest
import json
import boto3
from unittest.mock import Mock, patch, MagicMock
import requests
from moto import mock_dynamodb, mock_apigateway, mock_cognito_idp
import base64


class TestDeviceShadowAPI:
    """Test Device Shadow API endpoints"""
    
    @patch('boto3.resource')
    def test_get_device_shadow_endpoint(self, mock_dynamodb):
        """Test GET /devices/{device_id}/shadow endpoint"""
        # Mock DynamoDB response
        mock_table = Mock()
        mock_table.get_item.return_value = {
            'Item': {
                'device_id': 'device_001',
                'shadow_document': json.dumps({
                    'state': {
                        'reported': {
                            'temperature': 23.5,
                            'humidity': 65.2
                        }
                    },
                    'version': 1
                })
            }
        }
        mock_dynamodb.return_value.Table.return_value = mock_table
        
        # Mock API Gateway handler
        def get_device_shadow_handler(event, context):
            device_id = event['pathParameters']['device_id']
            
            # Mock authorization check
            if not event.get('headers', {}).get('Authorization'):
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'Unauthorized'})
                }
            
            try:
                dynamodb = boto3.resource('dynamodb')
                table = dynamodb.Table('device-shadow-table')
                
                response = table.get_item(Key={'device_id': device_id})
                
                if 'Item' in response:
                    shadow_doc = json.loads(response['Item']['shadow_document'])
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'device_id': device_id,
                            'shadow': shadow_doc
                        })
                    }
                else:
                    return {
                        'statusCode': 404,
                        'body': json.dumps({'error': 'Device not found'})
                    }
                    
            except Exception as e:
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': str(e)})
                }
        
        # Test successful request
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'device_id': 'device_001'},
            'headers': {'Authorization': 'Bearer valid-token'}
        }
        
        response = get_device_shadow_handler(event, {})
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['device_id'] == 'device_001'
        assert 'shadow' in body
        
        # Test unauthorized request
        event_no_auth = {
            'httpMethod': 'GET',
            'pathParameters': {'device_id': 'device_001'},
            'headers': {}
        }
        
        response_no_auth = get_device_shadow_handler(event_no_auth, {})
        assert response_no_auth['statusCode'] == 401
    
    @patch('boto3.resource')
    def test_update_device_shadow_endpoint(self, mock_dynamodb):
        """Test PUT /devices/{device_id}/shadow endpoint"""
        mock_table = Mock()
        mock_table.put_item.return_value = {}
        mock_dynamodb.return_value.Table.return_value = mock_table
        
        def update_device_shadow_handler(event, context):
            device_id = event['pathParameters']['device_id']
            
            # Mock authorization check
            if not event.get('headers', {}).get('Authorization'):
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'Unauthorized'})
                }
            
            try:
                shadow_update = json.loads(event['body'])
                
                # Validate shadow update structure
                if 'state' not in shadow_update:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'Invalid shadow update format'})
                    }
                
                dynamodb = boto3.resource('dynamodb')
                table = dynamodb.Table('device-shadow-table')
                
                table.put_item(
                    Item={
                        'device_id': device_id,
                        'shadow_document': json.dumps(shadow_update),
                        'updated_at': '2024-01-01T00:00:00Z'
                    }
                )
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Shadow updated successfully'})
                }
                
            except json.JSONDecodeError:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid JSON in request body'})
                }
            except Exception as e:
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': str(e)})
                }
        
        # Test successful update
        event = {
            'httpMethod': 'PUT',
            'pathParameters': {'device_id': 'device_001'},
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'state': {
                    'desired': {
                        'temperature_threshold': 25.0
                    }
                }
            })
        }
        
        response = update_device_shadow_handler(event, {})
        
        assert response['statusCode'] == 200
        mock_table.put_item.assert_called_once()
        
        # Test invalid JSON
        event_invalid_json = event.copy()
        event_invalid_json['body'] = 'invalid json'
        
        response_invalid = update_device_shadow_handler(event_invalid_json, {})
        assert response_invalid['statusCode'] == 400


class TestDataLakeAPI:
    """Test Data Lake API endpoints"""
    
    @patch('boto3.client')
    def test_query_sql_endpoint(self, mock_boto3_client):
        """Test POST /query/sql endpoint"""
        # Mock Athena client
        mock_athena = Mock()
        mock_athena.start_query_execution.return_value = {
            'QueryExecutionId': 'test-query-id'
        }
        mock_athena.get_query_execution.return_value = {
            'QueryExecution': {
                'Status': {'State': 'SUCCEEDED'}
            }
        }
        mock_athena.get_query_results.return_value = {
            'ResultSet': {
                'Rows': [
                    {
                        'Data': [
                            {'VarCharValue': 'device_001'},
                            {'VarCharValue': '23.5'}
                        ]
                    }
                ]
            }
        }
        mock_boto3_client.return_value = mock_athena
        
        def query_sql_handler(event, context):
            # Mock authorization check
            if not event.get('headers', {}).get('Authorization'):
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'Unauthorized'})
                }
            
            try:
                body = json.loads(event['body'])
                query = body.get('query')
                
                if not query:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'Query is required'})
                    }
                
                # Basic SQL injection protection
                dangerous_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'CREATE', 'ALTER']
                if any(keyword in query.upper() for keyword in dangerous_keywords):
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'Query contains prohibited keywords'})
                    }
                
                athena = boto3.client('athena')
                
                # Start query execution
                response = athena.start_query_execution(
                    QueryString=query,
                    QueryExecutionContext={'Database': 'iot_data_lake'},
                    WorkGroup='iot-analytics'
                )
                
                query_id = response['QueryExecutionId']
                
                # Check query status (simplified for testing)
                status_response = athena.get_query_execution(
                    QueryExecutionId=query_id
                )
                
                if status_response['QueryExecution']['Status']['State'] == 'SUCCEEDED':
                    results = athena.get_query_results(
                        QueryExecutionId=query_id
                    )
                    return {
                        'statusCode': 200,
                        'body': json.dumps({
                            'queryId': query_id,
                            'results': results['ResultSet']['Rows']
                        })
                    }
                else:
                    return {
                        'statusCode': 500,
                        'body': json.dumps({'error': 'Query execution failed'})
                    }
                    
            except json.JSONDecodeError:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid JSON in request body'})
                }
            except Exception as e:
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': str(e)})
                }
        
        # Test successful query
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'query': 'SELECT device_id, AVG(temperature) FROM iot_data_lake.raw_iot_data GROUP BY device_id'
            })
        }
        
        response = query_sql_handler(event, {})
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'queryId' in body
        assert 'results' in body
        
        # Test SQL injection attempt
        event_injection = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'query': 'SELECT * FROM users; DROP TABLE users;'
            })
        }
        
        response_injection = query_sql_handler(event_injection, {})
        assert response_injection['statusCode'] == 400


class TestOtaAPI:
    """Test OTA update API endpoints"""
    
    @patch('boto3.client')
    def test_create_ota_job_endpoint(self, mock_boto3_client):
        """Test POST /ota/jobs endpoint"""
        # Mock IoT client
        mock_iot = Mock()
        mock_iot.create_job.return_value = {
            'jobArn': 'arn:aws:iot:us-east-1:123456789012:job/test-job',
            'jobId': 'test-job'
        }
        mock_boto3_client.return_value = mock_iot
        
        def create_ota_job_handler(event, context):
            # Mock authorization check
            if not event.get('headers', {}).get('Authorization'):
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'Unauthorized'})
                }
            
            try:
                body = json.loads(event['body'])
                
                # Validate required fields
                required_fields = ['jobId', 'targets', 'firmwareUrl', 'version']
                missing_fields = [field for field in required_fields if field not in body]
                
                if missing_fields:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({
                            'error': f'Missing required fields: {", ".join(missing_fields)}'
                        })
                    }
                
                iot = boto3.client('iot')
                
                job_document = {
                    'operation': 'firmware_update',
                    'firmwareUrl': body['firmwareUrl'],
                    'version': body['version']
                }
                
                response = iot.create_job(
                    jobId=body['jobId'],
                    targets=body['targets'],
                    document=json.dumps(job_document),
                    jobExecutionsRolloutConfig={
                        'maximumPerMinute': body.get('rolloutRate', 10)
                    }
                )
                
                return {
                    'statusCode': 201,
                    'body': json.dumps({
                        'jobId': response['jobId'],
                        'jobArn': response['jobArn'],
                        'status': 'CREATED'
                    })
                }
                
            except json.JSONDecodeError:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid JSON in request body'})
                }
            except Exception as e:
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': str(e)})
                }
        
        # Test successful job creation
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'jobId': 'test-ota-job',
                'targets': ['device_001', 'device_002'],
                'firmwareUrl': 's3://firmware-bucket/firmware-v1.0.bin',
                'version': '1.0',
                'rolloutRate': 5
            })
        }
        
        response = create_ota_job_handler(event, {})
        
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['jobId'] == 'test-ota-job'
        assert body['status'] == 'CREATED'
        
        # Test missing required fields
        event_missing_fields = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'jobId': 'test-job'
                # Missing other required fields
            })
        }
        
        response_missing = create_ota_job_handler(event_missing_fields, {})
        assert response_missing['statusCode'] == 400


class TestAuthorizationMiddleware:
    """Test API authorization middleware"""
    
    @patch('boto3.client')
    def test_jwt_token_validation(self, mock_cognito):
        """Test JWT token validation"""
        # Mock Cognito client
        mock_cognito_client = Mock()
        mock_cognito_client.get_user.return_value = {
            'Username': 'testuser',
            'UserAttributes': [
                {'Name': 'sub', 'Value': 'user-id-123'},
                {'Name': 'email', 'Value': 'test@example.com'}
            ]
        }
        mock_cognito.return_value = mock_cognito_client
        
        def validate_authorization(event):
            """Mock authorization validation"""
            auth_header = event.get('headers', {}).get('Authorization', '')
            
            if not auth_header.startswith('Bearer '):
                return {'isAuthorized': False, 'error': 'Invalid authorization header'}
            
            token = auth_header.replace('Bearer ', '')
            
            # Mock token validation
            if token == 'valid-token':
                return {
                    'isAuthorized': True,
                    'user': {
                        'sub': 'user-id-123',
                        'email': 'test@example.com'
                    }
                }
            else:
                return {'isAuthorized': False, 'error': 'Invalid token'}
        
        # Test valid token
        event_valid = {
            'headers': {'Authorization': 'Bearer valid-token'}
        }
        
        result_valid = validate_authorization(event_valid)
        assert result_valid['isAuthorized'] is True
        assert result_valid['user']['sub'] == 'user-id-123'
        
        # Test invalid token
        event_invalid = {
            'headers': {'Authorization': 'Bearer invalid-token'}
        }
        
        result_invalid = validate_authorization(event_invalid)
        assert result_invalid['isAuthorized'] is False
        
        # Test missing authorization header
        event_missing = {
            'headers': {}
        }
        
        result_missing = validate_authorization(event_missing)
        assert result_missing['isAuthorized'] is False


class TestAPIErrorHandling:
    """Test API error handling and edge cases"""
    
    def test_cors_headers(self):
        """Test CORS headers in API responses"""
        def add_cors_headers(response):
            """Mock CORS header addition"""
            if 'headers' not in response:
                response['headers'] = {}
            
            response['headers'].update({
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Max-Age': '86400'
            })
            
            return response
        
        # Test CORS headers are added
        response = {
            'statusCode': 200,
            'body': json.dumps({'message': 'success'})
        }
        
        response_with_cors = add_cors_headers(response)
        
        assert 'Access-Control-Allow-Origin' in response_with_cors['headers']
        assert response_with_cors['headers']['Access-Control-Allow-Origin'] == '*'
    
    def test_request_validation(self):
        """Test request validation"""
        def validate_request(event):
            """Mock request validation"""
            errors = []
            
            # Validate HTTP method
            allowed_methods = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
            if event.get('httpMethod') not in allowed_methods:
                errors.append('Invalid HTTP method')
            
            # Validate content type for POST/PUT
            if event.get('httpMethod') in ['POST', 'PUT']:
                content_type = event.get('headers', {}).get('Content-Type', '')
                if 'application/json' not in content_type:
                    errors.append('Content-Type must be application/json')
            
            # Validate request body size
            body = event.get('body', '')
            if len(body) > 1024 * 1024:  # 1MB limit
                errors.append('Request body too large')
            
            return {
                'isValid': len(errors) == 0,
                'errors': errors
            }
        
        # Test valid request
        valid_event = {
            'httpMethod': 'POST',
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'key': 'value'})
        }
        
        result = validate_request(valid_event)
        assert result['isValid'] is True
        assert len(result['errors']) == 0
        
        # Test invalid method
        invalid_method_event = {
            'httpMethod': 'PATCH',
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'key': 'value'})
        }
        
        result_invalid = validate_request(invalid_method_event)
        assert result_invalid['isValid'] is False
        assert 'Invalid HTTP method' in result_invalid['errors']
    
    def test_rate_limiting(self):
        """Test API rate limiting"""
        def check_rate_limit(client_id, endpoint):
            """Mock rate limiting check"""
            # Mock rate limit data structure
            rate_limits = {
                'client_123': {
                    '/devices/shadow': {'count': 5, 'window_start': 1640995200},
                    '/query/sql': {'count': 2, 'window_start': 1640995200}
                }
            }
            
            current_time = 1640995260  # 1 minute later
            window_duration = 60  # 1 minute window
            max_requests = 10
            
            if client_id not in rate_limits:
                rate_limits[client_id] = {}
            
            if endpoint not in rate_limits[client_id]:
                rate_limits[client_id][endpoint] = {'count': 0, 'window_start': current_time}
            
            client_data = rate_limits[client_id][endpoint]
            
            # Reset window if expired
            if current_time - client_data['window_start'] >= window_duration:
                client_data['count'] = 0
                client_data['window_start'] = current_time
            
            # Check if rate limit exceeded
            if client_data['count'] >= max_requests:
                return {
                    'allowed': False,
                    'retry_after': window_duration - (current_time - client_data['window_start'])
                }
            
            client_data['count'] += 1
            return {'allowed': True}
        
        # Test within rate limit
        result = check_rate_limit('client_123', '/devices/shadow')
        assert result['allowed'] is True
        
        # Test rate limit exceeded (would need to mock high count)
        # This is a simplified test of the rate limiting logic 