import { Request, Response } from 'express';
import { iotService } from '../services/iot.service';
import { cacheService, CacheKeyGenerator } from '../services/cache.service';
import { asyncHandler } from '../middleware/error.middleware';
import { NotFoundError, handleAWSError } from '../middleware/error.middleware';
import { createLogger, logAudit } from '../utils/logger';

const logger = createLogger('DeviceController');

export class DeviceController {
  /**
   * 获取设备列表
   */
  listDevices = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { page = 1, limit = 20, status, deviceType, location } = req.query;
    const pageNum = parseInt(page as string);
    const limitNum = parseInt(limit as string);

    // 尝试从缓存获取
    const cacheKey = CacheKeyGenerator.deviceList(pageNum, limitNum);
    const cached = await cacheService.get(cacheKey);
    
    if (cached) {
      res.json({
        success: true,
        data: cached,
        cached: true,
      });
      return;
    }

    try {
      // 从IoT Core获取设备列表
      const result = await iotService.listDevices(limitNum);
      
      // 应用过滤
      let devices = result.devices;
      if (status) {
        devices = devices.filter(d => d.status === status);
      }
      if (deviceType) {
        devices = devices.filter(d => d.attributes.deviceType === deviceType);
      }
      if (location) {
        devices = devices.filter(d => d.attributes.location === location);
      }

      // 分页处理
      const startIndex = (pageNum - 1) * limitNum;
      const paginatedDevices = devices.slice(startIndex, startIndex + limitNum);

      const response = {
        devices: paginatedDevices,
        pagination: {
          page: pageNum,
          limit: limitNum,
          total: devices.length,
          pages: Math.ceil(devices.length / limitNum),
        },
        filters: {
          status: status || null,
          deviceType: deviceType || null,
          location: location || null,
        },
      };

      // 缓存结果
      await cacheService.set(cacheKey, response, 300); // 5分钟缓存

      res.json({
        success: true,
        data: response,
      });
    } catch (error) {
      throw handleAWSError(error, 'IoT');
    }
  });

  /**
   * 获取设备详情
   */
  getDevice = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;

    // 尝试从缓存获取
    const cacheKey = CacheKeyGenerator.device(deviceId);
    const cached = await cacheService.get(cacheKey);
    
    if (cached) {
      res.json({
        success: true,
        data: cached,
        cached: true,
      });
      return;
    }

    try {
      const device = await iotService.getDeviceDetails(deviceId);
      
      if (!device) {
        throw new NotFoundError('Device');
      }

      // 缓存结果
      await cacheService.set(cacheKey, device, 300);

      res.json({
        success: true,
        data: device,
      });
    } catch (error) {
      throw handleAWSError(error, 'IoT');
    }
  });

  /**
   * 创建设备
   */
  createDevice = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { thingName, attributes, generateCertificate } = req.body;

    try {
      const result = await iotService.createDevice(
        thingName,
        attributes,
        generateCertificate
      );

      // 清除设备列表缓存
      await cacheService.deletePattern('devices:list:*');

      // 记录审计日志
      logAudit('device.create', req.user!.id, {
        deviceId: result.device.deviceId,
        thingName,
      });

      res.status(201).json({
        success: true,
        data: result,
      });
    } catch (error) {
      throw handleAWSError(error, 'IoT');
    }
  });

  /**
   * 更新设备属性
   */
  updateDevice = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;
    const { attributes } = req.body;

    try {
      await iotService.updateDeviceAttributes(deviceId, attributes);

      // 清除相关缓存
      await cacheService.delete(CacheKeyGenerator.device(deviceId));
      await cacheService.deletePattern('devices:list:*');

      // 记录审计日志
      logAudit('device.update', req.user!.id, {
        deviceId,
        attributes,
      });

      res.json({
        success: true,
        message: 'Device updated successfully',
      });
    } catch (error) {
      throw handleAWSError(error, 'IoT');
    }
  });

  /**
   * 删除设备
   */
  deleteDevice = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;

    try {
      await iotService.deleteDevice(deviceId);

      // 清除相关缓存
      await cacheService.delete(CacheKeyGenerator.device(deviceId));
      await cacheService.delete(CacheKeyGenerator.deviceShadow(deviceId));
      await cacheService.deletePattern('devices:list:*');
      await cacheService.deletePattern(`telemetry:${deviceId}:*`);

      // 记录审计日志
      logAudit('device.delete', req.user!.id, { deviceId });

      res.json({
        success: true,
        message: 'Device deleted successfully',
      });
    } catch (error) {
      throw handleAWSError(error, 'IoT');
    }
  });

  /**
   * 获取设备影子
   */
  getDeviceShadow = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;

    // 尝试从缓存获取
    const cacheKey = CacheKeyGenerator.deviceShadow(deviceId);
    const cached = await cacheService.get(cacheKey);
    
    if (cached) {
      res.json({
        success: true,
        data: cached,
        cached: true,
      });
      return;
    }

    try {
      const shadow = await iotService.getDeviceShadow(deviceId);
      
      if (!shadow) {
        throw new NotFoundError('Device shadow');
      }

      // 缓存结果（较短时间，因为影子数据变化频繁）
      await cacheService.set(cacheKey, shadow, 60); // 1分钟缓存

      res.json({
        success: true,
        data: shadow,
      });
    } catch (error) {
      throw handleAWSError(error, 'IoT');
    }
  });

  /**
   * 更新设备影子
   */
  updateDeviceShadow = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;
    const { desired } = req.body;

    try {
      const shadow = await iotService.updateDeviceShadow(deviceId, desired);

      // 清除影子缓存
      await cacheService.delete(CacheKeyGenerator.deviceShadow(deviceId));

      // 记录审计日志
      logAudit('device.shadow.update', req.user!.id, {
        deviceId,
        desired,
      });

      res.json({
        success: true,
        data: shadow,
      });
    } catch (error) {
      throw handleAWSError(error, 'IoT');
    }
  });

  /**
   * 发送命令到设备
   */
  sendCommand = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;
    const { command, parameters, timeout } = req.body;

    try {
      await iotService.sendCommand(deviceId, command, parameters);

      // 记录审计日志
      logAudit('device.command.send', req.user!.id, {
        deviceId,
        command,
        parameters,
      });

      res.json({
        success: true,
        message: 'Command sent successfully',
        data: {
          deviceId,
          command,
          timestamp: new Date(),
          timeout,
        },
      });
    } catch (error) {
      throw handleAWSError(error, 'IoT');
    }
  });

  /**
   * 获取设备统计信息
   */
  getDeviceStats = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    try {
      // 获取所有设备
      const result = await iotService.listDevices(1000); // 获取更多设备用于统计
      const devices = result.devices;

      // 计算统计信息
      const stats = {
        total: devices.length,
        byStatus: {
          active: devices.filter(d => d.status === 'ACTIVE').length,
          inactive: devices.filter(d => d.status === 'INACTIVE').length,
          maintenance: devices.filter(d => d.status === 'MAINTENANCE').length,
          error: devices.filter(d => d.status === 'ERROR').length,
        },
        byConnection: {
          connected: devices.filter(d => d.connectionState === 'CONNECTED').length,
          disconnected: devices.filter(d => d.connectionState === 'DISCONNECTED').length,
          unknown: devices.filter(d => d.connectionState === 'UNKNOWN').length,
        },
        byType: devices.reduce((acc, device) => {
          const type = device.attributes.deviceType || 'unknown';
          acc[type] = (acc[type] || 0) + 1;
          return acc;
        }, {} as Record<string, number>),
        byLocation: devices.reduce((acc, device) => {
          const location = device.attributes.location || 'unknown';
          acc[location] = (acc[location] || 0) + 1;
          return acc;
        }, {} as Record<string, number>),
      };

      res.json({
        success: true,
        data: stats,
      });
    } catch (error) {
      throw handleAWSError(error, 'IoT');
    }
  });

  /**
   * 批量更新设备
   */
  batchUpdateDevices = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceIds, attributes } = req.body;

    const results = {
      successful: [] as string[],
      failed: [] as { deviceId: string; error: string }[],
    };

    // 并行更新设备
    const updatePromises = deviceIds.map(async (deviceId: string) => {
      try {
        await iotService.updateDeviceAttributes(deviceId, attributes);
        results.successful.push(deviceId);
        
        // 清除缓存
        await cacheService.delete(CacheKeyGenerator.device(deviceId));
      } catch (error) {
        results.failed.push({
          deviceId,
          error: error.message || 'Update failed',
        });
      }
    });

    await Promise.all(updatePromises);

    // 清除列表缓存
    await cacheService.deletePattern('devices:list:*');

    // 记录审计日志
    logAudit('device.batch.update', req.user!.id, {
      deviceIds,
      attributes,
      results,
    });

    res.json({
      success: true,
      data: results,
    });
  });
}

export const deviceController = new DeviceController();