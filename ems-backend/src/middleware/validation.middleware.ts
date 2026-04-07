import { Request, Response, NextFunction } from 'express';
import Joi, { Schema, ValidationError as JoiValidationError } from 'joi';
import { ValidationError } from './error.middleware';

export interface ValidationSchemas {
  body?: Schema;
  query?: Schema;
  params?: Schema;
  headers?: Schema;
}

/**
 * 创建验证中间件
 */
export const validate = (schemas: ValidationSchemas) => {
  return async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      // 验证各个部分
      if (schemas.body) {
        req.body = await schemas.body.validateAsync(req.body, { abortEarly: false });
      }

      if (schemas.query) {
        req.query = await schemas.query.validateAsync(req.query, { abortEarly: false });
      }

      if (schemas.params) {
        req.params = await schemas.params.validateAsync(req.params, { abortEarly: false });
      }

      if (schemas.headers) {
        const validatedHeaders = await schemas.headers.validateAsync(req.headers, { 
          abortEarly: false,
          allowUnknown: true 
        });
        Object.assign(req.headers, validatedHeaders);
      }

      next();
    } catch (error) {
      if (error instanceof JoiValidationError) {
        const details = error.details.map(detail => ({
          field: detail.path.join('.'),
          message: detail.message,
          type: detail.type,
        }));

        next(new ValidationError('Validation failed', details));
      } else {
        next(error);
      }
    }
  };
};

// 通用验证规则
export const commonValidations = {
  // ID验证
  id: Joi.string().alphanum().min(1).max(64),
  uuid: Joi.string().uuid(),
  deviceId: Joi.string().pattern(/^[a-zA-Z0-9_-]+$/).min(1).max(128),
  
  // 分页验证
  pagination: {
    page: Joi.number().integer().min(1).default(1),
    limit: Joi.number().integer().min(1).max(100).default(20),
    offset: Joi.number().integer().min(0),
  },
  
  // 排序验证
  sort: {
    orderBy: Joi.string().valid('createdAt', 'updatedAt', 'name', 'timestamp'),
    order: Joi.string().valid('ASC', 'DESC', 'asc', 'desc').default('DESC'),
  },
  
  // 时间范围验证
  dateRange: {
    startTime: Joi.date().iso().required(),
    endTime: Joi.date().iso().min(Joi.ref('startTime')).required(),
  },
  
  // 可选时间范围
  optionalDateRange: {
    startTime: Joi.date().iso(),
    endTime: Joi.date().iso().when('startTime', {
      is: Joi.exist(),
      then: Joi.date().min(Joi.ref('startTime')),
    }),
  },
};

// 设备相关验证模式
export const deviceValidations = {
  // 创建设备
  create: {
    body: Joi.object({
      thingName: Joi.string().pattern(/^[a-zA-Z0-9_-]+$/).min(1).max(128).required(),
      attributes: Joi.object({
        deviceType: Joi.string().required(),
        location: Joi.string(),
        firmware: Joi.string(),
        serialNumber: Joi.string(),
      }).unknown(true).required(),
      generateCertificate: Joi.boolean().default(true),
    }),
  },
  
  // 更新设备
  update: {
    params: Joi.object({
      deviceId: commonValidations.deviceId.required(),
    }),
    body: Joi.object({
      attributes: Joi.object().unknown(true).min(1).required(),
    }),
  },
  
  // 获取设备
  get: {
    params: Joi.object({
      deviceId: commonValidations.deviceId.required(),
    }),
  },
  
  // 设备列表
  list: {
    query: Joi.object({
      ...commonValidations.pagination,
      status: Joi.string().valid('ACTIVE', 'INACTIVE', 'MAINTENANCE', 'ERROR'),
      deviceType: Joi.string(),
      location: Joi.string(),
    }),
  },
  
  // 更新设备影子
  updateShadow: {
    params: Joi.object({
      deviceId: commonValidations.deviceId.required(),
    }),
    body: Joi.object({
      desired: Joi.object().unknown(true).required(),
    }),
  },
  
  // 发送命令
  sendCommand: {
    params: Joi.object({
      deviceId: commonValidations.deviceId.required(),
    }),
    body: Joi.object({
      command: Joi.string().required(),
      parameters: Joi.object().unknown(true),
      timeout: Joi.number().integer().min(1).max(300).default(60),
    }),
  },
};

// 遥测数据验证模式
export const telemetryValidations = {
  // 查询遥测数据
  query: {
    params: Joi.object({
      deviceId: commonValidations.deviceId.required(),
    }),
    query: Joi.object({
      ...commonValidations.dateRange,
      ...commonValidations.pagination,
      metrics: Joi.array().items(Joi.string()),
    }),
  },
  
  // 批量查询
  batchQuery: {
    body: Joi.object({
      deviceIds: Joi.array().items(commonValidations.deviceId).min(1).max(100).required(),
      ...commonValidations.dateRange,
      metrics: Joi.array().items(Joi.string()),
      aggregation: Joi.object({
        period: Joi.string().valid('MINUTE', 'HOUR', 'DAY', 'WEEK', 'MONTH'),
        functions: Joi.array().items(
          Joi.string().valid('MIN', 'MAX', 'AVG', 'SUM', 'COUNT', 'STDDEV')
        ),
      }),
    }),
  },
  
  // 获取最新数据
  latest: {
    params: Joi.object({
      deviceId: commonValidations.deviceId.required(),
    }),
  },
  
  // 聚合查询
  aggregate: {
    params: Joi.object({
      deviceId: commonValidations.deviceId.required(),
    }),
    query: Joi.object({
      ...commonValidations.dateRange,
      metric: Joi.string().required(),
      period: Joi.string().valid('HOUR', 'DAY', 'WEEK', 'MONTH').required(),
      function: Joi.string().valid('MIN', 'MAX', 'AVG', 'SUM', 'COUNT').default('AVG'),
    }),
  },
};

