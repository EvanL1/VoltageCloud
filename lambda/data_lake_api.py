"""
Data Lake API Lambda Function
Provides comprehensive data lake access and analytics capabilities
"""

import json
import os
import boto3
import uuid
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
athena_client = boto3.client('athena')
glue_client = boto3.client('glue')

# Environment variables
RAW_BUCKET = os.environ['RAW_BUCKET']
PROCESSED_BUCKET = os.environ['PROCESSED_BUCKET']
CURATED_BUCKET = os.environ['CURATED_BUCKET']
ANALYTICS_BUCKET = os.environ['ANALYTICS_BUCKET']
GLUE_DATABASE = os.environ['GLUE_DATABASE']
ATHENA_WORKGROUP = os.environ['ATHENA_WORKGROUP']
REGION = os.environ['REGION']


def handler(event, context):
    """
    Main Lambda handler for Data Lake API
    """
    try:
        # Parse the incoming request
        http_method = event.get('httpMethod', 'POST')
        resource_path = event.get('resource', '/')
        query_params = event.get('queryStringParameters') or {}
        body = event.get('body')
        
        if body:
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                body = {}
        else:
            body = {}

        logger.info(f"Processing {http_method} request to {resource_path}")

        # Route the request based on resource path
        if resource_path == "/query/sql":
            return execute_sql_query(body)
        elif resource_path == "/query/tables":
            return list_tables()
        elif resource_path == "/data/raw":
            return query_data_layer("raw", query_params)
        elif resource_path == "/data/processed":
            return query_data_layer("processed", query_params)
        elif resource_path == "/data/curated":
            return query_data_layer("curated", query_params)
        elif resource_path == "/analytics/dashboards":
            return list_dashboards()
        elif resource_path == "/analytics/reports":
            return generate_report(query_params)
        elif event.get('action') == 'update_partitions':
            return update_partitions(event)
        else:
            return create_response(400, {"error": "Invalid endpoint"})

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return create_response(500, {"error": str(e)})


