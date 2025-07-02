#!/usr/bin/env python3
"""
创建 IoT 测试设备和证书
"""
import boto3
import json
import os
from datetime import datetime

class IoTDeviceCreator:
    def __init__(self, region='us-east-1'):
        self.region = region
        self.iot = boto3.client('iot', region_name=region)
        self.sts = boto3.client('sts', region_name=region)
        
        # 获取账户ID
        identity = self.sts.get_caller_identity()
        self.account_id = identity['Account']
        
    def create_test_device(self, device_name="test-device-001"):
        """创建测试设备"""
        print(f"🔧 开始创建测试设备: {device_name}")
        
        try:
            # 1. 创建 Thing
            thing_response = self.iot.create_thing(
                thingName=device_name,
                thingTypeName="iot-demo-device-type",
                attributePayload={
                    'attributes': {
                        'deviceType': 'sensor',
                        'location': 'test-lab',
                        'firmware': '1.0.0'
                    }
                }
            )
            print(f"✅ Thing 创建成功: {thing_response['thingArn']}")
            
            # 2. 创建密钥和证书
            cert_response = self.iot.create_keys_and_certificate(setAsActive=True)
            certificate_arn = cert_response['certificateArn']
            certificate_id = cert_response['certificateId']
            certificate_pem = cert_response['certificatePem']
            private_key = cert_response['keyPair']['PrivateKey']
            public_key = cert_response['keyPair']['PublicKey']
            
            print(f"✅ 证书创建成功: {certificate_id}")
            
            # 3. 附加策略到证书
            policy_name = "iot-demo-device-policy"
            self.iot.attach_policy(
                policyName=policy_name,
                target=certificate_arn
            )
            print(f"✅ 策略附加成功: {policy_name}")
            
            # 4. 附加证书到 Thing
            self.iot.attach_thing_principal(
                thingName=device_name,
                principal=certificate_arn
            )
            print(f"✅ 证书附加到设备成功")
            
            # 5. 获取 IoT 端点
            endpoint_response = self.iot.describe_endpoint(endpointType='iot:Data-ATS')
            iot_endpoint = endpoint_response['endpointAddress']
            print(f"✅ IoT 端点获取成功: {iot_endpoint}")
            
            # 6. 保存证书和配置文件
            cert_dir = "certificates"
            os.makedirs(cert_dir, exist_ok=True)
            
            # 保存证书文件
            with open(f"{cert_dir}/{device_name}-certificate.pem.crt", "w") as f:
                f.write(certificate_pem)
                
            with open(f"{cert_dir}/{device_name}-private.pem.key", "w") as f:
                f.write(private_key)
                
            with open(f"{cert_dir}/{device_name}-public.pem.key", "w") as f:
                f.write(public_key)
            
            # 下载 Amazon Root CA 1
            import urllib.request
            root_ca_url = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"
            urllib.request.urlretrieve(root_ca_url, f"{cert_dir}/AmazonRootCA1.pem")
            
            # 保存设备配置
            device_config = {
                "device_name": device_name,
                "thing_arn": thing_response['thingArn'],
                "certificate_arn": certificate_arn,
                "certificate_id": certificate_id,
                "iot_endpoint": iot_endpoint,
                "region": self.region,
                "policy_name": policy_name,
                "created_at": datetime.now().isoformat()
            }
            
            with open(f"{cert_dir}/{device_name}-config.json", "w") as f:
                json.dump(device_config, f, indent=2)
                
            print(f"✅ 证书和配置文件保存在 {cert_dir}/ 目录")
            
            return device_config
            
        except Exception as e:
            print(f"❌ 创建设备失败: {str(e)}")
            return None

if __name__ == "__main__":
    creator = IoTDeviceCreator()
    config = creator.create_test_device()
    
    if config:
        print(f"\n🎉 测试设备创建完成!")
        print(f"设备名称: {config['device_name']}")
        print(f"IoT 端点: {config['iot_endpoint']}")
        print(f"证书 ID: {config['certificate_id']}")