// 能源管理验证模式
export const energyValidations = {
  // 能源消耗
  consumption: {
    query: Joi.object({
      deviceId: commonValidations.deviceId,
      deviceIds: Joi.array().items(commonValidations.deviceId),
      ...commonValidations.dateRange,
      period: Joi.string().valid('HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR').required(),
      groupBy: Joi.string().valid('device', 'location', 'type'),
    }).or('deviceId', 'deviceIds'),
  },
  
  // 能效分析
  efficiency: {
    query: Joi.object({
      deviceId: commonValidations.deviceId.required(),
      ...commonValidations.dateRange,
      benchmarkType: Joi.string().valid('industry', 'historical', 'peer'),
    }),
  },
  
  // 成本分析
  cost: {
    query: Joi.object({
      deviceId: commonValidations.deviceId,
      deviceIds: Joi.array().items(commonValidations.deviceId),
      ...commonValidations.dateRange,
      tariffId: Joi.string(),
      currency: Joi.string().default('USD'),
    }).or('deviceId', 'deviceIds'),
  },
  
  // 预测
  forecast: {
    query: Joi.object({
      deviceId: commonValidations.deviceId.required(),
      horizon: Joi.string().valid('DAY', 'WEEK', 'MONTH', 'QUARTER', 'YEAR').required(),
      method: Joi.string().valid('ARIMA', 'LSTM', 'PROPHET').default('ARIMA'),
    }),
  },
};

// 报表验证模式
export const reportValidations = {
  // 生成报表
  generate: {
    body: Joi.object({
      type: Joi.string().valid('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUAL', 'CUSTOM').required(),
      ...commonValidations.dateRange,
      deviceIds: Joi.array().items(commonValidations.deviceId).min(1).required(),
      metrics: Joi.array().items(Joi.string()).min(1).required(),
      format: Joi.string().valid('JSON', 'CSV', 'EXCEL', 'PDF').default('JSON'),
      sections: Joi.array().items(
        Joi.string().valid('SUMMARY', 'CONSUMPTION', 'COST', 'EFFICIENCY', 'COMPARISON', 'FORECAST')
      ),
      email: Joi.string().email(),
    }),
  },
  
  // 获取报表
  get: {
    params: Joi.object({
      reportId: commonValidations.uuid.required(),
    }),
  },
  
  // 报表列表
  list: {
    query: Joi.object({
      ...commonValidations.pagination,
      type: Joi.string().valid('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUAL', 'CUSTOM'),
      ...commonValidations.optionalDateRange,
    }),
  },
};

// 认证验证模式
export const authValidations = {
  // 登录
  login: {
    body: Joi.object({
      email: Joi.string().email().required(),
      password: Joi.string().min(6).required(),
    }),
  },
  
  // 注册
  register: {
    body: Joi.object({
      email: Joi.string().email().required(),
      password: Joi.string().min(8).pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/).required(),
      name: Joi.string().min(2).max(100).required(),
      role: Joi.string().valid('OPERATOR', 'VIEWER').default('VIEWER'),
    }),
  },
  
  // 刷新令牌
  refresh: {
    body: Joi.object({
      refreshToken: Joi.string().required(),
    }),
  },
  
  // 修改密码
  changePassword: {
    body: Joi.object({
      currentPassword: Joi.string().required(),
      newPassword: Joi.string().min(8).pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/).required(),
    }),
  },
  
  // 重置密码
  resetPassword: {
    body: Joi.object({
      token: Joi.string().required(),
      newPassword: Joi.string().min(8).pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/).required(),
    }),
  },
};

// 用户管理验证模式
export const userValidations = {
  // 创建用户
  create: {
    body: Joi.object({
      email: Joi.string().email().required(),
      password: Joi.string().min(8).required(),
      name: Joi.string().min(2).max(100).required(),
      role: Joi.string().valid('ADMIN', 'OPERATOR', 'VIEWER', 'API_USER').required(),
      permissions: Joi.array().items(Joi.string()),
    }),
  },
  
  // 更新用户
  update: {
    params: Joi.object({
      userId: commonValidations.uuid.required(),
    }),
    body: Joi.object({
      name: Joi.string().min(2).max(100),
      role: Joi.string().valid('ADMIN', 'OPERATOR', 'VIEWER', 'API_USER'),
      permissions: Joi.array().items(Joi.string()),
      active: Joi.boolean(),
    }).min(1),
  },
  
  // 用户列表
  list: {
    query: Joi.object({
      ...commonValidations.pagination,
      role: Joi.string().valid('ADMIN', 'OPERATOR', 'VIEWER', 'API_USER'),
      active: Joi.boolean(),
      search: Joi.string(),
    }),
  },
};