import { Router } from 'express';
import { telemetryController } from '../controllers/telemetry.controller';
import { authenticate, authorize } from '../middleware/auth.middleware';
import { validate, telemetryValidations } from '../middleware/validation.middleware';

const router = Router();

// 所有遥测路由都需要认证
router.use(authenticate);

// 获取设备遥测数据
router.get(
  '/:deviceId',
  authorize('telemetry:read'),
  validate(telemetryValidations.query),
  telemetryController.getDeviceTelemetry
);

// 获取最新数据
router.get(
  '/:deviceId/latest',
  authorize('telemetry:read'),
  validate(telemetryValidations.latest),
  telemetryController.getLatestTelemetry
);

// 获取聚合数据
router.get(
  '/:deviceId/aggregate',
  authorize('telemetry:read'),
  validate(telemetryValidations.aggregate),
  telemetryController.getAggregatedTelemetry
);

// 导出数据
router.get(
  '/:deviceId/export',
  authorize('telemetry:read'),
  telemetryController.exportTelemetry
);

// 获取数据质量报告
router.get(
  '/:deviceId/quality',
  authorize('telemetry:read'),
  telemetryController.getDataQuality
);

// 获取实时数据流端点
router.get(
  '/:deviceId/stream',
  authorize('telemetry:read'),
  telemetryController.getStreamEndpoint
);

// 批量查询
router.post(
  '/batch',
  authorize('telemetry:read'),
  validate(telemetryValidations.batchQuery),
  telemetryController.batchGetTelemetry
);

export default router;