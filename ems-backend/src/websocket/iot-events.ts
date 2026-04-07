import { Server, Socket } from 'socket.io';
import { Server as HttpServer } from 'http';
import jwt from 'jsonwebtoken';
import { device } from 'aws-iot-device-sdk';
import { appConfig } from '../config/app.config';
import { iotConfig } from '../config/aws.config';
import { createLogger } from '../utils/logger';
import { IAuthUser } from '../middleware/auth.middleware';

const logger = createLogger('WebSocket');

export class IoTEventsService {
  private io: Server;
  private iotDevice: any;
  private subscribedTopics: Set<string> = new Set();
  private deviceSubscriptions: Map<string, Set<string>> = new Map();

  constructor(httpServer: HttpServer) {
    this.io = new Server(httpServer, {
      cors: appConfig.websocket.cors,
      path: '/ws',
    });

    this.setupAuthentication();
    this.setupEventHandlers();
    this.connectToIoT();
  }

  /**
   * 设置WebSocket认证
   */
  private setupAuthentication(): void {
    this.io.use(async (socket, next) => {
      try {
        const token = socket.handshake.auth.token || socket.handshake.query.token;

        if (!token) {
          return next(new Error('Authentication required'));
        }

        const decoded = jwt.verify(token as string, appConfig.jwt.secret) as IAuthUser;
        socket.data.user = decoded;

        logger.info(`WebSocket authenticated: ${decoded.email}`);
        next();
      } catch (error) {
        logger.error('WebSocket authentication failed:', error);
        next(new Error('Invalid authentication token'));
      }
    });
  }

  /**
   * 设置事件处理器
   */
  private setupEventHandlers(): void {
    this.io.on('connection', (socket: Socket) => {
      const user = socket.data.user as IAuthUser;
      logger.info(`Client connected: ${socket.id} (${user.email})`);

      // 加入用户房间
      socket.join(`user:${user.id}`);

      // 处理订阅请求
      socket.on('subscribe', (data: { topics: string[] }) => {
        this.handleSubscribe(socket, data.topics);
      });

      // 处理取消订阅
      socket.on('unsubscribe', (data: { topics: string[] }) => {
        this.handleUnsubscribe(socket, data.topics);
      });

      // 处理设备订阅
      socket.on('subscribe:device', (data: { deviceId: string }) => {
        this.subscribeToDevice(socket, data.deviceId);
      });

      // 处理设备取消订阅
      socket.on('unsubscribe:device', (data: { deviceId: string }) => {
        this.unsubscribeFromDevice(socket, data.deviceId);
      });

      // 发送初始状态
      socket.emit('connected', {
        message: 'Connected to EMS WebSocket',
        timestamp: new Date(),
      });

      // 处理断开连接
      socket.on('disconnect', () => {
        logger.info(`Client disconnected: ${socket.id}`);
        this.cleanupSubscriptions(socket);
      });

      // 处理错误
      socket.on('error', (error) => {
        logger.error(`Socket error for ${socket.id}:`, error);
      });
    });
  }

  /**
   * 连接到AWS IoT
   */
  private connectToIoT(): void {
    if (!iotConfig.endpoint) {
      logger.warn('IoT endpoint not configured, skipping MQTT connection');
      return;
    }

    try {
      // 这里需要配置证书路径
      this.iotDevice = new device({
        keyPath: process.env.IOT_KEY_PATH || 'certs/private.key',
        certPath: process.env.IOT_CERT_PATH || 'certs/certificate.pem',
        caPath: process.env.IOT_CA_PATH || 'certs/root-CA.crt',
        clientId: `ems-backend-${Date.now()}`,
        host: iotConfig.endpoint,
      });

      this.iotDevice.on('connect', () => {
        logger.info('Connected to AWS IoT Core');
        this.subscribeToDefaultTopics();
      });

      this.iotDevice.on('message', (topic: string, payload: Buffer) => {
        this.handleIoTMessage(topic, payload);
      });

      this.iotDevice.on('error', (error: Error) => {
        logger.error('IoT device error:', error);
      });

      this.iotDevice.on('offline', () => {
        logger.warn('IoT device offline');
      });

      this.iotDevice.on('reconnect', () => {
        logger.info('IoT device reconnecting...');
      });
    } catch (error) {
      logger.error('Failed to initialize IoT device:', error);
    }
  }