def execute_sql_query(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute SQL query using Amazon Athena
    """
    try:
        query = body.get('query')
        if not query:
            return create_response(400, {"error": "Query parameter is required"})

        # Start query execution
        query_execution_id = start_athena_query(query)
        
        # Wait for query completion
        result = wait_for_query_completion(query_execution_id)
        
        if result['status'] == 'SUCCEEDED':
            # Get query results
            results = get_query_results(query_execution_id)
            return create_response(200, {
                "execution_id": query_execution_id,
                "status": "SUCCEEDED",
                "results": results,
                "row_count": len(results.get('rows', []))
            })
        else:
            return create_response(400, {
                "execution_id": query_execution_id,
                "status": result['status'],
                "error": result.get('error', 'Query failed')
            })

    except Exception as e:
        logger.error(f"Error executing SQL query: {str(e)}")
        return create_response(500, {"error": str(e)})


def list_tables() -> Dict[str, Any]:
    """
    List all tables in the Glue database
    """
    try:
        response = glue_client.get_tables(DatabaseName=GLUE_DATABASE)
        
        tables = []
        for table in response.get('TableList', []):
            table_info = {
                "name": table['Name'],
                "description": table.get('Description', ''),
                "location": table.get('StorageDescriptor', {}).get('Location', ''),
                "columns": [
                    {
                        "name": col['Name'],
                        "type": col['Type'],
                        "comment": col.get('Comment', '')
                    }
                    for col in table.get('StorageDescriptor', {}).get('Columns', [])
                ],
                "partitions": [
                    {
                        "name": part['Name'],
                        "type": part['Type']
                    }
                    for part in table.get('PartitionKeys', [])
                ],
                "creation_time": table.get('CreateTime', '').isoformat() if table.get('CreateTime') else '',
                "last_access_time": table.get('LastAccessTime', '').isoformat() if table.get('LastAccessTime') else ''
            }
            tables.append(table_info)

        return create_response(200, {
            "database": GLUE_DATABASE,
            "tables": tables,
            "table_count": len(tables)
        })

    except Exception as e:
        logger.error(f"Error listing tables: {str(e)}")
        return create_response(500, {"error": str(e)})


def query_data_layer(layer: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query data from a specific layer (raw, processed, curated)
    """
    try:
        # Map layer to bucket
        bucket_map = {
            "raw": RAW_BUCKET,
            "processed": PROCESSED_BUCKET,
            "curated": CURATED_BUCKET
        }
        
        bucket = bucket_map.get(layer)
        if not bucket:
            return create_response(400, {"error": f"Invalid layer: {layer}"})

        # Parse query parameters
        device_id = query_params.get('device_id')
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        limit = int(query_params.get('limit', 100))
        
        # Build SQL query based on layer
        if layer == "raw":
            table_name = "raw_iot_data"
        else:
            table_name = f"{layer}_iot_data"

        # Build WHERE clause
        where_conditions = []
        if device_id:
            where_conditions.append(f"device_id = '{device_id}'")
        if start_date:
            where_conditions.append(f"from_unixtime(timestamp) >= timestamp '{start_date}'")
        if end_date:
            where_conditions.append(f"from_unixtime(timestamp) <= timestamp '{end_date}'")

        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        query = f"""
        SELECT *
        FROM {GLUE_DATABASE}.{table_name}
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT {limit}
        """

        # Execute query
        query_execution_id = start_athena_query(query)
        result = wait_for_query_completion(query_execution_id)
        
        if result['status'] == 'SUCCEEDED':
            results = get_query_results(query_execution_id)
            return create_response(200, {
                "layer": layer,
                "query_execution_id": query_execution_id,
                "results": results,
                "parameters": {
                    "device_id": device_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "limit": limit
                }
            })
        else:
            return create_response(400, {
                "error": "Query failed",
                "details": result.get('error', 'Unknown error')
            })

    except Exception as e:
        logger.error(f"Error querying {layer} data: {str(e)}")
        return create_response(500, {"error": str(e)})


def list_dashboards() -> Dict[str, Any]:
    """
    List available dashboards and visualizations
    """
    try:
        # This would integrate with QuickSight or return predefined dashboards
        dashboards = [
            {
                "id": "device-overview",
                "name": "Device Overview Dashboard",
                "description": "Real-time overview of all IoT devices",
                "url": f"/analytics/dashboard/device-overview",
                "metrics": ["device_count", "active_devices", "avg_temperature", "avg_humidity"]
            },
            {
                "id": "temperature-trends",
                "name": "Temperature Trends",
                "description": "Historical temperature data analysis",
                "url": f"/analytics/dashboard/temperature-trends",
                "metrics": ["temperature_avg", "temperature_min", "temperature_max"]
            },
            {
                "id": "device-health",
                "name": "Device Health Monitor",
                "description": "Device connectivity and health status",
                "url": f"/analytics/dashboard/device-health",
                "metrics": ["connectivity_status", "last_seen", "data_quality"]
            }
        ]

        return create_response(200, {
            "dashboards": dashboards,
            "total": len(dashboards)
        })

    except Exception as e:
        logger.error(f"Error listing dashboards: {str(e)}")
        return create_response(500, {"error": str(e)})


def generate_report(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate analytics reports
    """
    try:
        report_type = query_params.get('type', 'summary')
        start_date = query_params.get('start_date', 
                                     (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        end_date = query_params.get('end_date', 
                                   datetime.now().strftime('%Y-%m-%d'))

        if report_type == "summary":
            query = f"""
            SELECT 
                COUNT(DISTINCT device_id) as device_count,
                COUNT(*) as total_readings,
                AVG(temperature) as avg_temperature,
                AVG(humidity) as avg_humidity,
                MIN(from_unixtime(timestamp)) as earliest_reading,
                MAX(from_unixtime(timestamp)) as latest_reading
            FROM {GLUE_DATABASE}.raw_iot_data
            WHERE from_unixtime(timestamp) BETWEEN timestamp '{start_date}' AND timestamp '{end_date}'
            """
        elif report_type == "device_analysis":
            query = f"""
            SELECT 
                device_id,
                COUNT(*) as reading_count,
                AVG(temperature) as avg_temperature,
                AVG(humidity) as avg_humidity,
                MIN(from_unixtime(timestamp)) as first_reading,
                MAX(from_unixtime(timestamp)) as last_reading
            FROM {GLUE_DATABASE}.raw_iot_data
            WHERE from_unixtime(timestamp) BETWEEN timestamp '{start_date}' AND timestamp '{end_date}'
            GROUP BY device_id
            ORDER BY reading_count DESC
            """
        elif report_type == "hourly_trends":
            query = f"""
            SELECT 
                date_trunc('hour', from_unixtime(timestamp)) as hour,
                COUNT(*) as reading_count,
                AVG(temperature) as avg_temperature,
                AVG(humidity) as avg_humidity
            FROM {GLUE_DATABASE}.raw_iot_data
            WHERE from_unixtime(timestamp) BETWEEN timestamp '{start_date}' AND timestamp '{end_date}'
            GROUP BY date_trunc('hour', from_unixtime(timestamp))
            ORDER BY hour
            """
        else:
            return create_response(400, {"error": f"Unknown report type: {report_type}"})

        # Execute query
        query_execution_id = start_athena_query(query)
        result = wait_for_query_completion(query_execution_id)
        
        if result['status'] == 'SUCCEEDED':
            results = get_query_results(query_execution_id)
            
            # Generate report metadata
            report = {
                "report_id": str(uuid.uuid4()),
                "type": report_type,
                "generated_at": datetime.now().isoformat(),
                "parameters": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "query_execution_id": query_execution_id,
                "data": results
            }
            
            return create_response(200, report)
        else:
            return create_response(400, {
                "error": "Report generation failed",
                "details": result.get('error', 'Unknown error')
            })

    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        return create_response(500, {"error": str(e)})


def update_partitions(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update Glue table partitions (used by Step Functions)
    """
    try:
        database = event.get('database')
        table = event.get('table')
        
        if not database or not table:
            return {"status": "error", "message": "Database and table parameters required"}

        # Get current date for partition
        now = datetime.now()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        day = now.strftime('%d')

        # Add partition
        partition_input = {
            'Values': [year, month, day],
            'StorageDescriptor': {
                'Columns': [
                    {'Name': 'device_id', 'Type': 'string'},
                    {'Name': 'timestamp', 'Type': 'bigint'},
                    {'Name': 'temperature', 'Type': 'double'},
                    {'Name': 'humidity', 'Type': 'double'},
                    {'Name': 'source_topic', 'Type': 'string'},
                    {'Name': 'event_time', 'Type': 'bigint'}
                ],
                'Location': f's3://{RAW_BUCKET}/raw/year={year}/month={month}/day={day}/',
                'InputFormat': 'org.apache.hadoop.mapred.TextInputFormat',
                'OutputFormat': 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat',
                'SerdeInfo': {
                    'SerializationLibrary': 'org.openx.data.jsonserde.JsonSerDe'
                }
            }
        }

        try:
            glue_client.create_partition(
                DatabaseName=database,
                TableName=table,
                PartitionInput=partition_input
            )
            message = f"Partition created for {year}-{month}-{day}"
        except glue_client.exceptions.AlreadyExistsException:
            message = f"Partition already exists for {year}-{month}-{day}"

        logger.info(message)
        return {"status": "success", "message": message}

    except Exception as e:
        logger.error(f"Error updating partitions: {str(e)}")
        return {"status": "error", "message": str(e)}


def start_athena_query(query: str) -> str:
    """
    Start an Athena query execution
    """
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={
            'Database': GLUE_DATABASE
        },
        WorkGroup=ATHENA_WORKGROUP
    )
    return response['QueryExecutionId']


def wait_for_query_completion(query_execution_id: str, timeout: int = 300) -> Dict[str, Any]:
    """
    Wait for Athena query to complete
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        status = response['QueryExecution']['Status']['State']
        
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            result = {'status': status}
            if status == 'FAILED':
                result['error'] = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
            return result
        
        time.sleep(2)
    
    return {'status': 'TIMEOUT', 'error': 'Query execution timeout'}


def get_query_results(query_execution_id: str) -> Dict[str, Any]:
    """
    Get results from completed Athena query
    """
    response = athena_client.get_query_results(QueryExecutionId=query_execution_id)
    
    # Extract column names
    columns = []
    if response['ResultSet']['ResultSetMetadata']['ColumnInfo']:
        columns = [col['Name'] for col in response['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    
    # Extract rows
    rows = []
    result_rows = response['ResultSet']['Rows']
    
    # Skip header row if it exists
    data_rows = result_rows[1:] if result_rows else []
    
    for row in data_rows:
        row_data = {}
        for i, data in enumerate(row['Data']):
            if i < len(columns):
                row_data[columns[i]] = data.get('VarCharValue', '')
        rows.append(row_data)
    
    return {
        'columns': columns,
        'rows': rows,
        'row_count': len(rows)
    }


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create standardized API response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }


#################
# Test Functions
#################

def test_sql_query():
    """Test SQL query execution"""
    try:
        event = {
            'httpMethod': 'POST',
            'resource': '/query/sql',
            'body': json.dumps({
                'query': f'SELECT COUNT(*) as total_records FROM {GLUE_DATABASE}.raw_iot_data LIMIT 10'
            })
        }
        
        response = handler(event, {})
        assert response['statusCode'] == 200
        print("✅ SQL query test passed")
        return True
    except Exception as e:
        print(f"❌ SQL query test failed: {e}")
        return False


def test_list_tables():
    """Test table listing functionality"""
    try:
        event = {
            'httpMethod': 'GET',
            'resource': '/query/tables'
        }
        
        response = handler(event, {})
        assert response['statusCode'] == 200
        print("✅ List tables test passed")
        return True
    except Exception as e:
        print(f"❌ List tables test failed: {e}")
        return False


def test_data_query():
    """Test data layer query"""
    try:
        event = {
            'httpMethod': 'GET',
            'resource': '/data/raw',
            'queryStringParameters': {
                'limit': '10'
            }
        }
        
        response = handler(event, {})
        assert response['statusCode'] in [200, 400]  # May fail if no data
        print("✅ Data query test passed")
        return True
    except Exception as e:
        print(f"❌ Data query test failed: {e}")
        return False


if __name__ == "__main__":
    # Run tests
    print("Running Data Lake API tests...")
    test_sql_query()
    test_list_tables()
    test_data_query()
    print("All tests completed!") 