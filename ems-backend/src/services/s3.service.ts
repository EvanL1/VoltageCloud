import {
  S3Client,
  GetObjectCommand,
  ListObjectsV2Command,
  PutObjectCommand,
  DeleteObjectCommand,
  HeadObjectCommand,
  GetObjectCommandOutput,
} from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import { Readable } from 'stream';
import { awsClients, s3Config } from '../config/aws.config';
import { createLogger } from '../utils/logger';
import { ITelemetryData } from '../models/interfaces/telemetry.interface';

const logger = createLogger('S3Service');

export class S3Service {
  private s3Client: S3Client;

  constructor() {
    this.s3Client = awsClients.s3Client;
  }

  /**
   * 获取设备的遥测数据
   */
  async getDeviceTelemetryData(
    deviceId: string,
    startDate: Date,
    endDate: Date,
    limit?: number
  ): Promise<ITelemetryData[]> {
    try {
      const prefix = `raw-data/${deviceId}/`;
      const allData: ITelemetryData[] = [];
      
      // 生成日期范围内的所有路径
      const datePaths = this.generateDatePaths(startDate, endDate);
      
      for (const datePath of datePaths) {
        const fullPrefix = `${prefix}${datePath}`;
        const objects = await this.listObjects(s3Config.buckets.dataLake, fullPrefix);
        
        // 获取每个对象的内容
        for (const obj of objects) {
          if (limit && allData.length >= limit) break;
          
          try {
            const data = await this.getObject(s3Config.buckets.dataLake, obj.Key!);
            const jsonData = JSON.parse(data);
            
            // 转换为标准格式
            const telemetryData: ITelemetryData = {
              deviceId: jsonData.deviceId || deviceId,
              timestamp: new Date(parseInt(obj.Key!.split('/').pop()!.replace('.json', ''))),
              metrics: jsonData.metrics || {},
              metadata: jsonData.metadata || {},
            };
            
            allData.push(telemetryData);
          } catch (error) {
            logger.error(`Failed to parse object ${obj.Key}:`, error);
          }
        }
        
        if (limit && allData.length >= limit) break;
      }
      
      // 按时间戳排序
      allData.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
      
      return limit ? allData.slice(0, limit) : allData;
    } catch (error) {
      logger.error('Failed to get device telemetry data:', error);
      throw new Error(`Failed to retrieve telemetry data: ${error.message}`);
    }
  }

  /**
   * 获取最新的设备数据
   */
  async getLatestDeviceData(deviceId: string): Promise<ITelemetryData | null> {
    try {
      const today = new Date();
      const data = await this.getDeviceTelemetryData(
        deviceId,
        new Date(today.getTime() - 24 * 60 * 60 * 1000), // 过去24小时
        today,
        1
      );
      
      return data.length > 0 ? data[0] : null;
    } catch (error) {
      logger.error('Failed to get latest device data:', error);
      return null;
    }
  }

  /**
   * 获取多个设备的数据
   */
  async getMultipleDevicesTelemetryData(
    deviceIds: string[],
    startDate: Date,
    endDate: Date,
    limitPerDevice?: number
  ): Promise<Map<string, ITelemetryData[]>> {
    const result = new Map<string, ITelemetryData[]>();
    
    // 并行获取所有设备的数据
    const promises = deviceIds.map(async (deviceId) => {
      const data = await this.getDeviceTelemetryData(
        deviceId,
        startDate,
        endDate,
        limitPerDevice
      );
      return { deviceId, data };
    });
    
    const results = await Promise.all(promises);
    results.forEach(({ deviceId, data }) => {
      result.set(deviceId, data);
    });
    
    return result;
  }

  /**
   * 列出S3对象
   */
  private async listObjects(bucket: string, prefix: string): Promise<any[]> {
    try {
      const command = new ListObjectsV2Command({
        Bucket: bucket,
        Prefix: prefix,
        MaxKeys: 1000,
      });
      
      const response = await this.s3Client.send(command);
      return response.Contents || [];
    } catch (error) {
      logger.error(`Failed to list objects in ${bucket}/${prefix}:`, error);
      throw error;
    }
  }

