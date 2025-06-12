"""
IoT PoC Lambda Processor
Processes SQS messages and writes to TimeStream and S3
"""

import os
import json
import boto3
import time
import logging
from datetime import datetime
from typing import Dict, List, Any
from botocore.exceptions import ClientError


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
DB = os.environ["TDB"]
TBL = os.environ["TBL"]
BUCKET = os.environ["BUCKET"]
REGION = os.environ["REGION"]
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")

# Initialize AWS clients with explicit region
ts_client = boto3.client("timestream-write", region_name=REGION)
s3_client = boto3.client("s3", region_name=REGION)


def extract_device_id(payload: Dict[str, Any]) -> str:
    """
    Extract device ID from SQS message payload
    
    Args:
        payload: Message payload
        
    Returns:
        Device ID string
    """
    # Try to get device ID directly from payload
    if "device_id" in payload:
        return payload["device_id"]
    
    # Try to extract from source_topic if available (IoT topic format: devices/{device_id}/data)
    if "source_topic" in payload:
        topic_parts = payload["source_topic"].split("/")
        if len(topic_parts) >= 2:
            return topic_parts[1]  # devices/{device_id}/data
    
    # Fallback: use timestamp as device ID if not found
    return f"unknown_{int(time.time())}"


def create_timestream_records(device_id: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Create TimeStream records from IoT payload
    
    Args:
        device_id: Device identifier
        payload: IoT message payload
        
    Returns:
        List of TimeStream record dictionaries
    """
    records = []
    
    # Extract timestamp (use event_time if available, otherwise current time)
    timestamp = payload.get("event_time", payload.get("ts", int(time.time() * 1000)))
    
    # Convert to string if not already (TimeStream expects string)
    if isinstance(timestamp, (int, float)):
        timestamp_str = str(int(timestamp))
    else:
        timestamp_str = str(timestamp)
    
    # Remove metadata fields from metrics
    excluded_fields = {"ts", "event_time", "source_topic", "device_id"}
    
    for key, value in payload.items():
        if key not in excluded_fields and isinstance(value, (int, float)):
            record = {
                "Dimensions": [
                    {"Name": "deviceId", "Value": device_id},
                    {"Name": "metric", "Value": key}
                ],
                "MeasureName": "value",
                "MeasureValue": str(value),
                "MeasureValueType": "DOUBLE",
                "Time": timestamp_str,
                "TimeUnit": "MILLISECONDS"
            }
            records.append(record)
    
    return records


def save_to_s3(device_id: str, payload: Dict[str, Any]) -> bool:
    """
    Save raw message to S3
    
    Args:
        device_id: Device identifier
        payload: IoT message payload
        
    Returns:
        True if successful, False otherwise
    """
    try:
        timestamp = payload.get("event_time", payload.get("ts", int(time.time())))
        current_date = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e10 else timestamp)
        
        # Organize by date for better partitioning
        s3_key = f"raw/{device_id}/{current_date.strftime('%Y/%m/%d')}/{timestamp}.json"
        
        s3_client.put_object(
            Bucket=BUCKET,
            Key=s3_key,
            Body=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            ContentType="application/json"
        )
        
        logger.info(f"Saved raw data to S3: {s3_key}")
        return True
        
    except ClientError as e:
        logger.error(f"Failed to save to S3: {e}")
        return False


def write_to_timestream(records: List[Dict[str, Any]]) -> bool:
    """Write records to TimeStream in chunks of 100."""

    if not records:
        logger.info("No records to write to TimeStream")
        return True

    success = True
    chunk_size = 100

    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        try:
            ts_client.write_records(
                DatabaseName=DB,
                TableName=TBL,
                Records=chunk,
            )
            logger.info(f"Wrote {len(chunk)} records to TimeStream")
        except ClientError as e:
            logger.error(f"Failed to write records chunk starting at {i}: {e}")
            success = False

    if success:
        logger.info(f"Successfully wrote {len(records)} records to TimeStream")
    else:
        logger.error("One or more record batches failed to write to TimeStream")

    return success


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for processing SQS messages
    
    Args:
        event: SQS event containing records
        context: Lambda context
        
    Returns:
        Processing result with batch item failures
    """
    logger.info(f"Processing SQS event with {len(event.get('Records', []))} messages")
    
    successful_records = 0
    failed_records = []
    all_ts_records = []
    
    # Process each SQS message
    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")
        
        try:
            # Parse SQS message body
            body = record.get("body", "")
            if not body:
                logger.warning(f"Empty SQS message body for message {message_id}")
                failed_records.append({"itemIdentifier": message_id})
                continue
            
            # Parse JSON payload
            payload = json.loads(body)
            logger.info(f"Processing payload: {payload}")
            
            # Extract device ID from payload
            device_id = extract_device_id(payload)
            
            # Save raw data to S3
            s3_success = save_to_s3(device_id, payload)
            
            # Create TimeStream records
            ts_records = create_timestream_records(device_id, payload)
            all_ts_records.extend(ts_records)
            
            if s3_success:
                successful_records += 1
                logger.info(f"Successfully processed message {message_id} for device {device_id}")
            else:
                failed_records.append({"itemIdentifier": message_id})
                logger.error(f"Failed to save to S3 for message {message_id}")
                
        except Exception as e:
            logger.error(f"Failed to process SQS message {message_id}: {e}")
            failed_records.append({"itemIdentifier": message_id})
    
    # Batch write to TimeStream
    ts_success = write_to_timestream(all_ts_records)
    
    result = {
        "statusCode": 200,
        "successful_records": successful_records,
        "failed_records": len(failed_records),
        "timestream_records": len(all_ts_records),
        "timestream_success": ts_success,
        "sqs_queue_url": SQS_QUEUE_URL
    }
    
    # Add batch item failures for SQS partial batch failure handling
    if failed_records:
        result["batchItemFailures"] = failed_records
    
    logger.info(f"Processing completed: {result}")
    return result


#[cfg(test)]
def test_extract_device_id():
    """Test device ID extraction"""
    # Test with device_id in payload
    payload1 = {"device_id": "sensor01", "temp": 25.0}
    assert extract_device_id(payload1) == "sensor01"
    
    # Test with source_topic in payload
    payload2 = {"source_topic": "devices/sensor02/data", "temp": 25.0}
    assert extract_device_id(payload2) == "sensor02"
    
    # Test with unknown device
    payload3 = {"temp": 25.0}
    device_id = extract_device_id(payload3)
    assert device_id.startswith("unknown_")


def test_create_timestream_records():
    """Test TimeStream record creation"""
    payload = {
        "temp": 25.5,
        "humidity": 60.0,
        "ts": 1717910400,
        "source_topic": "devices/test/data",
        "device_id": "test_device"
    }
    
    records = create_timestream_records("test_device", payload)
    assert len(records) == 2  # temp and humidity
    assert records[0]["Dimensions"][0]["Value"] == "test_device"
    assert records[0]["MeasureValueType"] == "DOUBLE"


if __name__ == "__main__":
    # Run tests
    test_extract_device_id()
    test_create_timestream_records()
    print("All tests passed!") 