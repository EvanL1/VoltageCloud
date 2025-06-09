#!/bin/bash
# IoT PoC Deployment Script

set -e

echo "🚀 Starting IoT PoC deployment..."

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Set default region if not set
export AWS_REGION=${AWS_REGION:-us-west-2}
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "📍 Deploying to region: $AWS_REGION"
echo "🏢 AWS Account: $AWS_ACCOUNT_ID"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# CDK bootstrap (if needed)
echo "🔧 Checking CDK bootstrap status..."
if ! cdk bootstrap aws://$AWS_ACCOUNT_ID/$AWS_REGION --quiet; then
    echo "⚠️  CDK bootstrap may have failed, but continuing..."
fi

# Deploy the stack
echo "🏗️  Deploying CDK stack..."
cdk deploy --require-approval never --outputs-file outputs.json

echo "✅ Deployment completed successfully!"
echo "📋 Stack outputs saved to outputs.json"

# Display important outputs
if [ -f outputs.json ]; then
    echo ""
    echo "📊 Key Resources:"
    echo "=================="
    cat outputs.json | jq -r '.IotPocStack | to_entries[] | "\(.key): \(.value)"'
fi

echo ""
echo "🔍 Next steps:"
echo "1. Check Kafka cluster status: ./scripts/check-kafka.sh"
echo "2. Test MQTT connection: ./scripts/test-mqtt.sh"
echo "3. Query TimeStream data: ./scripts/query-timestream.sh"
echo "4. Monitor Lambda logs: aws logs tail /aws/lambda/iot-poc-kafka-processor --follow"
echo ""
echo "⏳ Note: MSK cluster creation takes 10-15 minutes. Please wait for ACTIVE status before testing." 