  /**
   * 获取S3对象内容
   */
  private async getObject(bucket: string, key: string): Promise<string> {
    try {
      const command = new GetObjectCommand({
        Bucket: bucket,
        Key: key,
      });
      
      const response = await this.s3Client.send(command);
      return await this.streamToString(response.Body as Readable);
    } catch (error) {
      logger.error(`Failed to get object ${bucket}/${key}:`, error);
      throw error;
    }
  }

  /**
   * 生成预签名URL
   */
  async generatePresignedUrl(
    bucket: string,
    key: string,
    expiresIn: number = s3Config.presignedUrlExpiry
  ): Promise<string> {
    try {
      const command = new GetObjectCommand({
        Bucket: bucket,
        Key: key,
      });
      
      return await getSignedUrl(this.s3Client, command, { expiresIn });
    } catch (error) {
      logger.error('Failed to generate presigned URL:', error);
      throw error;
    }
  }

  /**
   * 上传数据到S3
   */
  async uploadData(
    bucket: string,
    key: string,
    data: Buffer | Uint8Array | string,
    contentType: string = 'application/json'
  ): Promise<void> {
    try {
      const command = new PutObjectCommand({
        Bucket: bucket,
        Key: key,
        Body: data,
        ContentType: contentType,
      });
      
      await this.s3Client.send(command);
      logger.info(`Successfully uploaded data to ${bucket}/${key}`);
    } catch (error) {
      logger.error(`Failed to upload data to ${bucket}/${key}:`, error);
      throw error;
    }
  }

  /**
   * 检查对象是否存在
   */
  async objectExists(bucket: string, key: string): Promise<boolean> {
    try {
      const command = new HeadObjectCommand({
        Bucket: bucket,
        Key: key,
      });
      
      await this.s3Client.send(command);
      return true;
    } catch (error) {
      if (error.name === 'NotFound') {
        return false;
      }
      throw error;
    }
  }

  /**
   * 删除对象
   */
  async deleteObject(bucket: string, key: string): Promise<void> {
    try {
      const command = new DeleteObjectCommand({
        Bucket: bucket,
        Key: key,
      });
      
      await this.s3Client.send(command);
      logger.info(`Successfully deleted object ${bucket}/${key}`);
    } catch (error) {
      logger.error(`Failed to delete object ${bucket}/${key}:`, error);
      throw error;
    }
  }

  /**
   * 生成日期路径
   */
  private generateDatePaths(startDate: Date, endDate: Date): string[] {
    const paths: string[] = [];
    const currentDate = new Date(startDate);
    
    while (currentDate <= endDate) {
      const year = currentDate.getFullYear();
      const month = String(currentDate.getMonth() + 1).padStart(2, '0');
      const day = String(currentDate.getDate()).padStart(2, '0');
      
      paths.push(`${year}/${month}/${day}`);
      
      // 移到下一天
      currentDate.setDate(currentDate.getDate() + 1);
    }
    
    return paths;
  }

  /**
   * 将流转换为字符串
   */
  private async streamToString(stream: Readable): Promise<string> {
    const chunks: any[] = [];
    
    return new Promise((resolve, reject) => {
      stream.on('data', (chunk) => chunks.push(chunk));
      stream.on('error', reject);
      stream.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    });
  }

  /**
   * 批量获取对象
   */
  async batchGetObjects(bucket: string, keys: string[]): Promise<Map<string, string>> {
    const result = new Map<string, string>();
    
    // 并行获取所有对象
    const promises = keys.map(async (key) => {
      try {
        const content = await this.getObject(bucket, key);
        return { key, content };
      } catch (error) {
        logger.error(`Failed to get object ${key}:`, error);
        return { key, content: null };
      }
    });
    
    const results = await Promise.all(promises);
    results.forEach(({ key, content }) => {
      if (content) {
        result.set(key, content);
      }
    });
    
    return result;
  }
}

// 导出单例
export const s3Service = new S3Service();