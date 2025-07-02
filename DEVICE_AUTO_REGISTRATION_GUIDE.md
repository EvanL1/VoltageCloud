# Device Auto-Registration System Guide

## Overview

This guide explains how to implement automatic device registration for IoT devices connecting to AWS IoT Core. The system generates a unique 16-character device ID based on hardware characteristics and automatically registers the device with AWS.

## Device ID Generation

### Format
- **Length**: 16 hexadecimal characters (0-9, a-f)
- **Example**: `8f2a1b3c4d5e6789`
- **Uniqueness**: 2^64 possible combinations

### Multi-Tier Fallback Strategy

The system attempts to generate device IDs using the following priority order:

#### Priority 1: Hardware Serial Numbers (Most Stable)
```bash
# Motherboard serial number
sudo dmidecode -s baseboard-serial-number

# System serial number
sudo dmidecode -s system-serial-number
```

#### Priority 2: CPU Information
```bash
# Extract CPU serial from /proc/cpuinfo
grep -i serial /proc/cpuinfo
```

#### Priority 3: Machine ID (Linux Standard)
```bash
# Persistent system identifier
cat /etc/machine-id
```

#### Priority 4: Disk UUID
```bash
# First available disk UUID
lsblk -no UUID | head -1
```

#### Priority 5: Network MAC Address
```bash
# Try common interface names: eth0, enp0s3, ens33, wlan0
cat /sys/class/net/eth0/address
```

#### Priority 6: Persistent Device ID File
```bash
# Previously saved device ID
cat /etc/device-id
```

#### Priority 7: Random Generation (Last Resort)
- Generates cryptographically secure random ID
- Saves to `/etc/device-id` for future use

## Auto-Registration Flow

### 1. Device Startup
```
Hardware Detection → ID Generation → Device Name Creation
```

### 2. Certificate Check
```
Check Local Certs → If Missing → Trigger Registration
```

### 3. AWS Registration
```
Create Thing → Generate Certificate → Create Policy → Attach Resources
```

### 4. Certificate Management
```
Save Certificates → Set Permissions → Download Root CA → Create Config
```

## Implementation

### Required Dependencies
```bash
pip install boto3 AWSIoTPythonSDK
```

### Basic Usage
```python
from device_auto_registration import DeviceAutoRegistration

# Initialize registration system
registration = DeviceAutoRegistration(region='us-east-1')

# Execute auto-registration
success = registration.run_auto_registration()

if success:
    print("Device registered successfully!")
else:
    print("Registration failed")
```

### Command Line Usage
```bash
# Run auto-registration
python device_auto_registration.py

# Check generated configuration
cat /opt/iot-device/certificates/device-config.json
```

## Security Features

### Certificate Management
- Private keys stored with 600 permissions
- Automatic Amazon Root CA download
- Certificate validation and error handling

### IAM Policy (Device-Specific)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["iot:Connect"],
      "Resource": "arn:aws:iot:region:account:client/device-name"
    },
    {
      "Effect": "Allow", 
      "Action": ["iot:Publish"],
      "Resource": "arn:aws:iot:region:account:topic/device/device-name/*"
    },
    {
      "Effect": "Allow",
      "Action": ["iot:Subscribe", "iot:Receive"],
      "Resource": "arn:aws:iot:region:account:topicfilter/device/device-name/*"
    }
  ]
}
```

### Security Considerations
- **Hardware Binding**: IDs based on immutable hardware characteristics
- **Collision Resistance**: SHA-256 hashing prevents ID collisions  
- **Access Control**: Device-specific policies limit topic access
- **Certificate Rotation**: Support for certificate renewal
- **Audit Trail**: Comprehensive logging of registration process

## File Structure

### Certificate Directory: `/opt/iot-device/certificates/`
```
├── auto-device-{id}-certificate.pem.crt    # Device certificate
├── auto-device-{id}-private.pem.key        # Private key (600 permissions)
├── AmazonRootCA1.pem                       # AWS root certificate
└── device-config.json                     # Device configuration
```

### Configuration File Format
```json
{
  "device_id": "8f2a1b3c4d5e6789",
  "device_name": "auto-device-8f2a1b3c4d5e6789",
  "iot_endpoint": "xxxxx.iot.us-east-1.amazonaws.com",
  "region": "us-east-1",
  "registration_time": "2025-07-02T10:30:00",
  "auto_registered": true
}
```

## Deployment Options

### Option 1: Systemd Service (Auto-start)
```ini
[Unit]
Description=IoT Device Auto Registration
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/iot-device/device_auto_registration.py
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

### Option 2: Docker Container
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install boto3 AWSIoTPythonSDK
COPY device_auto_registration.py .
CMD ["python", "device_auto_registration.py"]
```

### Option 3: Cron Job (Periodic Check)
```bash
# Run registration check every hour
0 * * * * /usr/bin/python3 /opt/iot-device/device_auto_registration.py
```

## Troubleshooting

### Common Issues

#### 1. Permission Denied (DMI Access)
```bash
# Solution: Run with sudo or add user to appropriate group
sudo usermod -a -G dialout $USER
```

#### 2. No Hardware Identifiers Found
```bash
# Check available hardware info
sudo dmidecode -t system
cat /proc/cpuinfo
```

#### 3. AWS Credentials Missing
```bash
# Configure AWS credentials
aws configure
# or set environment variables
export AWS_ACCESS_KEY_ID=xxx
export AWS_SECRET_ACCESS_KEY=xxx
```

#### 4. Certificate Directory Permissions
```bash
# Fix certificate directory permissions
sudo chown -R iot-user:iot-user /opt/iot-device
sudo chmod 700 /opt/iot-device/certificates
```

### Logging and Debugging

#### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### Check Registration Status
```bash
# Verify certificates exist
ls -la /opt/iot-device/certificates/

# Test IoT connection
aws iot describe-endpoint --endpoint-type iot:Data-ATS
```

## Production Considerations

### Scale Deployment
- Pre-provision device IDs in manufacturing
- Implement bulk registration APIs
- Use AWS IoT Device Management for fleet operations

### Monitoring
- CloudWatch metrics for registration success rates
- Device connectivity monitoring
- Certificate expiration alerts

### Backup and Recovery
- Backup certificate files securely
- Implement certificate rotation procedures
- Plan for device re-registration scenarios

## Integration with Existing Systems

### Manufacturing Integration
```python
# Generate device ID during manufacturing
device_id = registration.get_hardware_id()
print(f"Device ID for QR code: {device_id}")

# Pre-register device in backend systems
register_device_in_manufacturing_db(device_id)
```

### Fleet Management
```python
# Batch device registration
def register_device_fleet(device_ids):
    for device_id in device_ids:
        registration = DeviceAutoRegistration()
        registration.device_id = device_id
        registration.run_auto_registration()
```

## Best Practices

1. **Test on Target Hardware**: Verify ID generation works on production hardware
2. **Secure Storage**: Protect private keys and configuration files
3. **Network Security**: Use VPN or secure networks for registration
4. **Certificate Management**: Implement automatic certificate renewal
5. **Monitoring**: Track device registration and connection status
6. **Documentation**: Maintain device ID mapping and registration logs

## Support and Maintenance

### Regular Tasks
- Monitor certificate expiration dates
- Update AWS root certificates when needed
- Review and update IAM policies
- Check device connectivity status

### Upgrades
- Test new versions on development devices first
- Plan for certificate migration during updates
- Maintain backward compatibility for existing devices

This system provides a robust, secure, and scalable solution for automatic IoT device registration based on unique hardware identifiers.