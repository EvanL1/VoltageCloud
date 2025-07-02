#!/usr/bin/env python3
"""
IoT 设备模拟器 - 发送模拟传感器数据到 AWS IoT Core
"""
import json
import time
import random
import ssl
import logging
from datetime import datetime
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IoTDeviceSimulator:
    def __init__(self, device_config_path="certificates/test-device-001-config.json"):
        """初始化 IoT 设备模拟器"""
        # 加载设备配置
        with open(device_config_path, 'r') as f:
            self.config = json.load(f)
            
        self.device_name = self.config['device_name']
        self.iot_endpoint = self.config['iot_endpoint']
        
        # 初始化 MQTT 客户端
        self.mqtt_client = AWSIoTMQTTClient(self.device_name)
        self.mqtt_client.configureEndpoint(self.iot_endpoint, 8883)
        
        # 配置证书
        cert_dir = "certificates"
        self.mqtt_client.configureCredentials(
            f"{cert_dir}/AmazonRootCA1.pem",
            f"{cert_dir}/{self.device_name}-private.pem.key",
            f"{cert_dir}/{self.device_name}-certificate.pem.crt"
        )
        
        # 配置连接参数
        self.mqtt_client.configureAutoReconnectBackoffTime(1, 32, 20)
        self.mqtt_client.configureOfflinePublishQueueing(-1)
        self.mqtt_client.configureDrainingFrequency(2)
        self.mqtt_client.configureConnectDisconnectTimeout(10)
        self.mqtt_client.configureMQTTOperationTimeout(5)
        
        # 主题配置
        self.telemetry_topic = f"device/{self.device_name}/telemetry"
        self.status_topic = f"device/{self.device_name}/status"
        
        logger.info(f"🔧 IoT 设备模拟器初始化完成: {self.device_name}")
        
    def connect(self):
        """连接到 AWS IoT Core"""
        try:
            self.mqtt_client.connect()
            logger.info(f"✅ 成功连接到 AWS IoT Core: {self.iot_endpoint}")
            return True
        except Exception as e:
            logger.error(f"❌ 连接失败: {str(e)}")
            return False
            
    def disconnect(self):
        """断开连接"""
        self.mqtt_client.disconnect()
        logger.info("🔌 已断开连接")
        
    def generate_sensor_data(self):
        """生成模拟传感器数据"""
        return {
            "deviceId": self.device_name,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "temperature": round(random.uniform(18.0, 35.0), 2),
                "humidity": round(random.uniform(30.0, 80.0), 2),
                "pressure": round(random.uniform(980.0, 1030.0), 2),
                "battery_level": round(random.uniform(10.0, 100.0), 2),
                "signal_strength": random.randint(-100, -30)
            },
            "location": {
                "lat": 40.7128 + random.uniform(-0.01, 0.01),
                "lon": -74.0060 + random.uniform(-0.01, 0.01)
            },
            "status": "online",
            "firmware_version": "1.0.0"
        }
        
    def send_telemetry(self, data):
        """发送遥测数据"""
        try:
            message = json.dumps(data, indent=2)
            self.mqtt_client.publish(self.telemetry_topic, message, 1)
            logger.info(f"📡 发送数据到 {self.telemetry_topic}")
            logger.info(f"📊 数据内容: {json.dumps(data['metrics'], indent=2)}")
            return True
        except Exception as e:
            logger.error(f"❌ 数据发送失败: {str(e)}")
            return False
            
    def send_status(self, status="online"):
        """发送设备状态"""
        status_data = {
            "deviceId": self.device_name,
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "uptime": random.randint(1000, 10000),
            "memory_usage": round(random.uniform(20.0, 80.0), 2)
        }
        
        try:
            message = json.dumps(status_data, indent=2)
            self.mqtt_client.publish(self.status_topic, message, 1)
            logger.info(f"📡 发送状态到 {self.status_topic}: {status}")
            return True
        except Exception as e:
            logger.error(f"❌ 状态发送失败: {str(e)}")
            return False
            
    def run_simulation(self, duration_seconds=300, interval_seconds=10):
        """运行模拟"""
        logger.info(f"🚀 开始设备模拟 - 持续 {duration_seconds} 秒，间隔 {interval_seconds} 秒")
        
        if not self.connect():
            return False
            
        try:
            # 发送初始状态
            self.send_status("online")
            
            start_time = time.time()
            message_count = 0
            
            while time.time() - start_time < duration_seconds:
                # 生成并发送传感器数据
                sensor_data = self.generate_sensor_data()
                if self.send_telemetry(sensor_data):
                    message_count += 1
                    
                # 偶尔发送状态更新
                if message_count % 5 == 0:
                    self.send_status("online")
                    
                logger.info(f"⏱️  已发送 {message_count} 条消息，剩余时间: {int(duration_seconds - (time.time() - start_time))} 秒")
                time.sleep(interval_seconds)
                
            # 发送离线状态
            self.send_status("offline")
            logger.info(f"✅ 模拟完成！总共发送了 {message_count} 条遥测消息")
            
        except KeyboardInterrupt:
            logger.info("⏹️  模拟被用户中断")
            self.send_status("offline")
        except Exception as e:
            logger.error(f"❌ 模拟过程中出错: {str(e)}")
        finally:
            self.disconnect()
            
        return True

if __name__ == "__main__":
    import sys
    
    # 解析命令行参数
    duration = 300  # 默认5分钟
    interval = 10   # 默认10秒间隔
    
    if len(sys.argv) > 1:
        duration = int(sys.argv[1])
    if len(sys.argv) > 2:
        interval = int(sys.argv[2])
        
    # 运行模拟器
    simulator = IoTDeviceSimulator()
    simulator.run_simulation(duration_seconds=duration, interval_seconds=interval)