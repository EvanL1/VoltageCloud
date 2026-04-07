import express, { Application } from 'express';
import http from 'http';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import rateLimit from 'express-rate-limit';
import dotenv from 'dotenv';

// 加载环境变量
dotenv.config();

import { appConfig } from './config/app.config';
import { logger, httpLogger } from './utils/logger';
import { errorHandler, notFoundHandler } from './middleware/error.middleware';
import { IoTEventsService } from './websocket/iot-events';

// 导入路由
import authRoutes from './routes/auth.routes';
import deviceRoutes from './routes/device.routes';
import telemetryRoutes from './routes/telemetry.routes';
import energyRoutes from './routes/energy.routes';

class App {
  public app: Application;
  public server: http.Server;
  private iotEvents: IoTEventsService;

  constructor() {
    this.app = express();
    this.server = http.createServer(this.app);
    this.iotEvents = new IoTEventsService(this.server);
    
    this.initializeMiddlewares();
    this.initializeRoutes();
    this.initializeErrorHandling();
  }

  /**
   * 初始化中间件
   */
  private initializeMiddlewares(): void {
    // 安全中间件
    this.app.use(helmet({
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
          styleSrc: ["'self'", "'unsafe-inline'"],
          scriptSrc: ["'self'"],
          imgSrc: ["'self'", "data:", "https:"],
          connectSrc: ["'self'", "wss:", "https:"],
        },
      },
    }));

    // CORS配置
    this.app.use(cors({
      origin: appConfig.server.corsOrigin,
      credentials: true,
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'Authorization', 'X-API-Key'],
    }));

    // 请求解析
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true, limit: '10mb' }));

    // 请求日志
    this.app.use(morgan('combined', {
      stream: {
        write: (message: string) => httpLogger.info(message.trim()),
      },
    }));

    // 速率限制
    const limiter = rateLimit({
      windowMs: appConfig.api.rateLimit.windowMs,
      max: appConfig.api.rateLimit.max,
      message: 'Too many requests from this IP, please try again later.',
      standardHeaders: true,
      legacyHeaders: false,
    });

    this.app.use(`${appConfig.api.prefix}/`, limiter);

    // 请求ID中间件
    this.app.use((req, res, next) => {
      (req as any).id = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      next();
    });

    // 健康检查端点
    this.app.get('/health', (req, res) => {
      res.json({
        status: 'healthy',
        timestamp: new Date(),
        uptime: process.uptime(),
        environment: appConfig.server.env,
        websocketClients: this.iotEvents.getConnectedClients(),
      });
    });

    // API信息端点
    this.app.get('/api', (req, res) => {
      res.json({
        name: 'EMS Backend API',
        version: '1.0.0',
        description: 'Energy Management System Backend with AWS IoT Integration',
        endpoints: {
          devices: `${appConfig.api.prefix}/devices`,
          telemetry: `${appConfig.api.prefix}/telemetry`,
          energy: `${appConfig.api.prefix}/energy`,
          websocket: '/ws',
        },
        documentation: '/api/docs',
      });
    });
  }

  /**
   * 初始化路由
   */
  private initializeRoutes(): void {
    // API路由
    this.app.use(`${appConfig.api.prefix}/auth`, authRoutes);
    this.app.use(`${appConfig.api.prefix}/devices`, deviceRoutes);
    this.app.use(`${appConfig.api.prefix}/telemetry`, telemetryRoutes);
    this.app.use(`${appConfig.api.prefix}/energy`, energyRoutes);

    // 静态文件服务（如果需要）
    // this.app.use('/static', express.static('public'));
  }

  /**
   * 初始化错误处理
   */
  private initializeErrorHandling(): void {
    // 404处理
    this.app.use(notFoundHandler);

    // 全局错误处理
    this.app.use(errorHandler);
  }

  /**
   * 启动服务器
   */
  public listen(): void {
    const port = appConfig.server.port;

    this.server.listen(port, () => {
      logger.info(`
        ################################################
        🚀 Server listening on port: ${port}
        🌍 Environment: ${appConfig.server.env}
        📍 API Prefix: ${appConfig.api.prefix}
        🔌 WebSocket Path: /ws
        ################################################
      `);
    });

    // 优雅关闭
    process.on('SIGTERM', () => {
      logger.info('SIGTERM signal received: closing HTTP server');
      this.server.close(() => {
        logger.info('HTTP server closed');
        process.exit(0);
      });
    });

    process.on('SIGINT', () => {
      logger.info('SIGINT signal received: closing HTTP server');
      this.server.close(() => {
        logger.info('HTTP server closed');
        process.exit(0);
      });
    });
  }
}

// 创建并启动应用
const app = new App();
app.listen();

export default app.app;