import { S3Client } from '@aws-sdk/client-s3';
import { IoTClient } from '@aws-sdk/client-iot';
import { IoTDataPlaneClient } from '@aws-sdk/client-iot-data-plane';
import { TimestreamQueryClient } from '@aws-sdk/client-timestream-query';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient } from '@aws-sdk/lib-dynamodb';
import { LambdaClient } from '@aws-sdk/client-lambda';

// AWS配置
export const awsConfig = {
  region: process.env.AWS_REGION || 'us-east-1',
  credentials: process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY ? {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
  } : undefined,
};

// S3配置
export const s3Config = {
  buckets: {
    dataLake: process.env.S3_DATA_LAKE_BUCKET || 'iot-demo-data-lake-985539760410',
    otaUpdates: process.env.S3_OTA_BUCKET || 'iot-demo-ota-updates-985539760410',
  },
  presignedUrlExpiry: 3600, // 1小时
};

// IoT配置
export const iotConfig = {
  endpoint: process.env.AWS_IOT_ENDPOINT || '',
  thingType: process.env.IOT_THING_TYPE || 'iot-demo-device-type',
  policyName: process.env.IOT_POLICY_NAME || 'iot-demo-device-policy',
  topics: {
    telemetry: 'device/+/telemetry',
    command: 'device/+/command',
    status: 'device/+/status',
    shadow: '$aws/things/+/shadow/+',
  },
};

// DynamoDB配置
export const dynamoConfig = {
  tables: {
    devices: process.env.DYNAMODB_TABLE_DEVICES || 'ems-devices',
    users: process.env.DYNAMODB_TABLE_USERS || 'ems-users',
    sessions: process.env.DYNAMODB_TABLE_SESSIONS || 'ems-sessions',
    energyData: process.env.DYNAMODB_TABLE_ENERGY || 'ems-energy-data',
  },
};

// TimeStream配置
export const timestreamConfig = {
  database: process.env.TIMESTREAM_DATABASE || 'iot-demo_iot_db',
  table: process.env.TIMESTREAM_TABLE || 'device_metrics',
  retentionPeriod: {
    memoryStoreHours: 24,
    magneticStoreDays: 365,
  },
};

// Lambda配置
export const lambdaConfig = {
  functions: {
    dataProcessor: process.env.LAMBDA_PROCESSOR_NAME || 'iot-demo-iot-data-processor',
  },
};

// 创建AWS客户端实例
export const createAWSClients = () => {
  // S3客户端
  const s3Client = new S3Client(awsConfig);

  // IoT客户端
  const iotClient = new IoTClient(awsConfig);
  const iotDataClient = new IoTDataPlaneClient({
    ...awsConfig,
    endpoint: `https://${iotConfig.endpoint}`,
  });

  // DynamoDB客户端
  const dynamoClient = new DynamoDBClient(awsConfig);
  const dynamoDocClient = DynamoDBDocumentClient.from(dynamoClient);

  // TimeStream客户端
  const timestreamClient = new TimestreamQueryClient(awsConfig);

  // Lambda客户端
  const lambdaClient = new LambdaClient(awsConfig);

  return {
    s3Client,
    iotClient,
    iotDataClient,
    dynamoClient,
    dynamoDocClient,
    timestreamClient,
    lambdaClient,
  };
};

// 导出客户端实例
export const awsClients = createAWSClients();