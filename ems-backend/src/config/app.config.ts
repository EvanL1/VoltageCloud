import dotenv from 'dotenv';

// 加载环境变量
dotenv.config();

export const appConfig = {
  // 服务器配置
  server: {
    port: parseInt(process.env.PORT || '3000', 10),
    env: process.env.NODE_ENV || 'development',
    corsOrigin: process.env.CORS_ORIGIN || '*',
  },

  // API配置
  api: {
    prefix: '/api/v1',
    rateLimit: {
      windowMs: 15 * 60 * 1000, // 15分钟
      max: parseInt(process.env.API_RATE_LIMIT || '100', 10),
    },
  },

  // JWT配置
  jwt: {
    secret: process.env.JWT_SECRET || 'default-secret-key',
    expiresIn: process.env.JWT_EXPIRY || '7d',
    refreshExpiresIn: process.env.JWT_REFRESH_EXPIRY || '30d',
  },

  // 日志配置
  logging: {
    level: process.env.LOG_LEVEL || 'info',
    dir: process.env.LOG_DIR || 'logs',
  },

  // Redis配置
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379', 10),
    password: process.env.REDIS_PASSWORD,
    ttl: 3600, // 默认缓存1小时
  },

  // Grafana配置
  grafana: {
    url: process.env.GRAFANA_URL || 'http://localhost:3001',
    apiKey: process.env.GRAFANA_API_KEY,
  },

  // 分页配置
  pagination: {
    defaultLimit: 20,
    maxLimit: 100,
  },

  // WebSocket配置
  websocket: {
    cors: {
      origin: process.env.CORS_ORIGIN || '*',
      credentials: true,
    },
  },
};