  /**
   * 订阅默认主题
   */
  private subscribeToDefaultTopics(): void {
    const defaultTopics = [
      'device/+/telemetry',
      'device/+/status',
      '$aws/things/+/shadow/update/accepted',
      '$aws/things/+/shadow/update/rejected',
    ];

    defaultTopics.forEach(topic => {
      this.iotDevice.subscribe(topic, { qos: 1 }, (error: Error) => {
        if (error) {
          logger.error(`Failed to subscribe to ${topic}:`, error);
        } else {
          logger.info(`Subscribed to IoT topic: ${topic}`);
          this.subscribedTopics.add(topic);
        }
      });
    });
  }

  /**
   * 处理IoT消息
   */
  private handleIoTMessage(topic: string, payload: Buffer): void {
    try {
      const message = JSON.parse(payload.toString());
      const topicParts = topic.split('/');

      // 提取设备ID
      let deviceId: string | null = null;
      if (topicParts[0] === 'device' && topicParts[2]) {
        deviceId = topicParts[1];
      } else if (topic.includes('$aws/things/')) {
        deviceId = topicParts[2];
      }

      // 构建事件数据
      const eventData = {
        topic,
        deviceId,
        timestamp: new Date(),
        data: message,
      };

      // 广播到相关房间
      if (deviceId) {
        // 发送给订阅该设备的客户端
        this.io.to(`device:${deviceId}`).emit('telemetry', eventData);
        
        // 发送给订阅了特定设备的用户
        const subscribers = this.deviceSubscriptions.get(deviceId);
        if (subscribers) {
          subscribers.forEach(socketId => {
            this.io.to(socketId).emit('device:update', eventData);
          });
        }
      }

      // 广播给订阅了所有设备的客户端
      this.io.to('telemetry:all').emit('telemetry:update', eventData);

      // 根据主题类型发送特定事件
      if (topic.includes('/telemetry')) {
        this.io.to('telemetry:live').emit('telemetry:live', eventData);
      } else if (topic.includes('/status')) {
        this.io.to('status:updates').emit('status:update', eventData);
      } else if (topic.includes('/shadow/')) {
        this.io.to('shadow:updates').emit('shadow:update', eventData);
      }

      logger.debug(`Broadcasted IoT message from topic: ${topic}`);
    } catch (error) {
      logger.error('Failed to handle IoT message:', error);
    }
  }

  /**
   * 处理订阅
   */
  private handleSubscribe(socket: Socket, topics: string[]): void {
    const user = socket.data.user as IAuthUser;

    topics.forEach(topic => {
      // 检查权限
      if (!this.hasPermission(user, topic)) {
        socket.emit('subscription:error', {
          topic,
          error: 'Insufficient permissions',
        });
        return;
      }

      // 加入房间
      socket.join(topic);
      logger.info(`Socket ${socket.id} subscribed to: ${topic}`);

      socket.emit('subscription:success', {
        topic,
        timestamp: new Date(),
      });
    });
  }

  /**
   * 处理取消订阅
   */
  private handleUnsubscribe(socket: Socket, topics: string[]): void {
    topics.forEach(topic => {
      socket.leave(topic);
      logger.info(`Socket ${socket.id} unsubscribed from: ${topic}`);

      socket.emit('unsubscription:success', {
        topic,
        timestamp: new Date(),
      });
    });
  }

  /**
   * 订阅特定设备
   */
  private subscribeToDevice(socket: Socket, deviceId: string): void {
    const user = socket.data.user as IAuthUser;

    // 检查权限
    if (!user.permissions.includes('telemetry:read') && !user.permissions.includes('*')) {
      socket.emit('subscription:error', {
        deviceId,
        error: 'Insufficient permissions',
      });
      return;
    }

    // 加入设备房间
    socket.join(`device:${deviceId}`);

    // 记录订阅关系
    if (!this.deviceSubscriptions.has(deviceId)) {
      this.deviceSubscriptions.set(deviceId, new Set());
    }
    this.deviceSubscriptions.get(deviceId)!.add(socket.id);

    logger.info(`Socket ${socket.id} subscribed to device: ${deviceId}`);

    socket.emit('device:subscribed', {
      deviceId,
      timestamp: new Date(),
    });
  }

