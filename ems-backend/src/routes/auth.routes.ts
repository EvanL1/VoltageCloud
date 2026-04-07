import { Router } from 'express';
import { authController } from '../controllers/auth.controller';
import { authenticate, refreshToken } from '../middleware/auth.middleware';
import { validate, authValidations } from '../middleware/validation.middleware';

const router = Router();

// 公开路由
router.post(
  '/login',
  validate(authValidations.login),
  authController.login
);

// 刷新令牌
router.post(
  '/refresh',
  validate(authValidations.refresh),
  refreshToken
);

// 需要认证的路由
router.get(
  '/me',
  authenticate,
  authController.getCurrentUser
);

router.post(
  '/logout',
  authenticate,
  authController.logout
);

router.post(
  '/change-password',
  authenticate,
  validate(authValidations.changePassword),
  authController.changePassword
);

export default router;