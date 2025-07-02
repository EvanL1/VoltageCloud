#!/usr/bin/env python3
"""
IoT Device Auto-Registration System
Automatically register devices to AWS IoT Core based on unique hardware identifiers
"""
import os
import json
import hashlib
import subprocess
import requests
import boto3
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DeviceAutoRegistration:
    def __init__(self, region='us-east-1', registration_endpoint=None):
        self.region = region
        self.registration_endpoint = registration_endpoint or "https://your-registration-api.amazonaws.com"
        self.device_id = None
        self.device_name = None
        self.cert_dir = "/opt/iot-device/certificates"
        
        # Ensure certificate directory exists
        os.makedirs(self.cert_dir, exist_ok=True)
        
    def get_hardware_id(self):
        """Generate absolutely unique 16-character device ID with multiple fallbacks"""
        import re
        
        # Priority 1: Hardware Serial Numbers
        try:
            # Motherboard serial
            result = subprocess.run(['sudo', 'dmidecode', '-s', 'baseboard-serial-number'], 
                                  capture_output=True, text=True)
            mb_serial = result.stdout.strip()
            if mb_serial and mb_serial not in ["Not Specified", "Not Available", ""]:
                device_id = hashlib.sha256(f"MB-{mb_serial}".encode()).hexdigest()[:16]
                logger.info(f"🔑 Device ID from motherboard serial: {device_id}")
                return device_id
                
            # System serial  
            result = subprocess.run(['sudo', 'dmidecode', '-s', 'system-serial-number'],
                                  capture_output=True, text=True)
            sys_serial = result.stdout.strip()
            if sys_serial and sys_serial not in ["Not Specified", "Not Available", ""]:
                device_id = hashlib.sha256(f"SYS-{sys_serial}".encode()).hexdigest()[:16]
                logger.info(f"🔑 Device ID from system serial: {device_id}")
                return device_id
        except Exception as e:
            logger.debug(f"DMI access failed: {e}")
        
        # Priority 2: CPU Information
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpu_info = f.read()
            # Extract CPU serial if available
            cpu_serial = re.search(r'Serial\s*:\s*([a-fA-F0-9]+)', cpu_info)
            if cpu_serial:
                device_id = hashlib.sha256(f"CPU-{cpu_serial.group(1)}".encode()).hexdigest()[:16]
                logger.info(f"🔑 Device ID from CPU serial: {device_id}")
                return device_id
        except Exception as e:
            logger.debug(f"CPU info access failed: {e}")
        
        # Priority 3: Machine ID (Linux standard)
        try:
            with open('/etc/machine-id', 'r') as f:
                machine_id = f.read().strip()
            if machine_id and len(machine_id) > 10:
                device_id = hashlib.sha256(f"MACHINE-{machine_id}".encode()).hexdigest()[:16]
                logger.info(f"🔑 Device ID from machine-id: {device_id}")
                return device_id
        except Exception as e:
            logger.debug(f"Machine ID access failed: {e}")
        
        # Priority 4: Disk UUID (first available disk)
        try:
            result = subprocess.run(['lsblk', '-no', 'UUID'], capture_output=True, text=True)
            disk_uuids = [uuid.strip() for uuid in result.stdout.split('\n') if uuid.strip()]
            if disk_uuids:
                device_id = hashlib.sha256(f"DISK-{disk_uuids[0]}".encode()).hexdigest()[:16]
                logger.info(f"🔑 Device ID from disk UUID: {device_id}")
                return device_id
        except Exception as e:
            logger.debug(f"Disk UUID access failed: {e}")
        
        # Priority 5: Network MAC (stable network interface)
        try:
            # Try multiple common interface names
            interfaces = ['eth0', 'enp0s3', 'ens33', 'wlan0']
            for iface in interfaces:
                try:
                    with open(f'/sys/class/net/{iface}/address', 'r') as f:
                        mac = f.read().strip()
                    if mac and mac != "00:00:00:00:00:00":
                        device_id = hashlib.sha256(f"MAC-{mac}".encode()).hexdigest()[:16]
                        logger.info(f"🔑 Device ID from MAC {iface}: {device_id}")
                        return device_id
                except:
                    continue
        except Exception as e:
            logger.debug(f"MAC address access failed: {e}")
        
        # Priority 6: Check for persistent device ID file
        try:
            if os.path.exists('/etc/device-id'):
                with open('/etc/device-id', 'r') as f:
                    stored_id = f.read().strip()
                if stored_id and len(stored_id) == 16:
                    logger.info(f"🔑 Device ID from stored file: {stored_id}")
                    return stored_id
        except Exception as e:
            logger.debug(f"Stored device ID access failed: {e}")
        
        # Final fallback: Generate and persist new ID
        logger.warning("⚠️  No hardware identifiers found, generating new device ID")
        import secrets
        fallback_id = hashlib.sha256(f"FALLBACK-{datetime.now().isoformat()}-{secrets.token_hex(8)}".encode()).hexdigest()[:16]
        
        # Try to save for future use
        try:
            with open('/etc/device-id', 'w') as f:
                f.write(fallback_id)
            os.chmod('/etc/device-id', 0o644)
            logger.info(f"🔑 Generated and saved new device ID: {fallback_id}")
        except:
            logger.warning("⚠️  Could not save device ID to /etc/device-id")
        
        return fallback_id
    
    def check_existing_certificates(self):
        """Check if certificates already exist locally"""
        cert_files = [
            f"{self.cert_dir}/{self.device_name}-certificate.pem.crt",
            f"{self.cert_dir}/{self.device_name}-private.pem.key",
            f"{self.cert_dir}/AmazonRootCA1.pem"
        ]
        
        all_exist = all(os.path.exists(f) for f in cert_files)
        
        if all_exist:
            logger.info("✅ Found existing certificate files, skipping registration")
            return True
        else:
            logger.info("🔍 No valid certificates found, registration required")
            return False
    
    def register_device_with_aws(self):
        """Register device through AWS API"""
        try:
            # Use boto3 to directly create device and certificates
            iot = boto3.client('iot', region_name=self.region)
            
            # 1. Create Thing Type (if not exists)
            try:
                iot.create_thing_type(
                    thingTypeName="auto-registered-device",
                    thingTypeDescription="Auto-registered IoT device"
                )
            except iot.exceptions.ResourceAlreadyExistsException:
                pass
            
            # 2. Create Thing
            try:
                thing_response = iot.create_thing(
                    thingName=self.device_name,
                    thingTypeName="auto-registered-device",
                    attributePayload={
                        'attributes': {
                            'deviceId': self.device_id,
                            'registrationTime': datetime.now().isoformat(),
                            'autoRegistered': 'true'
                        }
                    }
                )
                logger.info(f"✅ Thing created successfully: {thing_response['thingArn']}")
            except iot.exceptions.ResourceAlreadyExistsException:
                logger.info(f"ℹ️  Thing already exists: {self.device_name}")
            
            # 3. Create certificate
            cert_response = iot.create_keys_and_certificate(setAsActive=True)
            certificate_arn = cert_response['certificateArn']
            certificate_pem = cert_response['certificatePem']
            private_key = cert_response['keyPair']['PrivateKey']
            
            # 4. Create and attach policy
            policy_name = f"{self.device_name}-policy"
            policy_document = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:Connect"
                        ],
                        "Resource": f"arn:aws:iot:{self.region}:*:client/{self.device_name}"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:Publish"
                        ],
                        "Resource": f"arn:aws:iot:{self.region}:*:topic/device/{self.device_name}/*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:Subscribe",
                            "iot:Receive"
                        ],
                        "Resource": f"arn:aws:iot:{self.region}:*:topicfilter/device/{self.device_name}/*"
                    }
                ]
            }
            
            try:
                iot.create_policy(
                    policyName=policy_name,
                    policyDocument=json.dumps(policy_document)
                )
            except iot.exceptions.ResourceAlreadyExistsException:
                pass
            
            # 5. Attach policy to certificate
            iot.attach_policy(policyName=policy_name, target=certificate_arn)
            
            # 6. Attach certificate to Thing
            iot.attach_thing_principal(thingName=self.device_name, principal=certificate_arn)
            
            # 7. Get IoT endpoint
            endpoint_response = iot.describe_endpoint(endpointType='iot:Data-ATS')
            iot_endpoint = endpoint_response['endpointAddress']
            
            # 8. Save certificates and configuration
            self.save_certificates(certificate_pem, private_key, iot_endpoint)
            
            logger.info(f"🎉 Device registration successful: {self.device_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ AWS registration failed: {str(e)}")
            return False
    
    def save_certificates(self, certificate_pem, private_key, iot_endpoint):
        """Save certificate files"""
        try:
            # Save device certificate
            with open(f"{self.cert_dir}/{self.device_name}-certificate.pem.crt", "w") as f:
                f.write(certificate_pem)
            
            # Save private key
            with open(f"{self.cert_dir}/{self.device_name}-private.pem.key", "w") as f:
                f.write(private_key)
            
            # Download Amazon Root CA
            import urllib.request
            root_ca_url = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"
            urllib.request.urlretrieve(root_ca_url, f"{self.cert_dir}/AmazonRootCA1.pem")
            
            # Save device configuration
            config = {
                "device_id": self.device_id,
                "device_name": self.device_name,
                "iot_endpoint": iot_endpoint,
                "region": self.region,
                "registration_time": datetime.now().isoformat(),
                "auto_registered": True
            }
            
            with open(f"{self.cert_dir}/device-config.json", "w") as f:
                json.dump(config, f, indent=2)
            
            # Set file permissions
            os.chmod(f"{self.cert_dir}/{self.device_name}-private.pem.key", 0o600)
            
            logger.info(f"✅ Certificate files saved to: {self.cert_dir}")
            
        except Exception as e:
            logger.error(f"❌ Certificate save failed: {str(e)}")
    
    def run_auto_registration(self):
        """Execute auto-registration flow"""
        logger.info("🚀 Starting device auto-registration process")
        
        # 1. Get device hardware ID
        self.device_id = self.get_hardware_id()
        self.device_name = f"auto-device-{self.device_id}"
        
        logger.info(f"📱 Device name: {self.device_name}")
        
        # 2. Check existing certificates
        if self.check_existing_certificates():
            logger.info("✅ Device already registered, no need to re-register")
            return True
        
        # 3. Execute registration
        if self.register_device_with_aws():
            logger.info("🎉 Auto-registration completed!")
            return True
        else:
            logger.error("❌ Auto-registration failed")
            return False

if __name__ == "__main__":
    registration = DeviceAutoRegistration()
    success = registration.run_auto_registration()
    
    if success:
        print("✅ Device auto-registration successful! Ready to send data")
    else:
        print("❌ Device registration failed, please check network and AWS credentials")
        exit(1)