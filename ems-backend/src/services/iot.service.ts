import {
  IoTClient,
  ListThingsCommand,
  DescribeThingCommand,
  UpdateThingCommand,
  CreateThingCommand,
  DeleteThingCommand,
  ListThingPrincipalsCommand,
  CreateKeysAndCertificateCommand,
  AttachPolicyCommand,
  AttachThingPrincipalCommand,
  UpdateCertificateCommand,
  DescribeEndpointCommand,
} from '@aws-sdk/client-iot';
import {
  IoTDataPlaneClient,
  GetThingShadowCommand,
  UpdateThingShadowCommand,
  PublishCommand,
} from '@aws-sdk/client-iot-data-plane';
import { awsClients, iotConfig } from '../config/aws.config';
import { createLogger } from '../utils/logger';
import { IDevice, IDeviceShadow, DeviceStatus, ConnectionState } from '../models/interfaces/device.interface';

const logger = createLogger('IoTService');

export class IoTService {
  private iotClient: IoTClient;
  private iotDataClient: IoTDataPlaneClient;
  private endpoint: string | null = null;

  constructor() {
    this.iotClient = awsClients.iotClient;
    this.iotDataClient = awsClients.iotDataClient;
    this.initializeEndpoint();
  }

  /**
   * 初始化IoT端点
   */
  private async initializeEndpoint(): Promise<void> {
    try {
      const command = new DescribeEndpointCommand({
        endpointType: 'iot:Data-ATS',
      });
      const response = await this.iotClient.send(command);
      this.endpoint = response.endpointAddress || null;
      logger.info(`IoT endpoint initialized: ${this.endpoint}`);
    } catch (error) {
      logger.error('Failed to get IoT endpoint:', error);
    }
  }

  /**
   * 获取所有设备列表
   */
  async listDevices(limit: number = 100, nextToken?: string): Promise<{
    devices: IDevice[];
    nextToken?: string;
  }> {
    try {
      const command = new ListThingsCommand({
        maxResults: limit,
        nextToken,
        thingTypeName: iotConfig.thingType,
      });

      const response = await this.iotClient.send(command);
      const devices: IDevice[] = [];

      for (const thing of response.things || []) {
        const device = await this.getDeviceDetails(thing.thingName!);
        if (device) {
          devices.push(device);
        }
      }

      return {
        devices,
        nextToken: response.nextToken,
      };
    } catch (error) {
      logger.error('Failed to list devices:', error);
      throw new Error(`Failed to list devices: ${error.message}`);
    }
  }

  /**
   * 获取设备详情
   */
  async getDeviceDetails(thingName: string): Promise<IDevice | null> {
    try {
      const command = new DescribeThingCommand({ thingName });
      const response = await this.iotClient.send(command);

      if (!response.thingName) {
        return null;
      }

      // 获取设备连接状态
      const connectionState = await this.getDeviceConnectionState(thingName);
      
      // 获取设备影子以获取更多状态信息
      const shadow = await this.getDeviceShadow(thingName);
      const lastSeen = shadow?.state?.reported?.timestamp 
        ? new Date(shadow.state.reported.timestamp) 
        : undefined;

      const device: IDevice = {
        deviceId: response.attributes?.deviceId || thingName,
        thingName: response.thingName,
        thingType: response.thingTypeName,
        attributes: response.attributes || {},
        status: this.determineDeviceStatus(shadow),
        connectionState,
        lastSeen,
        createdAt: new Date(), // IoT Core doesn't provide creation date
        updatedAt: new Date(),
        metadata: {
          thingArn: response.thingArn,
          version: response.version,
        },
      };

      return device;
    } catch (error) {
      logger.error(`Failed to get device details for ${thingName}:`, error);
      return null;
    }
  }

  /**
   * 获取设备影子
   */
  async getDeviceShadow(thingName: string): Promise<IDeviceShadow | null> {
    try {
      const command = new GetThingShadowCommand({ thingName });
      const response = await this.iotDataClient.send(command);

      if (!response.payload) {
        return null;
      }

      const shadowData = JSON.parse(new TextDecoder().decode(response.payload));
      return shadowData;
    } catch (error) {
      if (error.name === 'ResourceNotFoundException') {
        logger.debug(`No shadow found for device ${thingName}`);
        return null;
      }
      logger.error(`Failed to get device shadow for ${thingName}:`, error);
      throw error;
    }
  }

  /**
   * 更新设备影子
   */
  async updateDeviceShadow(
    thingName: string,
    desiredState: Record<string, any>
  ): Promise<IDeviceShadow> {
    try {
      const payload = {
        state: {
          desired: desiredState,
        },
      };

      const command = new UpdateThingShadowCommand({
        thingName,
        payload: new TextEncoder().encode(JSON.stringify(payload)),
      });

      const response = await this.iotDataClient.send(command);
      
      if (!response.payload) {
        throw new Error('No response payload from shadow update');
      }

      const shadowData = JSON.parse(new TextDecoder().decode(response.payload));
      
      logger.info(`Successfully updated shadow for device ${thingName}`);
      return shadowData;
    } catch (error) {
      logger.error(`Failed to update device shadow for ${thingName}:`, error);
      throw new Error(`Failed to update device shadow: ${error.message}`);
    }
  }

  /**
   * 发布MQTT消息到设备
   */
  async publishToDevice(
    deviceId: string,
    topic: string,
    payload: any
  ): Promise<void> {
    try {
      const fullTopic = topic.replace('+', deviceId);
      const command = new PublishCommand({
        topic: fullTopic,
        payload: new TextEncoder().encode(JSON.stringify(payload)),
        qos: 1,
      });

      await this.iotDataClient.send(command);
      logger.info(`Message published to ${fullTopic}`);
    } catch (error) {
      logger.error(`Failed to publish message to ${deviceId}:`, error);
      throw new Error(`Failed to publish message: ${error.message}`);
    }
  }

