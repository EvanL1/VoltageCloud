#!/bin/bash
# IoT PoC Certificate Setup Script

set -e

echo "🔐 Setting up IoT device certificates..."

# Create certs directory
mkdir -p certs

# Download Amazon Root CA certificate
if [ ! -f "certs/AmazonRootCA1.pem" ]; then
    echo "📥 Downloading Amazon Root CA certificate..."
    curl -s https://www.amazontrust.com/repository/AmazonRootCA1.pem -o certs/AmazonRootCA1.pem
fi

# Check if device certificate already exists
if [ -f "certs/device.crt" ] && [ -f "certs/device.key" ]; then
    echo "✅ Device certificates already exist"
    exit 0
fi

# Create a new IoT thing and certificate
THING_NAME="iot-poc-device-$(date +%s)"
echo "🏷️  Creating IoT thing: $THING_NAME"

# Create the thing
aws iot create-thing --thing-name "$THING_NAME" > /dev/null

# Create certificate and keys
CERT_RESPONSE=$(aws iot create-keys-and-certificate --set-as-active --output json)
CERT_ARN=$(echo "$CERT_RESPONSE" | jq -r '.certificateArn')
CERT_ID=$(echo "$CERT_RESPONSE" | jq -r '.certificateId')

# Save certificate and key files
echo "$CERT_RESPONSE" | jq -r '.certificatePem' > certs/device.crt
echo "$CERT_RESPONSE" | jq -r '.keyPair.PrivateKey' > certs/device.key

# Create and attach a policy
POLICY_NAME="iot-poc-device-policy"
POLICY_DOCUMENT=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iot:Connect",
        "iot:Publish"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)

# Create policy (ignore error if already exists)
echo "📋 Creating IoT policy: $POLICY_NAME"
aws iot create-policy --policy-name "$POLICY_NAME" --policy-document "$POLICY_DOCUMENT" 2>/dev/null || true

# Attach policy to certificate
echo "🔗 Attaching policy to certificate..."
aws iot attach-policy --policy-name "$POLICY_NAME" --target "$CERT_ARN"

# Attach certificate to thing
echo "🔗 Attaching certificate to thing..."
aws iot attach-thing-principal --thing-name "$THING_NAME" --principal "$CERT_ARN"

# Save thing info
echo "$THING_NAME" > certs/thing-name.txt
echo "$CERT_ARN" > certs/cert-arn.txt

echo "✅ IoT certificates setup completed!"
echo "📄 Files created:"
echo "   - certs/device.crt (Device certificate)"
echo "   - certs/device.key (Private key)"
echo "   - certs/AmazonRootCA1.pem (Root CA)"
echo "   - certs/thing-name.txt (Thing name: $THING_NAME)"
echo "   - certs/cert-arn.txt (Certificate ARN)" 