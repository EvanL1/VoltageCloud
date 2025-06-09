#!/bin/bash
# IoT PoC Cleanup Script

set -e

echo "🧹 Starting IoT PoC cleanup..."

# Confirm before destroying
read -p "⚠️  This will destroy ALL resources created by this PoC. Are you sure? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cleanup cancelled"
    exit 1
fi

# Clean up IoT certificates and things
if [ -f "certs/cert-arn.txt" ] && [ -f "certs/thing-name.txt" ]; then
    CERT_ARN=$(cat certs/cert-arn.txt)
    THING_NAME=$(cat certs/thing-name.txt)
    CERT_ID=$(echo "$CERT_ARN" | cut -d'/' -f2)
    
    echo "🔐 Cleaning up IoT certificates and things..."
    
    # Detach policy from certificate
    echo "🔗 Detaching policy from certificate..."
    aws iot detach-policy --policy-name "iot-poc-device-policy" --target "$CERT_ARN" 2>/dev/null || true
    
    # Detach certificate from thing
    echo "🔗 Detaching certificate from thing..."
    aws iot detach-thing-principal --thing-name "$THING_NAME" --principal "$CERT_ARN" 2>/dev/null || true
    
    # Deactivate and delete certificate
    echo "🗑️  Deactivating and deleting certificate..."
    aws iot update-certificate --certificate-id "$CERT_ID" --new-status INACTIVE 2>/dev/null || true
    aws iot delete-certificate --certificate-id "$CERT_ID" 2>/dev/null || true
    
    # Delete thing
    echo "🗑️  Deleting thing..."
    aws iot delete-thing --thing-name "$THING_NAME" 2>/dev/null || true
    
    # Delete policy (might fail if used by other certificates)
    echo "🗑️  Attempting to delete policy..."
    aws iot delete-policy --policy-name "iot-poc-device-policy" 2>/dev/null || echo "   Policy might be in use by other certificates"
fi

# Empty S3 bucket before CDK destroy (CDK can't delete non-empty buckets)
if [ -f "outputs.json" ]; then
    BUCKET_NAME=$(cat outputs.json | jq -r '.IotPocStack.S3BucketName // empty')
    if [ ! -z "$BUCKET_NAME" ]; then
        echo "🗑️  Emptying S3 bucket: $BUCKET_NAME"
        aws s3 rm "s3://$BUCKET_NAME" --recursive 2>/dev/null || echo "   Bucket might not exist or be already empty"
    fi
fi

# Destroy CDK stack
echo "🏗️  Destroying CDK stack..."
cdk destroy --force

# Clean up local files
echo "🧹 Cleaning up local files..."
rm -rf certs/
rm -f outputs.json
rm -rf cdk.out/
rm -rf __pycache__/
rm -rf iot_poc/__pycache__/

echo "✅ Cleanup completed!"
echo ""
echo "📋 What was cleaned up:"
echo "- CloudFormation stack and all AWS resources"
echo "- IoT certificates, things, and policies"
echo "- S3 bucket contents"
echo "- Local certificate files"
echo "- Generated output files"
echo ""
echo "💰 Cost: Resources are destroyed and should stop incurring charges" 