import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import { appConfig } from '../config/app.config';
import { createLogger } from '../utils/logger';

const logger = createLogger('AuthMiddleware');

// 扩展Request接口
declare global {
  namespace Express {
    interface Request {
      user?: IAuthUser;
      token?: string;
    }
  }
}

export interface IAuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  permissions: string[];
  iat?: number;
  exp?: number;
}

export enum UserRole {
  ADMIN = 'ADMIN',
  OPERATOR = 'OPERATOR',
  VIEWER = 'VIEWER',
  API_USER = 'API_USER',
}

// 角色权限映射
const rolePermissions: Record<UserRole, string[]> = {
  [UserRole.ADMIN]: ['*'], // 所有权限
  [UserRole.OPERATOR]: [
    'devices:read',
    'devices:write',
    'telemetry:read',
    'energy:read',
    'reports:read',
    'commands:execute',
  ],
  [UserRole.VIEWER]: [
    'devices:read',
    'telemetry:read',
    'energy:read',
    'reports:read',
  ],
  [UserRole.API_USER]: [
    'devices:read',
    'telemetry:read',
    'api:access',
  ],
};

/**
 * JWT认证中间件
 */
export const authenticate = async (
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    // 从不同来源获取token
    const token = extractToken(req);

    if (!token) {
      res.status(401).json({
        success: false,
        error: 'No authentication token provided',
      });
      return;
    }

    // 验证token
    const decoded = jwt.verify(token, appConfig.jwt.secret) as IAuthUser;

    // 检查token是否过期
    if (decoded.exp && decoded.exp * 1000 < Date.now()) {
      res.status(401).json({
        success: false,
        error: 'Token has expired',
      });
      return;
    }

    // 添加权限
    decoded.permissions = rolePermissions[decoded.role] || [];

    // 将用户信息附加到请求对象
    req.user = decoded;
    req.token = token;

    next();
  } catch (error) {
    if (error instanceof jwt.JsonWebTokenError) {
      res.status(401).json({
        success: false,
        error: 'Invalid authentication token',
      });
      return;
    }

    logger.error('Authentication error:', error);
    res.status(500).json({
      success: false,
      error: 'Authentication failed',
    });
  }
};

/**
 * 权限检查中间件
 */
export const authorize = (...requiredPermissions: string[]) => {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user) {
      res.status(401).json({
        success: false,
        error: 'Authentication required',
      });
      return;
    }

    const userPermissions = req.user.permissions || [];

    // 管理员拥有所有权限
    if (userPermissions.includes('*')) {
      next();
      return;
    }

    // 检查是否有所需权限
    const hasPermission = requiredPermissions.some(permission =>
      userPermissions.includes(permission)
    );

    if (!hasPermission) {
      logger.warn(
        `User ${req.user.id} attempted to access resource without permission: ${requiredPermissions.join(', ')}`
      );
      res.status(403).json({
        success: false,
        error: 'Insufficient permissions',
        required: requiredPermissions,
      });
      return;
    }

    next();
  };
};

/**
 * 角色检查中间件
 */
export const requireRole = (...roles: UserRole[]) => {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user) {
      res.status(401).json({
        success: false,
        error: 'Authentication required',
      });
      return;
    }

    if (!roles.includes(req.user.role)) {
      res.status(403).json({
        success: false,
        error: 'Insufficient role privileges',
        required: roles,
        current: req.user.role,
      });
      return;
    }

    next();
  };
};

/**
 * API密钥认证中间件
 */
export const authenticateApiKey = async (
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> => {
  const apiKey = req.headers['x-api-key'] as string;

  if (!apiKey) {
    res.status(401).json({
      success: false,
      error: 'API key required',
    });
    return;
  }

  // TODO: 验证API密钥
  // 这里应该从数据库或缓存中验证API密钥
  // 临时实现
  if (apiKey === 'demo-api-key') {
    req.user = {
      id: 'api-user',
      email: 'api@example.com',
      name: 'API User',
      role: UserRole.API_USER,
      permissions: rolePermissions[UserRole.API_USER],
    };
    next();
  } else {
    res.status(401).json({
      success: false,
      error: 'Invalid API key',
    });
  }
};

/**
 * 可选认证中间件
 */
export const optionalAuth = async (
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const token = extractToken(req);

    if (token) {
      const decoded = jwt.verify(token, appConfig.jwt.secret) as IAuthUser;
      decoded.permissions = rolePermissions[decoded.role] || [];
      req.user = decoded;
      req.token = token;
    }

    next();
  } catch (error) {
    // 忽略错误，继续处理请求
    next();
  }
};

/**
 * 刷新令牌中间件
 */
export const refreshToken = async (
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const refreshToken = req.body.refreshToken || req.headers['x-refresh-token'];

    if (!refreshToken) {
      res.status(400).json({
        success: false,
        error: 'Refresh token required',
      });
      return;
    }

    // TODO: 验证刷新令牌并生成新的访问令牌
    // 这里应该验证刷新令牌的有效性
    // 临时实现
    const decoded = jwt.verify(refreshToken, appConfig.jwt.secret) as IAuthUser;

    // 生成新的访问令牌
    const newToken = jwt.sign(
      {
        id: decoded.id,
        email: decoded.email,
        name: decoded.name,
        role: decoded.role,
      },
      appConfig.jwt.secret,
      { expiresIn: appConfig.jwt.expiresIn }
    );

    res.json({
      success: true,
      token: newToken,
      expiresIn: appConfig.jwt.expiresIn,
    });
  } catch (error) {
    res.status(401).json({
      success: false,
      error: 'Invalid refresh token',
    });
  }
};

/**
 * 从请求中提取token
 */
function extractToken(req: Request): string | null {
  // 从Authorization header提取
  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    return authHeader.substring(7);
  }

  // 从cookie提取
  if (req.cookies && req.cookies.token) {
    return req.cookies.token;
  }

  // 从查询参数提取（不推荐用于生产环境）
  if (req.query.token && typeof req.query.token === 'string') {
    return req.query.token;
  }

  return null;
}

/**
 * 生成JWT token
 */
export function generateToken(user: Partial<IAuthUser>): string {
  const payload = {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
  };

  return jwt.sign(payload, appConfig.jwt.secret, {
    expiresIn: appConfig.jwt.expiresIn,
  });
}

/**
 * 生成刷新令牌
 */
export function generateRefreshToken(userId: string): string {
  return jwt.sign({ id: userId, type: 'refresh' }, appConfig.jwt.secret, {
    expiresIn: appConfig.jwt.refreshExpiresIn,
  });
}