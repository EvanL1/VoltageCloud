#!/usr/bin/env python3
"""
监控 IoT 数据流 - 检查 Lambda 日志和 S3 数据
"""
import boto3
import json
import time
from datetime import datetime, timedelta

class DataFlowMonitor:
    def __init__(self, region='us-east-1'):
        self.region = region
        self.logs = boto3.client('logs', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.iot = boto3.client('iot', region_name=region)
        
        # 配置信息
        self.lambda_log_group = '/aws/lambda/iot-demo-iot-data-processor'
        self.s3_bucket = 'iot-demo-data-lake-985539760410'
        self.device_name = 'test-device-001'
        
    def check_lambda_logs(self, minutes_back=10):
        """检查 Lambda 函数日志"""
        print(f"🔍 检查 Lambda 日志 (最近 {minutes_back} 分钟)")
        
        try:
            # 设置时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=minutes_back)
            
            # 获取日志事件
            response = self.logs.filter_log_events(
                logGroupName=self.lambda_log_group,
                startTime=int(start_time.timestamp() * 1000),
                endTime=int(end_time.timestamp() * 1000),
                filterPattern='[timestamp, requestId, level, ...]'
            )
            
            events = response.get('events', [])
            print(f"📊 找到 {len(events)} 条日志事件")
            
            # 显示最近的日志
            for event in events[-10:]:  # 显示最近10条
                timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                print(f"⏰ {timestamp}: {event['message']}")
                
            return len(events)
            
        except Exception as e:
            print(f"❌ 获取 Lambda 日志失败: {str(e)}")
            return 0
            
    def check_s3_data(self):
        """检查 S3 中的数据"""
        print(f"🗂️  检查 S3 存储桶: {self.s3_bucket}")
        
        try:
            # 列出最近的数据文件
            response = self.s3.list_objects_v2(
                Bucket=self.s3_bucket,
                Prefix=f'raw-data/{self.device_name}/',
                MaxKeys=10
            )
            
            objects = response.get('Contents', [])
            print(f"📁 找到 {len(objects)} 个数据文件")
            
            # 显示最近的文件
            for obj in sorted(objects, key=lambda x: x['LastModified'], reverse=True)[:5]:
                print(f"📄 {obj['Key']} - {obj['LastModified']} ({obj['Size']} bytes)")
                
                # 读取并显示文件内容
                try:
                    file_response = self.s3.get_object(Bucket=self.s3_bucket, Key=obj['Key'])
                    content = file_response['Body'].read().decode('utf-8')
                    data = json.loads(content)
                    
                    print(f"   📊 设备: {data.get('deviceId', 'unknown')}")
                    metrics = data.get('metrics', {})
                    print(f"   🌡️  温度: {metrics.get('temperature', 'N/A')}°C")
                    print(f"   💧 湿度: {metrics.get('humidity', 'N/A')}%")
                    print(f"   📊 气压: {metrics.get('pressure', 'N/A')} hPa")
                    print("   " + "-" * 40)
                    
                except Exception as e:
                    print(f"   ❌ 读取文件内容失败: {str(e)}")
                    
            return len(objects)
            
        except Exception as e:
            print(f"❌ 获取 S3 数据失败: {str(e)}")
            return 0
            
    def check_iot_metrics(self):
        """检查 IoT Core 指标"""
        print("📡 检查 IoT Core 连接状态")
        
        try:
            # 检查设备状态
            response = self.iot.describe_thing(thingName=self.device_name)
            print(f"✅ 设备 {self.device_name} 存在")
            print(f"   类型: {response.get('thingTypeName', 'N/A')}")
            
            attributes = response.get('attributes', {})
            for key, value in attributes.items():
                print(f"   {key}: {value}")
                
        except Exception as e:
            print(f"❌ 获取设备信息失败: {str(e)}")
            
    def monitor_realtime(self, duration_minutes=10, check_interval=30):
        """实时监控数据流"""
        print(f"🚀 开始实时监控 - 持续 {duration_minutes} 分钟，每 {check_interval} 秒检查一次")
        print("=" * 60)
        
        start_time = time.time()
        check_count = 0
        
        while time.time() - start_time < duration_minutes * 60:
            check_count += 1
            print(f"\n🔄 第 {check_count} 次检查 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
            print("-" * 50)
            
            # 检查各个组件
            self.check_iot_metrics()
            lambda_events = self.check_lambda_logs(minutes_back=2)
            s3_files = self.check_s3_data()
            
            # 总结
            print(f"\n📈 本次检查总结:")
            print(f"   Lambda 事件: {lambda_events}")
            print(f"   S3 文件: {s3_files}")
            
            if lambda_events > 0 and s3_files > 0:
                print("✅ 数据流正常运行！")
            elif lambda_events > 0:
                print("⚠️  Lambda 有活动，但 S3 可能还没有数据")
            else:
                print("⚠️  暂未检测到活动")
                
            print(f"\n⏱️  等待 {check_interval} 秒后进行下次检查...")
            time.sleep(check_interval)
            
        print(f"\n✅ 监控完成！总共进行了 {check_count} 次检查")

if __name__ == "__main__":
    monitor = DataFlowMonitor()
    
    # 先做一次初始检查
    print("🔍 初始状态检查")
    print("=" * 50)
    monitor.check_iot_metrics()
    monitor.check_lambda_logs(minutes_back=30)
    monitor.check_s3_data()
    
    print(f"\n{'='*60}")
    print("准备开始实时监控...")
    print("建议现在启动 IoT 设备模拟器！")
    print("命令: docker-compose up")
    print("=" * 60)
    
    # 等待用户确认
    input("按 Enter 键开始监控...")
    
    # 开始实时监控
    monitor.monitor_realtime(duration_minutes=15, check_interval=20)