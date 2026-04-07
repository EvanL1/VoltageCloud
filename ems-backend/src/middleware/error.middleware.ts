import { Request, Response, NextFunction } from 'express';
import { createLogger, logError } from '../utils/logger';
import { appConfig } from '../config/app.config';

const logger = createLogger('ErrorMiddleware');

// 自定义错误类
export class AppError extends Error {
  statusCode: number;
  isOperational: boolean;
  code?: string;
  details?: any;

  constructor(
    message: string,
    statusCode: number = 500,
    isOperational: boolean = true,
    code?: string,
    details?: any
  ) {
    super(message);
    this.statusCode = statusCode;
    this.isOperational = isOperational;
    this.code = code;
    this.details = details;

    Error.captureStackTrace(this, this.constructor);
  }
}

// 常见错误类
export class ValidationError extends AppError {
  constructor(message: string, details?: any) {
    super(message, 400, true, 'VALIDATION_ERROR', details);
  }
}

export class AuthenticationError extends AppError {
  constructor(message: string = 'Authentication failed') {
    super(message, 401, true, 'AUTHENTICATION_ERROR');
  }
}

export class AuthorizationError extends AppError {
  constructor(message: string = 'Access denied') {
    super(message, 403, true, 'AUTHORIZATION_ERROR');
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string = 'Resource') {
    super(`${resource} not found`, 404, true, 'NOT_FOUND');
  }
}

export class ConflictError extends AppError {
  constructor(message: string) {
    super(message, 409, true, 'CONFLICT_ERROR');
  }
}

export class RateLimitError extends AppError {
  constructor(message: string = 'Too many requests') {
    super(message, 429, true, 'RATE_LIMIT_ERROR');
  }
}

export class ExternalServiceError extends AppError {
  constructor(service: string, originalError?: any) {
    super(`External service error: ${service}`, 503, true, 'EXTERNAL_SERVICE_ERROR', {
      service,
      originalError: originalError?.message || originalError,
    });
  }
}

/**
 * 异步错误捕获器
 */
export const asyncHandler = (fn: Function) => {
  return (req: Request, res: Response, next: NextFunction) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
};

/**
 * 404错误处理
 */
export const notFoundHandler = (
  req: Request,
  res: Response,
  next: NextFunction
): void => {
  const error = new NotFoundError(`Route ${req.originalUrl}`);
  next(error);
};

/**
 * 全局错误处理中间件
 */
export const errorHandler = (
  err: Error | AppError,
  req: Request,
  res: Response,
  next: NextFunction
): void => {
  let error = err;

  // 如果不是AppError实例，转换为AppError
  if (!(error instanceof AppError)) {
    const statusCode = (error as any).statusCode || 500;
    const message = error.message || 'Internal server error';
    error = new AppError(message, statusCode, false);
  }

  const appError = error as AppError;

  // 记录错误
  if (appError.statusCode >= 500) {
    logError(error, {
      url: req.url,
      method: req.method,
      ip: req.ip,
      userId: req.user?.id,
    });
  } else {
    logger.warn(`${appError.statusCode} - ${appError.message}`, {
      url: req.url,
      method: req.method,
      ip: req.ip,
      userId: req.user?.id,
    });
  }

  // 发送错误响应
  const response: any = {
    success: false,
    error: {
      message: appError.message,
      code: appError.code,
    },
  };

  // 开发环境下包含更多错误信息
  if (appConfig.server.env === 'development') {
    response.error.statusCode = appError.statusCode;
    response.error.details = appError.details;
    response.error.stack = appError.stack;
  }

  // 添加请求ID（如果有）
  if ((req as any).id) {
    response.requestId = (req as any).id;
  }

  res.status(appError.statusCode).json(response);
};

/**
 * 处理未捕获的Promise拒绝
 */
process.on('unhandledRejection', (reason: any, promise: Promise<any>) => {
  logger.error('Unhandled Promise Rejection:', {
    reason: reason?.message || reason,
    stack: reason?.stack,
  });

  // 在生产环境中，可能需要优雅地关闭服务器
  if (appConfig.server.env === 'production') {
    // 给一些时间来记录错误
    setTimeout(() => {
      process.exit(1);
    }, 1000);
  }
});

/**
 * 处理未捕获的异常
 */
process.on('uncaughtException', (error: Error) => {
  logger.error('Uncaught Exception:', {
    message: error.message,
    stack: error.stack,
  });

  // 在生产环境中，需要优雅地关闭服务器
  if (appConfig.server.env === 'production') {
    // 给一些时间来记录错误
    setTimeout(() => {
      process.exit(1);
    }, 1000);
  }
});

/**
 * 验证错误处理
 */
export const handleValidationError = (errors: any[]): ValidationError => {
  const formattedErrors = errors.map(err => ({
    field: err.param || err.path,
    message: err.msg || err.message,
    value: err.value,
  }));

  return new ValidationError('Validation failed', formattedErrors);
};

/**
 * MongoDB/DynamoDB错误处理
 */
export const handleDatabaseError = (error: any): AppError => {
  // 重复键错误
  if (error.code === 11000 || error.name === 'ConditionalCheckFailedException') {
    const field = Object.keys(error.keyPattern || {})[0] || 'field';
    return new ConflictError(`Duplicate ${field} value`);
  }

  // 验证错误
  if (error.name === 'ValidationError') {
    return new ValidationError('Database validation failed', error.errors);
  }

  // 其他数据库错误
  return new AppError('Database operation failed', 500, true, 'DATABASE_ERROR');
};

/**
 * AWS服务错误处理
 */
export const handleAWSError = (error: any, service: string): AppError => {
  const statusCode = error.$metadata?.httpStatusCode || 500;
  const errorCode = error.name || error.Code || 'UnknownError';
  const message = error.message || `AWS ${service} error`;

  // 处理常见的AWS错误
  switch (errorCode) {
    case 'ResourceNotFoundException':
      return new NotFoundError(`${service} resource`);
    case 'AccessDeniedException':
      return new AuthorizationError(`Access denied to ${service}`);
    case 'ThrottlingException':
    case 'TooManyRequestsException':
      return new RateLimitError(`${service} rate limit exceeded`);
    case 'ValidationException':
      return new ValidationError(`${service} validation failed`, error);
    default:
      return new ExternalServiceError(service, error);
  }
};