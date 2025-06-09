#!/bin/bash
# IoT PoC Kafka Status Check Script

set -e

echo "🔍 Checking Kafka (MSK) cluster status..."

# Check if outputs.json exists
if [ ! -f "outputs.json" ]; then
    echo "❌ outputs.json not found. Please deploy the stack first: ./scripts/deploy.sh"
    exit 1
fi

# Extract MSK cluster information
MSK_CLUSTER_ARN=$(cat outputs.json | jq -r '.IotPocStack.MSKClusterArn // empty')
BOOTSTRAP_SERVERS=$(cat outputs.json | jq -r '.IotPocStack.MSKBootstrapServers // empty')
KAFKA_TOPIC=$(cat outputs.json | jq -r '.IotPocStack.KafkaTopic // empty')

if [ -z "$MSK_CLUSTER_ARN" ]; then
    echo "❌ MSK cluster ARN not found in outputs"
    exit 1
fi

echo "📊 MSK Cluster Information:"
echo "=========================="
echo "Cluster ARN: $MSK_CLUSTER_ARN"
echo "Bootstrap Servers: $BOOTSTRAP_SERVERS"
echo "Topic: $KAFKA_TOPIC"
echo ""

# Check cluster status
echo "🔍 Checking cluster status..."
CLUSTER_STATUS=$(aws kafka describe-cluster --cluster-arn "$MSK_CLUSTER_ARN" --query 'ClusterInfo.State' --output text)
echo "Cluster State: $CLUSTER_STATUS"

if [ "$CLUSTER_STATUS" = "ACTIVE" ]; then
    echo "✅ MSK cluster is active and ready"
    
    # Get detailed cluster info
    echo ""
    echo "📋 Cluster Details:"
    aws kafka describe-cluster --cluster-arn "$MSK_CLUSTER_ARN" --query 'ClusterInfo.{
        CreationTime: CreationTime,
        KafkaVersion: CurrentVersion.KafkaVersion,
        NumberOfBrokerNodes: NumberOfBrokerNodes,
        InstanceType: BrokerNodeGroupInfo.InstanceType,
        StorageSize: BrokerNodeGroupInfo.StorageInfo.EBSStorageInfo.VolumeSize
    }' --output table
    
elif [ "$CLUSTER_STATUS" = "CREATING" ]; then
    echo "⏳ MSK cluster is still being created. This may take 10-15 minutes..."
    echo "💡 You can monitor progress with: aws kafka describe-cluster --cluster-arn $MSK_CLUSTER_ARN"
    
elif [ "$CLUSTER_STATUS" = "DELETING" ]; then
    echo "🗑️  MSK cluster is being deleted"
    
else
    echo "⚠️  MSK cluster status: $CLUSTER_STATUS"
fi

# Check if Lambda function exists and is connected
echo ""
echo "🔍 Checking Lambda integration..."
LAMBDA_NAME=$(cat outputs.json | jq -r '.IotPocStack.LambdaFunctionName // empty')

if [ ! -z "$LAMBDA_NAME" ]; then
    # Check Lambda function status
    LAMBDA_STATE=$(aws lambda get-function --function-name "$LAMBDA_NAME" --query 'Configuration.State' --output text 2>/dev/null || echo "NOT_FOUND")
    echo "Lambda State: $LAMBDA_STATE"
    
    if [ "$LAMBDA_STATE" = "Active" ]; then
        echo "✅ Lambda function is active"
        
        # Check event source mappings
        echo ""
        echo "🔗 Event Source Mappings:"
        aws lambda list-event-source-mappings --function-name "$LAMBDA_NAME" --query 'EventSourceMappings[].{
            State: State,
            EventSourceArn: EventSourceArn,
            LastModified: LastModified
        }' --output table
        
    else
        echo "⚠️  Lambda function state: $LAMBDA_STATE"
    fi
else
    echo "❌ Lambda function name not found"
fi

# Check recent Lambda logs if cluster is active
if [ "$CLUSTER_STATUS" = "ACTIVE" ] && [ "$LAMBDA_STATE" = "Active" ]; then
    echo ""
    echo "📝 Recent Lambda logs (last 5 minutes):"
    echo "======================================="
    aws logs tail "/aws/lambda/$LAMBDA_NAME" --since 5m --format short | head -20 || echo "No recent logs found"
fi

echo ""
echo "🔧 Useful commands:"
echo "=================="
echo "# Monitor cluster status:"
echo "aws kafka describe-cluster --cluster-arn $MSK_CLUSTER_ARN"
echo ""
echo "# List Lambda event source mappings:"
echo "aws lambda list-event-source-mappings --function-name $LAMBDA_NAME"
echo ""
echo "# Monitor Lambda logs:"
echo "aws logs tail /aws/lambda/$LAMBDA_NAME --follow"
echo ""
echo "# Check IoT topic rule:"
echo "aws iot get-topic-rule --rule-name iot_poc_to_kafka" 