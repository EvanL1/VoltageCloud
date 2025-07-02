import json
import boto3
import time
import os
from datetime import datetime

def lambda_handler(event, context):
    """处理IoT数据的Lambda函数"""
    
    print(f"收到事件: {json.dumps(event, indent=2)}")
    
    # 初始化客户端
    s3 = boto3.client('s3')
    
    # 从环境变量获取配置
    s3_bucket = os.environ.get('S3_BUCKET', 'iot-demo-data-lake-985539760410')
    timestream_db = os.environ.get('TIMESTREAM_DB', 'iot-demo_iot_db')
    timestream_table = os.environ.get('TIMESTREAM_TABLE', 'device_metrics')
    
    print(f"使用 S3 存储桶: {s3_bucket}")
    
    # 处理IoT消息
    device_id = event.get('deviceId', 'unknown')
    timestamp = str(int(time.time() * 1000))
    
    # 尝试写入TimeStream (预期会失败，但不应阻止S3写入)
    try:
        timestream = boto3.client('timestream-write')
        records = []
        for key, value in event.get('metrics', {}).items():
            records.append({
                'Time': timestamp,
                'TimeUnit': 'MILLISECONDS',
                'Dimensions': [
                    {'Name': 'deviceId', 'Value': device_id},
                    {'Name': 'metricType', 'Value': key}
                ],
                'MeasureName': 'value',
                'MeasureValue': str(value),
                'MeasureValueType': 'DOUBLE'
            })
        
        if records:
            timestream.write_records(
                DatabaseName=timestream_db,
                TableName=timestream_table,
                Records=records
            )
            print("✅ 数据成功写入 TimeStream")
    except Exception as e:
        print(f"⚠️ TimeStream 写入失败（预期）: {str(e)}")
    
    # 存储原始数据到S3
    try:
        now = datetime.now()
        key = f"raw-data/{device_id}/{now.strftime('%Y/%m/%d')}/{timestamp}.json"
        
        print(f"写入 S3: bucket={s3_bucket}, key={key}")
        
        response = s3.put_object(
            Bucket=s3_bucket,
            Key=key,
            Body=json.dumps(event, indent=2),
            ContentType='application/json'
        )
        
        print(f"✅ 数据成功写入 S3: {key}")
        print(f"S3 响应: {response.get('ETag', 'N/A')}")
        
    except Exception as e:
        print(f"❌ S3 写入失败: {str(e)}")
        raise e
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Data processed successfully',
            'device_id': device_id,
            's3_key': key,
            'timestamp': timestamp
        })
    }