  /**
   * 取消订阅设备
   */
  private unsubscribeFromDevice(socket: Socket, deviceId: string): void {
    socket.leave(`device:${deviceId}`);

    // 清理订阅关系
    const subscribers = this.deviceSubscriptions.get(deviceId);
    if (subscribers) {
      subscribers.delete(socket.id);
      if (subscribers.size === 0) {
        this.deviceSubscriptions.delete(deviceId);
      }
    }

    logger.info(`Socket ${socket.id} unsubscribed from device: ${deviceId}`);

    socket.emit('device:unsubscribed', {
      deviceId,
      timestamp: new Date(),
    });
  }

  /**
   * 清理订阅
   */
  private cleanupSubscriptions(socket: Socket): void {
    // 清理设备订阅
    this.deviceSubscriptions.forEach((subscribers, deviceId) => {
      if (subscribers.has(socket.id)) {
        subscribers.delete(socket.id);
        if (subscribers.size === 0) {
          this.deviceSubscriptions.delete(deviceId);
        }
      }
    });
  }

  /**
   * 检查权限
   */
  private hasPermission(user: IAuthUser, topic: string): boolean {
    // 管理员有所有权限
    if (user.permissions.includes('*')) {
      return true;
    }

    // 根据主题检查权限
    if (topic.includes('telemetry')) {
      return user.permissions.includes('telemetry:read');
    }
    if (topic.includes('device')) {
      return user.permissions.includes('devices:read');
    }
    if (topic.includes('energy')) {
      return user.permissions.includes('energy:read');
    }

    return false;
  }

  /**
   * 发送事件给特定用户
   */
  public sendToUser(userId: string, event: string, data: any): void {
    this.io.to(`user:${userId}`).emit(event, data);
  }

  /**
   * 发送事件给特定设备的订阅者
   */
  public sendToDevice(deviceId: string, event: string, data: any): void {
    this.io.to(`device:${deviceId}`).emit(event, data);
  }

  /**
   * 广播事件
   */
  public broadcast(event: string, data: any): void {
    this.io.emit(event, data);
  }

  /**
   * 获取连接的客户端数量
   */
  public getConnectedClients(): number {
    return this.io.sockets.sockets.size;
  }

  /**
   * 获取房间信息
   */
  public getRoomInfo(): Map<string, Set<string>> {
    return this.io.sockets.adapter.rooms;
  }
}

// WebSocket事件类型
export enum WebSocketEvents {
  // 连接事件
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  ERROR = 'error',

  // 订阅事件
  SUBSCRIBE = 'subscribe',
  UNSUBSCRIBE = 'unsubscribe',
  SUBSCRIPTION_SUCCESS = 'subscription:success',
  SUBSCRIPTION_ERROR = 'subscription:error',

  // 设备事件
  DEVICE_SUBSCRIBE = 'subscribe:device',
  DEVICE_UNSUBSCRIBE = 'unsubscribe:device',
  DEVICE_SUBSCRIBED = 'device:subscribed',
  DEVICE_UNSUBSCRIBED = 'device:unsubscribed',
  DEVICE_UPDATE = 'device:update',

  // 数据事件
  TELEMETRY = 'telemetry',
  TELEMETRY_UPDATE = 'telemetry:update',
  TELEMETRY_LIVE = 'telemetry:live',
  STATUS_UPDATE = 'status:update',
  SHADOW_UPDATE = 'shadow:update',

  // 能源事件
  ENERGY_UPDATE = 'energy:update',
  ENERGY_ALERT = 'energy:alert',

  // 系统事件
  SYSTEM_ALERT = 'system:alert',
  SYSTEM_STATUS = 'system:status',
}