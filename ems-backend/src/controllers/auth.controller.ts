import { Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import { asyncHandler } from '../middleware/error.middleware';
import { generateToken, generateRefreshToken, UserRole } from '../middleware/auth.middleware';
import { createLogger } from '../utils/logger';

const logger = createLogger('AuthController');

// 临时用户存储（实际应使用数据库）
const users = [
  {
    id: '1',
    email: 'admin@example.com',
    password: '$2a$10$XkH9z0x5P.8WJvEZMqrqLOhXjgDdXS0UHGX.6DMBpH6KbDW9hFZXi', // password: admin123
    name: 'Admin User',
    role: UserRole.ADMIN,
  },
  {
    id: '2',
    email: 'operator@example.com',
    password: '$2a$10$XkH9z0x5P.8WJvEZMqrqLOhXjgDdXS0UHGX.6DMBpH6KbDW9hFZXi', // password: admin123
    name: 'Operator User',
    role: UserRole.OPERATOR,
  },
  {
    id: '3',
    email: 'viewer@example.com',
    password: '$2a$10$XkH9z0x5P.8WJvEZMqrqLOhXjgDdXS0UHGX.6DMBpH6KbDW9hFZXi', // password: admin123
    name: 'Viewer User',
    role: UserRole.VIEWER,
  },
];

export class AuthController {
  /**
   * 用户登录
   */
  login = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { email, password } = req.body;

    // 查找用户
    const user = users.find(u => u.email === email);
    
    if (!user) {
      res.status(401).json({
        success: false,
        error: 'Invalid credentials',
      });
      return;
    }

    // 验证密码
    const isPasswordValid = await bcrypt.compare(password, user.password);
    
    if (!isPasswordValid) {
      res.status(401).json({
        success: false,
        error: 'Invalid credentials',
      });
      return;
    }

    // 生成token
    const token = generateToken({
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
    });

    const refreshToken = generateRefreshToken(user.id);

    logger.info(`User logged in: ${user.email}`);

    res.json({
      success: true,
      data: {
        user: {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role,
        },
        token,
        refreshToken,
        expiresIn: '7d',
      },
    });
  });

  /**
   * 获取当前用户信息
   */
  getCurrentUser = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const userId = req.user!.id;
    
    const user = users.find(u => u.id === userId);
    
    if (!user) {
      res.status(404).json({
        success: false,
        error: 'User not found',
      });
      return;
    }

    res.json({
      success: true,
      data: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
      },
    });
  });

  /**
   * 登出
   */
  logout = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    // 在实际应用中，这里应该使token失效
    logger.info(`User logged out: ${req.user!.email}`);

    res.json({
      success: true,
      message: 'Logged out successfully',
    });
  });

  /**
   * 修改密码
   */
  changePassword = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { currentPassword, newPassword } = req.body;
    const userId = req.user!.id;

    const user = users.find(u => u.id === userId);
    
    if (!user) {
      res.status(404).json({
        success: false,
        error: 'User not found',
      });
      return;
    }

    // 验证当前密码
    const isPasswordValid = await bcrypt.compare(currentPassword, user.password);
    
    if (!isPasswordValid) {
      res.status(401).json({
        success: false,
        error: 'Current password is incorrect',
      });
      return;
    }

    // 更新密码（实际应更新数据库）
    const hashedPassword = await bcrypt.hash(newPassword, 10);
    user.password = hashedPassword;

    logger.info(`Password changed for user: ${user.email}`);

    res.json({
      success: true,
      message: 'Password changed successfully',
    });
  });
}

export const authController = new AuthController();