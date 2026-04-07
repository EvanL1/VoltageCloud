import { Request, Response } from 'express';
import { s3Service } from '../services/s3.service';
import { cacheService, CacheKeyGenerator } from '../services/cache.service';
import { asyncHandler } from '../middleware/error.middleware';
import { NotFoundError, ValidationError } from '../middleware/error.middleware';
import { createLogger } from '../utils/logger';
import { ITelemetryData, IAggregatedData, AggregationPeriod, AggregationFunction } from '../models/interfaces/telemetry.interface';
import { format, startOfHour, startOfDay, startOfWeek, startOfMonth } from 'date-fns';

const logger = createLogger('TelemetryController');

export class TelemetryController {
  /**
   * 获取设备遥测数据
   */
  getDeviceTelemetry = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;
    const { 
      startTime, 
      endTime, 
      page = 1, 
      limit = 20,
      metrics
    } = req.query;

    const startDate = new Date(startTime as string);
    const endDate = new Date(endTime as string);
    const pageNum = parseInt(page as string);
    const limitNum = parseInt(limit as string);

    // 生成缓存键
    const cacheKey = `telemetry:${deviceId}:${format(startDate, 'yyyy-MM-dd')}:${format(endDate, 'yyyy-MM-dd')}:${pageNum}:${limitNum}`;
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
      // 从S3获取数据
      const allData = await s3Service.getDeviceTelemetryData(
        deviceId,
        startDate,
        endDate
      );

      // 过滤指定的指标
      let filteredData = allData;
      if (metrics && Array.isArray(metrics)) {
        filteredData = allData.map(data => ({
          ...data,
          metrics: Object.keys(data.metrics)
            .filter(key => (metrics as string[]).includes(key))
            .reduce((obj, key) => {
              obj[key] = data.metrics[key];
              return obj;
            }, {} as any)
        }));
      }

      // 分页
      const startIndex = (pageNum - 1) * limitNum;
      const paginatedData = filteredData.slice(startIndex, startIndex + limitNum);

      const response = {
        data: paginatedData,
        pagination: {
          page: pageNum,
          limit: limitNum,
          total: filteredData.length,
          pages: Math.ceil(filteredData.length / limitNum),
        },
        summary: {
          deviceId,
          startTime: startDate,
          endTime: endDate,
          totalRecords: filteredData.length,
          metrics: metrics || this.extractUniqueMetrics(allData),
        },
      };

      // 缓存结果
      await cacheService.set(cacheKey, response, 300); // 5分钟缓存