  /**
   * 发送命令到设备
   */
  async sendCommand(
    deviceId: string,
    command: string,
    parameters?: Record<string, any>
  ): Promise<void> {
    const payload = {
      command,
      parameters,
      timestamp: new Date().toISOString(),
      requestId: this.generateRequestId(),
    };

    await this.publishToDevice(
      deviceId,
      `device/${deviceId}/command`,
      payload
    );
  }

  /**
   * 创建新设备
   */
  async createDevice(
    thingName: string,
    attributes: Record<string, string>,
    generateCertificate: boolean = true
  ): Promise<{
    device: IDevice;
    certificate?: {
      certificateArn: string;
      certificateId: string;
      certificatePem: string;
      privateKey: string;
    };
  }> {
    try {
      // 创建Thing
      const createThingCommand = new CreateThingCommand({
        thingName,
        thingTypeName: iotConfig.thingType,
        attributePayload: { attributes },
      });

      await this.iotClient.send(createThingCommand);
      logger.info(`Created thing: ${thingName}`);

      let certificate;
      if (generateCertificate) {
        // 创建证书
        const createCertCommand = new CreateKeysAndCertificateCommand({
          setAsActive: true,
        });
        const certResponse = await this.iotClient.send(createCertCommand);

        // 附加策略到证书
        await this.iotClient.send(
          new AttachPolicyCommand({
            policyName: iotConfig.policyName,
            target: certResponse.certificateArn!,
          })
        );

        // 附加证书到Thing
        await this.iotClient.send(
          new AttachThingPrincipalCommand({
            thingName,
            principal: certResponse.certificateArn!,
          })
        );

        certificate = {
          certificateArn: certResponse.certificateArn!,
          certificateId: certResponse.certificateId!,
          certificatePem: certResponse.certificatePem!,
          privateKey: certResponse.keyPair!.PrivateKey!,
        };
      }

      const device = await this.getDeviceDetails(thingName);
      if (!device) {
        throw new Error('Failed to retrieve created device');
      }

      return { device, certificate };
    } catch (error) {
      logger.error('Failed to create device:', error);
      throw new Error(`Failed to create device: ${error.message}`);
    }
  }

  /**
   * 更新设备属性
   */
  async updateDeviceAttributes(
    thingName: string,
    attributes: Record<string, string>
  ): Promise<void> {
    try {
      const command = new UpdateThingCommand({
        thingName,
        attributePayload: { attributes },
      });

      await this.iotClient.send(command);
      logger.info(`Updated attributes for device ${thingName}`);
    } catch (error) {
      logger.error(`Failed to update device attributes for ${thingName}:`, error);
      throw new Error(`Failed to update device attributes: ${error.message}`);
    }
  }

  /**
   * 删除设备
   */
  async deleteDevice(thingName: string): Promise<void> {
    try {
      // 先获取并分离所有附加的主体（证书）
      const principalsCommand = new ListThingPrincipalsCommand({ thingName });
      const principalsResponse = await this.iotClient.send(principalsCommand);

      // 分离所有证书
      for (const principal of principalsResponse.principals || []) {
        // 这里可以添加分离证书的逻辑
        logger.info(`Would detach principal ${principal} from ${thingName}`);
      }

      // 删除Thing
      const deleteCommand = new DeleteThingCommand({ thingName });
      await this.iotClient.send(deleteCommand);
      
      logger.info(`Deleted device: ${thingName}`);
    } catch (error) {
      logger.error(`Failed to delete device ${thingName}:`, error);
      throw new Error(`Failed to delete device: ${error.message}`);
    }
  }

  /**
   * 获取设备连接状态
   */
  private async getDeviceConnectionState(thingName: string): Promise<ConnectionState> {
    try {
      const shadow = await this.getDeviceShadow(thingName);
      if (!shadow?.state?.reported?.connected) {
        return ConnectionState.DISCONNECTED;
      }

      const lastUpdate = shadow.state.reported.timestamp || shadow.metadata?.reported?.timestamp;
      if (!lastUpdate) {
        return ConnectionState.UNKNOWN;
      }

      const lastUpdateTime = new Date(lastUpdate).getTime();
      const now = Date.now();
      const fiveMinutes = 5 * 60 * 1000;

      // 如果最后更新时间在5分钟内，认为设备在线
      return now - lastUpdateTime < fiveMinutes 
        ? ConnectionState.CONNECTED 
        : ConnectionState.DISCONNECTED;
    } catch (error) {
      return ConnectionState.UNKNOWN;
    }
  }

  /**
   * 确定设备状态
   */
  private determineDeviceStatus(shadow: IDeviceShadow | null): DeviceStatus {
    if (!shadow?.state?.reported) {
      return DeviceStatus.INACTIVE;
    }

    const reported = shadow.state.reported;
    
    if (reported.error || reported.fault) {
      return DeviceStatus.ERROR;
    }
    
    if (reported.maintenance) {
      return DeviceStatus.MAINTENANCE;
    }
    
    if (reported.active === false) {
      return DeviceStatus.INACTIVE;
    }
    
    return DeviceStatus.ACTIVE;
  }

  /**
   * 生成请求ID
   */
  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * 获取IoT端点
   */
  getEndpoint(): string | null {
    return this.endpoint;
  }
}

// 导出单例
export const iotService = new IoTService();