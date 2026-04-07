import { s3Service } from './src/services/s3.service';
import { iotService } from './src/services/iot.service';
import { createLogger } from './src/utils/logger';

const logger = createLogger('TestAWSConnection');

async function testAWSConnections() {
  logger.info('Testing AWS connections...');

  // Test S3 connection
  try {
    logger.info('Testing S3 connection...');
    const s3Objects = await s3Service['listObjects']('iot-demo-data-lake-985539760410', 'raw-data/');
    logger.info(`✅ S3 connection successful. Found ${s3Objects.length} objects`);
  } catch (error) {
    logger.error('❌ S3 connection failed:', error);
  }

  // Test IoT Core connection
  try {
    logger.info('Testing IoT Core connection...');
    const devices = await iotService.listDevices(5);
    logger.info(`✅ IoT Core connection successful. Found ${devices.devices.length} devices`);
    
    const endpoint = iotService.getEndpoint();
    logger.info(`IoT Endpoint: ${endpoint}`);
  } catch (error) {
    logger.error('❌ IoT Core connection failed:', error);
  }

  // Test getting latest device data
  try {
    logger.info('Testing device data retrieval...');
    const latestData = await s3Service.getLatestDeviceData('test-device-001');
    if (latestData) {
      logger.info('✅ Successfully retrieved latest device data:', {
        deviceId: latestData.deviceId,
        timestamp: latestData.timestamp,
        metrics: Object.keys(latestData.metrics).length
      });
    } else {
      logger.info('ℹ️ No recent data found for test-device-001');
    }
  } catch (error) {
    logger.error('❌ Failed to retrieve device data:', error);
  }

  logger.info('AWS connection tests completed');
}

// Run the tests
testAWSConnections().catch(console.error);