      res.json({
        success: true,
        data: response,
      });
    } catch (error) {
      logger.error('Failed to get telemetry data:', error);
      throw error;
    }
  });

  /**
   * 获取设备最新数据
   */
  getLatestTelemetry = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;

    // 尝试从缓存获取
    const cacheKey = CacheKeyGenerator.latestTelemetry(deviceId);
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
      const latestData = await s3Service.getLatestDeviceData(deviceId);

      if (!latestData) {
        throw new NotFoundError('No telemetry data found for device');
      }

      // 缓存结果（较短时间）
      await cacheService.set(cacheKey, latestData, 60); // 1分钟缓存

      res.json({
        success: true,
        data: latestData,
      });
    } catch (error) {
      logger.error('Failed to get latest telemetry:', error);
      throw error;
    }
  });

  /**
   * 批量获取多个设备的遥测数据
   */
  batchGetTelemetry = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceIds, startTime, endTime, metrics, aggregation } = req.body;

    const startDate = new Date(startTime);
    const endDate = new Date(endTime);

    try {
      // 获取所有设备的数据
      const deviceDataMap = await s3Service.getMultipleDevicesTelemetryData(
        deviceIds,
        startDate,
        endDate
      );

      // 处理聚合
      const result: any = {};
      
      for (const [deviceId, data] of deviceDataMap) {
        if (aggregation) {
          result[deviceId] = this.aggregateData(
            data,
            aggregation.period,
            aggregation.functions,
            metrics
          );
        } else {
          result[deviceId] = data;
        }
      }

      res.json({
        success: true,
        data: {
          devices: result,
          summary: {
            requestedDevices: deviceIds.length,
            returnedDevices: deviceDataMap.size,
            startTime: startDate,
            endTime: endDate,
            aggregation: aggregation || null,
          },
        },
      });
    } catch (error) {
      logger.error('Failed to batch get telemetry:', error);
      throw error;
    }
  });

  /**
   * 获取聚合数据
   */
  getAggregatedTelemetry = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;
    const { 
      startTime, 
      endTime, 
      metric, 
      period, 
      function: aggFunction = 'AVG' 
    } = req.query;

    const startDate = new Date(startTime as string);
    const endDate = new Date(endTime as string);

    // 生成缓存键
    const cacheKey = CacheKeyGenerator.aggregation(
      deviceId,
      metric as string,
      period as string,
      format(startDate, 'yyyy-MM-dd')
    );
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
      // 获取原始数据
      const rawData = await s3Service.getDeviceTelemetryData(
        deviceId,
        startDate,
        endDate
      );

      // 执行聚合
      const aggregatedData = this.aggregateDataByMetric(
        rawData,
        metric as string,
        period as AggregationPeriod,
        [aggFunction as AggregationFunction]
      );

      const response = {
        deviceId,
        metric,
        period,
        function: aggFunction,
        data: aggregatedData,
        summary: {
          startTime: startDate,
          endTime: endDate,
          dataPoints: rawData.length,
          aggregatedPoints: aggregatedData.length,
        },
      };

      // 缓存结果
      await cacheService.set(cacheKey, response, 600); // 10分钟缓存

      res.json({
        success: true,
        data: response,
      });
    } catch (error) {
      logger.error('Failed to get aggregated telemetry:', error);
      throw error;
    }
  });

  /**
   * 导出遥测数据
   */
  exportTelemetry = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;
    const { startTime, endTime, format: exportFormat = 'CSV' } = req.query;

    const startDate = new Date(startTime as string);
    const endDate = new Date(endTime as string);

    try {
      // 获取数据
      const data = await s3Service.getDeviceTelemetryData(
        deviceId,
        startDate,
        endDate
      );

      // 根据格式导出
      switch (exportFormat) {
        case 'CSV':
          const csv = this.convertToCSV(data);
          res.setHeader('Content-Type', 'text/csv');
          res.setHeader('Content-Disposition', `attachment; filename="${deviceId}_telemetry_${format(startDate, 'yyyyMMdd')}_${format(endDate, 'yyyyMMdd')}.csv"`);
          res.send(csv);
          break;

        case 'JSON':
        default:
          res.setHeader('Content-Type', 'application/json');
          res.setHeader('Content-Disposition', `attachment; filename="${deviceId}_telemetry_${format(startDate, 'yyyyMMdd')}_${format(endDate, 'yyyyMMdd')}.json"`);
          res.json(data);
          break;
      }
    } catch (error) {
      logger.error('Failed to export telemetry:', error);
      throw error;
    }
  });

  /**
   * 获取实时数据流端点信息
   */
  getStreamEndpoint = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;

    // 返回WebSocket连接信息
    const protocol = req.secure ? 'wss' : 'ws';
    const host = req.get('host');
    
    res.json({
      success: true,
      data: {
        endpoint: `${protocol}://${host}/ws`,
        subscriptions: [
          `telemetry/${deviceId}`,
          `telemetry/${deviceId}/latest`,
          `telemetry/all`, // 订阅所有设备
        ],
        authentication: 'Include JWT token in connection query params or headers',
      },
    });
  });

  /**
   * 获取数据质量报告
   */
  getDataQuality = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;
    const { startTime, endTime } = req.query;

    const startDate = new Date(startTime as string);
    const endDate = new Date(endTime as string);

    try {
      const data = await s3Service.getDeviceTelemetryData(
        deviceId,
        startDate,
        endDate
      );

      const quality = this.analyzeDataQuality(data);

      res.json({
        success: true,
        data: {
          deviceId,
          period: {
            start: startDate,
            end: endDate,
          },
          quality,
        },
      });
    } catch (error) {
      logger.error('Failed to get data quality:', error);
      throw error;
    }
  });

  // 辅助方法

  /**
   * 提取唯一的指标名称
   */
  private extractUniqueMetrics(data: ITelemetryData[]): string[] {
    const metricsSet = new Set<string>();
    
    data.forEach(item => {
      Object.keys(item.metrics).forEach(metric => {
        metricsSet.add(metric);
      });
    });

    return Array.from(metricsSet);
  }

  /**
   * 聚合数据
   */
  private aggregateData(
    data: ITelemetryData[],
    period: AggregationPeriod,
    functions: AggregationFunction[],
    metrics?: string[]
  ): IAggregatedData[] {
    const aggregated: IAggregatedData[] = [];
    const targetMetrics = metrics || this.extractUniqueMetrics(data);

    targetMetrics.forEach(metric => {
      const metricData = data.filter(d => d.metrics[metric] !== undefined);
      const grouped = this.groupByPeriod(metricData, period);

      Object.entries(grouped).forEach(([periodKey, items]) => {
        const values = items.map(item => item.metrics[metric] as number);
        const aggregation = this.calculateAggregation(values, functions);

        aggregated.push({
          deviceId: data[0]?.deviceId || '',
          metric,
          period,
          startTime: new Date(periodKey),
          endTime: this.getEndTime(new Date(periodKey), period),
          values: aggregation,
        });
      });
    });

    return aggregated;
  }

  /**
   * 按指标聚合数据
   */
  private aggregateDataByMetric(
    data: ITelemetryData[],
    metric: string,
    period: AggregationPeriod,
    functions: AggregationFunction[]
  ): any[] {
    const metricData = data.filter(d => d.metrics[metric] !== undefined);
    const grouped = this.groupByPeriod(metricData, period);

    return Object.entries(grouped).map(([periodKey, items]) => {
      const values = items.map(item => item.metrics[metric] as number);
      const aggregation = this.calculateAggregation(values, functions);

      return {
        timestamp: new Date(periodKey),
        ...aggregation,
        count: items.length,
      };
    });
  }

  /**
   * 按时间段分组数据
   */
  private groupByPeriod(
    data: ITelemetryData[],
    period: AggregationPeriod
  ): Record<string, ITelemetryData[]> {
    const grouped: Record<string, ITelemetryData[]> = {};

    data.forEach(item => {
      let key: string;
      const date = new Date(item.timestamp);

      switch (period) {
        case AggregationPeriod.MINUTE:
          key = format(date, 'yyyy-MM-dd HH:mm:00');
          break;
        case AggregationPeriod.HOUR:
          key = format(startOfHour(date), 'yyyy-MM-dd HH:00:00');
          break;
        case AggregationPeriod.DAY:
          key = format(startOfDay(date), 'yyyy-MM-dd');
          break;
        case AggregationPeriod.WEEK:
          key = format(startOfWeek(date), 'yyyy-MM-dd');
          break;
        case AggregationPeriod.MONTH:
          key = format(startOfMonth(date), 'yyyy-MM');
          break;
        default:
          key = format(date, 'yyyy-MM-dd');
      }

      if (!grouped[key]) {
        grouped[key] = [];
      }
      grouped[key].push(item);
    });

    return grouped;
  }

  /**
   * 计算聚合值
   */
  private calculateAggregation(
    values: number[],
    functions: AggregationFunction[]
  ): any {
    const result: any = {};

    if (values.length === 0) {
      functions.forEach(func => {
        result[func.toLowerCase()] = null;
      });
      return result;
    }

    functions.forEach(func => {
      switch (func) {
        case AggregationFunction.MIN:
          result.min = Math.min(...values);
          break;
        case AggregationFunction.MAX:
          result.max = Math.max(...values);
          break;
        case AggregationFunction.AVG:
          result.avg = values.reduce((a, b) => a + b, 0) / values.length;
          break;
        case AggregationFunction.SUM:
          result.sum = values.reduce((a, b) => a + b, 0);
          break;
        case AggregationFunction.COUNT:
          result.count = values.length;
          break;
        case AggregationFunction.STDDEV:
          const avg = values.reduce((a, b) => a + b, 0) / values.length;
          const variance = values.reduce((a, b) => a + Math.pow(b - avg, 2), 0) / values.length;
          result.stdDev = Math.sqrt(variance);
          break;
      }
    });

    return result;
  }

  /**
   * 获取时间段结束时间
   */
  private getEndTime(startTime: Date, period: AggregationPeriod): Date {
    const date = new Date(startTime);
    
    switch (period) {
      case AggregationPeriod.MINUTE:
        date.setMinutes(date.getMinutes() + 1);
        break;
      case AggregationPeriod.HOUR:
        date.setHours(date.getHours() + 1);
        break;
      case AggregationPeriod.DAY:
        date.setDate(date.getDate() + 1);
        break;
      case AggregationPeriod.WEEK:
        date.setDate(date.getDate() + 7);
        break;
      case AggregationPeriod.MONTH:
        date.setMonth(date.getMonth() + 1);
        break;
    }
    
    return date;
  }

  /**
   * 转换为CSV格式
   */
  private convertToCSV(data: ITelemetryData[]): string {
    if (data.length === 0) return '';

    // 获取所有唯一的指标键
    const allMetrics = this.extractUniqueMetrics(data);
    
    // 创建CSV头
    const headers = ['timestamp', 'deviceId', ...allMetrics];
    const csv = [headers.join(',')];

    // 添加数据行
    data.forEach(item => {
      const row = [
        item.timestamp.toISOString(),
        item.deviceId,
        ...allMetrics.map(metric => item.metrics[metric] || ''),
      ];
      csv.push(row.join(','));
    });

    return csv.join('\n');
  }

  /**
   * 分析数据质量
   */
  private analyzeDataQuality(data: ITelemetryData[]): any {
    if (data.length === 0) {
      return {
        totalRecords: 0,
        quality: 'NO_DATA',
      };
    }

    const metrics = this.extractUniqueMetrics(data);
    const timestamps = data.map(d => new Date(d.timestamp).getTime());
    timestamps.sort((a, b) => a - b);

    // 计算时间间隔
    const intervals: number[] = [];
    for (let i = 1; i < timestamps.length; i++) {
      intervals.push(timestamps[i] - timestamps[i - 1]);
    }

    const avgInterval = intervals.length > 0 
      ? intervals.reduce((a, b) => a + b, 0) / intervals.length 
      : 0;

    // 检查缺失值
    const missingValues: Record<string, number> = {};
    metrics.forEach(metric => {
      const missing = data.filter(d => d.metrics[metric] === undefined || d.metrics[metric] === null).length;
      if (missing > 0) {
        missingValues[metric] = missing;
      }
    });

    return {
      totalRecords: data.length,
      metrics: metrics.length,
      timeRange: {
        start: new Date(timestamps[0]),
        end: new Date(timestamps[timestamps.length - 1]),
        duration: timestamps[timestamps.length - 1] - timestamps[0],
      },
      sampling: {
        averageInterval: avgInterval,
        minInterval: Math.min(...intervals),
        maxInterval: Math.max(...intervals),
      },
      completeness: {
        overallPercentage: ((data.length - Object.values(missingValues).reduce((a, b) => a + b, 0)) / (data.length * metrics.length)) * 100,
        missingValues,
      },
      quality: this.determineQualityLevel(data, missingValues, avgInterval),
    };
  }

  /**
   * 确定数据质量级别
   */
  private determineQualityLevel(
    data: ITelemetryData[],
    missingValues: Record<string, number>,
    avgInterval: number
  ): string {
    const totalPossibleValues = data.length * this.extractUniqueMetrics(data).length;
    const totalMissing = Object.values(missingValues).reduce((a, b) => a + b, 0);
    const completenessRatio = (totalPossibleValues - totalMissing) / totalPossibleValues;

    if (completenessRatio >= 0.95 && avgInterval < 60000) { // 95%完整且间隔小于1分钟
      return 'EXCELLENT';
    } else if (completenessRatio >= 0.80) {
      return 'GOOD';
    } else if (completenessRatio >= 0.60) {
      return 'FAIR';
    } else {
      return 'POOR';
    }
  }
}

export const telemetryController = new TelemetryController();