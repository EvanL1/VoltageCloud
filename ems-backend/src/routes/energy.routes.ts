import { Router } from 'express';
import { energyController } from '../controllers/energy.controller';
import { authenticate, authorize } from '../middleware/auth.middleware';
import { validate, energyValidations } from '../middleware/validation.middleware';

const router = Router();

// 所有能源路由都需要认证
router.use(authenticate);

// 能源消耗
router.get(
  '/consumption',
  authorize('energy:read'),
  validate(energyValidations.consumption),
  energyController.getEnergyConsumption
);

// 能效分析
router.get(
  '/efficiency',
  authorize('energy:read'),
  validate(energyValidations.efficiency),
  energyController.getEnergyEfficiency
);

// 成本分析
router.get(
  '/cost',
  authorize('energy:read'),
  validate(energyValidations.cost),
  energyController.getEnergyCost
);

// 能源预测
router.get(
  '/forecast',
  authorize('energy:read'),
  validate(energyValidations.forecast),
  energyController.getEnergyForecast
);

// 优化建议
router.get(
  '/devices/:deviceId/optimization',
  authorize('energy:read'),
  energyController.getOptimizationSuggestions
);

// 能源仪表板
router.get(
  '/dashboard',
  authorize('energy:read'),
  energyController.getEnergyDashboard
);

export default router;