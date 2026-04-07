import { Router } from 'express';
import { deviceController } from '../controllers/device.controller';
import { authenticate, authorize } from '../middleware/auth.middleware';
import { validate, deviceValidations } from '../middleware/validation.middleware';

const router = Router();

// 所有设备路由都需要认证
router.use(authenticate);

// 设备列表
router.get(
  '/',
  authorize('devices:read'),
  validate(deviceValidations.list),
  deviceController.listDevices
);

// 设备统计
router.get(
  '/stats',
  authorize('devices:read'),
  deviceController.getDeviceStats
);

// 获取设备详情
router.get(
  '/:deviceId',
  authorize('devices:read'),
  validate(deviceValidations.get),
  deviceController.getDevice
);

// 获取设备影子
router.get(
  '/:deviceId/shadow',
  authorize('devices:read'),
  validate(deviceValidations.get),
  deviceController.getDeviceShadow
);

// 创建设备
router.post(
  '/',
  authorize('devices:write'),
  validate(deviceValidations.create),
  deviceController.createDevice
);

// 更新设备
router.put(
  '/:deviceId',
  authorize('devices:write'),
  validate(deviceValidations.update),
  deviceController.updateDevice
);

// 更新设备影子
router.put(
  '/:deviceId/shadow',
  authorize('devices:write'),
  validate(deviceValidations.updateShadow),
  deviceController.updateDeviceShadow
);

// 发送命令到设备
router.post(
  '/:deviceId/command',
  authorize('commands:execute'),
  validate(deviceValidations.sendCommand),
  deviceController.sendCommand
);

// 批量更新设备
router.post(
  '/batch/update',
  authorize('devices:write'),
  deviceController.batchUpdateDevices
);

// 删除设备
router.delete(
  '/:deviceId',
  authorize('devices:write'),
  validate(deviceValidations.get),
  deviceController.deleteDevice
);

export default router;