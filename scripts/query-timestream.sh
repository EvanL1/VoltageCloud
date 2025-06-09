#!/bin/bash
# IoT PoC TimeStream Query Script

set -e

echo "🔍 Querying TimeStream data..."

# Default query - show recent data
QUERY=${1:-"SELECT time, deviceId, metric, measure_value::double as value FROM iot_poc.metrics WHERE time > ago(1h) ORDER BY time DESC LIMIT 20"}

echo "📊 Executing query:"
echo "$QUERY"
echo ""

# Execute the query and format output
RESULT=$(aws timestream-query query --query-string "$QUERY" --output json)

if echo "$RESULT" | jq -e '.Rows | length > 0' > /dev/null; then
    echo "✅ Query results:"
    echo "================="
    
    # Format the output nicely
    echo "$RESULT" | jq -r '
        .ColumnInfo as $cols |
        .Rows[] |
        . as $row |
        [$cols | keys[] as $i | $cols[$i].Name + ": " + $row.Data[$i].ScalarValue] |
        join(" | ")
    ' | column -t -s '|'
    
    echo ""
    echo "📈 Summary:"
    TOTAL_ROWS=$(echo "$RESULT" | jq '.Rows | length')
    echo "Total records: $TOTAL_ROWS"
    
    # Show unique devices
    DEVICES=$(echo "$RESULT" | jq -r '.Rows[].Data[1].ScalarValue' 2>/dev/null | sort | uniq | wc -l)
    echo "Unique devices: $DEVICES"
    
    # Show metrics
    METRICS=$(echo "$RESULT" | jq -r '.Rows[].Data[2].ScalarValue' 2>/dev/null | sort | uniq | tr '\n' ', ' | sed 's/,$//')
    echo "Metrics found: $METRICS"
    
else
    echo "📭 No data found in TimeStream"
    echo ""
    echo "💡 Troubleshooting tips:"
    echo "1. Check if data was recently sent: ./scripts/test-mqtt.sh"
    echo "2. Check Lambda logs: aws logs tail /aws/lambda/iot-poc-sqs-processor --since 10m"
fi

echo ""
echo "🔧 Other useful queries:"
echo "========================"
echo "# Show all devices:"
echo "SELECT DISTINCT deviceId FROM iot_poc.metrics"
echo ""
echo "# Show average temperature per device (last hour):"
echo "SELECT deviceId, AVG(measure_value::double) as avg_temp FROM iot_poc.metrics WHERE metric='temp' AND time > ago(1h) GROUP BY deviceId"
echo ""
echo "# Show latest values for each metric:"
echo "SELECT deviceId, metric, measure_value::double as value, time FROM iot_poc.metrics WHERE time > ago(15m) ORDER BY time DESC" 