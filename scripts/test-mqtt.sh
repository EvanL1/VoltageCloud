#!/bin/bash
# IoT PoC MQTT Testing Script

set -e

echo "🧪 Testing MQTT connectivity..."

# Get IoT endpoint
ENDPOINT=$(aws iot describe-endpoint --endpoint-type iot:Data-ATS --query 'endpointAddress' --output text)
echo "📡 IoT Endpoint: $ENDPOINT"

# Check if certificates exist
if [ ! -f "certs/device.crt" ] || [ ! -f "certs/device.key" ] || [ ! -f "certs/AmazonRootCA1.pem" ]; then
    echo "📄 Creating IoT certificates..."
    ./scripts/setup-certificates.sh
fi

# Generate test data
TIMESTAMP=$(date +%s)
DEVICE_ID="test-sensor-$(date +%s)"
TEMP=$(awk 'BEGIN {printf "%.1f", 20 + rand() * 15}')  # 20-35°C
HUMIDITY=$(awk 'BEGIN {printf "%.1f", 40 + rand() * 30}')  # 40-70%
VOLTAGE=$(awk 'BEGIN {printf "%.1f", 220 + rand() * 20}')  # 220-240V

TEST_MESSAGE=$(cat <<EOF
{
  "ts": ${TIMESTAMP}000,
  "temp": ${TEMP},
  "humidity": ${HUMIDITY},
  "voltage": ${VOLTAGE},
  "device_status": "online"
}
EOF
)

echo "📊 Test message:"
echo "$TEST_MESSAGE" | jq .

# Publish to MQTT
echo "📤 Publishing to MQTT topic: devices/${DEVICE_ID}/data"

if command -v mosquitto_pub > /dev/null; then
    mosquitto_pub \
        -h "$ENDPOINT" \
        -p 8883 \
        --cafile certs/AmazonRootCA1.pem \
        --cert certs/device.crt \
        --key certs/device.key \
        -t "devices/${DEVICE_ID}/data" \
        -m "$TEST_MESSAGE"
    
    echo "✅ Message published successfully!"
else
    echo "⚠️  mosquitto_pub not found. Installing..."
    
    # Try to install mosquitto clients
    if command -v brew > /dev/null; then
        brew install mosquitto
    elif command -v apt-get > /dev/null; then
        sudo apt-get update && sudo apt-get install -y mosquitto-clients
    elif command -v yum > /dev/null; then
        sudo yum install -y mosquitto
    else
        echo "❌ Please install mosquitto-clients manually"
        echo "   brew install mosquitto    # macOS"
        echo "   apt install mosquitto-clients    # Ubuntu/Debian"
        echo "   yum install mosquitto    # RHEL/CentOS"
        exit 1
    fi
    
    # Retry publishing
    mosquitto_pub \
        -h "$ENDPOINT" \
        -p 8883 \
        --cafile certs/AmazonRootCA1.pem \
        --cert certs/device.crt \
        --key certs/device.key \
        -t "devices/${DEVICE_ID}/data" \
        -m "$TEST_MESSAGE"
    
    echo "✅ Message published successfully!"
fi

echo ""
echo "🔍 Next steps:"
echo "1. Check Lambda logs: aws logs tail /aws/lambda/iot-poc-kafka-processor --since 1m --follow"
echo "2. Query TimeStream: ./scripts/query-timestream.sh"
echo "3. Check S3 data: aws s3 ls s3://\$(cat outputs.json | jq -r '.IotPocStack.S3BucketName')/raw/ --recursive"
echo "4. Check Kafka topic: ./scripts/check-kafka.sh" 