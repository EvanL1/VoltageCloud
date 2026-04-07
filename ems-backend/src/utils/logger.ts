import winston from 'winston';
import path from 'path';
import fs from 'fs';
import { appConfig } from '../config/app.config';

// 确保日志目录存在
const logDir = path.join(process.cwd(), appConfig.logging.dir);
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true });
}

// 定义日志格式
const logFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.errors({ stack: true }),
  winston.format.splat(),
  winston.format.json()
);

// 控制台输出格式（开发环境）
const consoleFormat = winston.format.combine(
  winston.format.colorize(),
  winston.format.timestamp({ format: 'HH:mm:ss' }),
  winston.format.printf(({ timestamp, level, message, ...meta }) => {
    let metaStr = '';
    if (Object.keys(meta).length > 0) {
      metaStr = JSON.stringify(meta, null, 2);
    }
    return `${timestamp} [${level}]: ${message} ${metaStr}`;
  })
);

// 创建 Winston logger
export const logger = winston.createLogger({
  level: appConfig.logging.level,
  format: logFormat,
  defaultMeta: { service: 'ems-backend' },
  transports: [
    // 错误日志
    new winston.transports.File({
      filename: path.join(logDir, 'error.log'),
      level: 'error',
      maxsize: 10485760, // 10MB
      maxFiles: 5,
    }),
    // 所有日志
    new winston.transports.File({
      filename: path.join(logDir, 'combined.log'),
      maxsize: 10485760, // 10MB
      maxFiles: 10,
    }),
  ],
});

// 开发环境添加控制台输出
if (appConfig.server.env !== 'production') {
  logger.add(
    new winston.transports.Console({
      format: consoleFormat,
    })
  );
}

// HTTP请求日志中间件
export const httpLogger = winston.createLogger({
  level: 'info',
  format: logFormat,
  transports: [
    new winston.transports.File({
      filename: path.join(logDir, 'http.log'),
      maxsize: 10485760, // 10MB
      maxFiles: 5,
    }),
  ],
});

// 为不同模块创建子logger
export const createLogger = (module: string) => {
  return logger.child({ module });
};

// 审计日志
export const auditLogger = winston.createLogger({
  level: 'info',
  format: logFormat,
  transports: [
    new winston.transports.File({
      filename: path.join(logDir, 'audit.log'),
      maxsize: 10485760, // 10MB
      maxFiles: 30, // 保留更多审计日志
    }),
  ],
});

// 性能日志
export const performanceLogger = winston.createLogger({
  level: 'info',
  format: logFormat,
  transports: [
    new winston.transports.File({
      filename: path.join(logDir, 'performance.log'),
      maxsize: 10485760, // 10MB
      maxFiles: 5,
    }),
  ],
});

// 记录未捕获的异常
logger.exceptions.handle(
  new winston.transports.File({
    filename: path.join(logDir, 'exceptions.log'),
  })
);

// 记录未处理的Promise拒绝
logger.rejections.handle(
  new winston.transports.File({
    filename: path.join(logDir, 'rejections.log'),
  })
);

// 导出日志级别
export const LogLevel = {
  ERROR: 'error',
  WARN: 'warn',
  INFO: 'info',
  HTTP: 'http',
  VERBOSE: 'verbose',
  DEBUG: 'debug',
  SILLY: 'silly',
};

// 日志工具函数
export const logError = (error: Error, context?: any) => {
  logger.error({
    message: error.message,
    stack: error.stack,
    context,
  });
};

export const logPerformance = (operation: string, duration: number, metadata?: any) => {
  performanceLogger.info({
    operation,
    duration,
    ...metadata,
  });
};

export const logAudit = (action: string, userId: string, details: any) => {
  auditLogger.info({
    action,
    userId,
    timestamp: new Date(),
    ...details,
  });
};