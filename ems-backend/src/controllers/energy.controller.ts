import { Request, Response } from 'express';
import { s3Service } from '../services/s3.service';
import { cacheService, CacheKeyGenerator } from '../services/cache.service';
import { asyncHandler } from '../middleware/error.middleware';
import { createLogger } from '../utils/logger';
import { 
  IEnergyConsumption, 
  IEnergyEfficiency, 
  IEnergyCost,
  IEnergyForecast,
  EnergyUnit,
  TariffType,
  ForecastHorizon,
  Priority
} from '../models/interfaces/energy.interface';
import { AggregationPeriod } from '../models/interfaces/telemetry.interface';
import { format, startOfDay, endOfDay, subDays, addDays } from 'date-fns';

const logger = createLogger('EnergyController');

export class EnergyController {
  /**
   * 获取能源消耗数据
   */
  getEnergyConsumption = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { 
      deviceId, 
      deviceIds, 
      startTime, 
      endTime, 
      period,
      groupBy 
    } = req.query;

    const startDate = new Date(startTime as string);
    const endDate = new Date(endTime as string);

    // 确定要查询的设备列表
    const targetDeviceIds = deviceIds 
      ? (deviceIds as string).split(',') 
      : deviceId 
      ? [deviceId as string]
      : [];

    if (targetDeviceIds.length === 0) {
      res.status(400).json({
        success: false,
        error: 'At least one device ID is required',
      });
      return;
    }

    try {
      // 获取所有设备的遥测数据
      const deviceDataMap = await s3Service.getMultipleDevicesTelemetryData(
        targetDeviceIds,
        startDate,
        endDate
      );

      // 计算能源消耗
      const consumptionData: IEnergyConsumption[] = [];
      
      for (const [deviceId, telemetryData] of deviceDataMap) {
        const consumption = this.calculateEnergyConsumption(
          deviceId,
          telemetryData,
          period as AggregationPeriod
        );
        consumptionData.push(...consumption);
      }

      // 根据groupBy参数分组
      let groupedData = consumptionData;
      if (groupBy) {
        groupedData = this.groupConsumptionData(consumptionData, groupBy as string);
      }

      // 计算总体统计
      const summary = this.calculateConsumptionSummary(consumptionData);

      res.json({
        success: true,
        data: {
          consumption: groupedData,
          summary,
          parameters: {
            devices: targetDeviceIds,
            period: { start: startDate, end: endDate },
            aggregation: period,
            groupBy: groupBy || null,
          },
        },
      });
    } catch (error) {
      logger.error('Failed to get energy consumption:', error);
      throw error;
    }
  });

  /**
   * 获取能效分析
   */
  getEnergyEfficiency = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId, startTime, endTime, benchmarkType = 'industry' } = req.query;

    const startDate = new Date(startTime as string);
    const endDate = new Date(endTime as string);

    // 缓存键
    const cacheKey = CacheKeyGenerator.energy(
      'efficiency',
      deviceId as string,
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
      // 获取设备数据
      const telemetryData = await s3Service.getDeviceTelemetryData(
        deviceId as string,
        startDate,
        endDate
      );

      // 计算能效指标
      const efficiency = this.calculateEnergyEfficiency(
        deviceId as string,
        telemetryData,
        benchmarkType as string
      );

      // 生成建议
      const recommendations = this.generateEfficiencyRecommendations(efficiency);
      efficiency.recommendations = recommendations;

      // 缓存结果
      await cacheService.set(cacheKey, efficiency, 1800); // 30分钟缓存

      res.json({
        success: true,
        data: efficiency,
      });
    } catch (error) {
      logger.error('Failed to get energy efficiency:', error);
      throw error;
    }
  });

  /**
   * 获取能源成本分析
   */
  getEnergyCost = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { 
      deviceId, 
      deviceIds, 
      startTime, 
      endTime, 
      tariffId = 'default',
      currency = 'USD' 
    } = req.query;

    const startDate = new Date(startTime as string);
    const endDate = new Date(endTime as string);

    const targetDeviceIds = deviceIds 
      ? (deviceIds as string).split(',') 
      : deviceId 
      ? [deviceId as string]
      : [];

    try {
      // 获取电费费率（这里使用模拟数据，实际应从数据库获取）
      const tariff = this.getTariffStructure(tariffId as string);

      // 获取能源消耗数据
      const deviceDataMap = await s3Service.getMultipleDevicesTelemetryData(
        targetDeviceIds,
        startDate,
        endDate
      );

      // 计算成本
      const costData: IEnergyCost[] = [];
      
      for (const [deviceId, telemetryData] of deviceDataMap) {
        const costs = this.calculateEnergyCost(
          deviceId,
          telemetryData,
          tariff,
          currency as string
        );
        costData.push(...costs);
      }

      // 计算总成本和分析
      const analysis = this.analyzeCosts(costData);

      res.json({
        success: true,
        data: {
          costs: costData,
          analysis,
          tariff: {
            id: tariffId,
            structure: tariff,
          },
          currency,
        },
      });
    } catch (error) {
      logger.error('Failed to get energy cost:', error);
      throw error;
    }
  });

  /**
   * 获取能源预测
   */
  getEnergyForecast = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId, horizon, method = 'ARIMA' } = req.query;

    // 缓存键
    const cacheKey = `energy:forecast:${deviceId}:${horizon}:${method}`;
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
      // 获取历史数据用于预测
      const endDate = new Date();
      const startDate = this.getForecastHistoricalStartDate(horizon as ForecastHorizon);
      
      const historicalData = await s3Service.getDeviceTelemetryData(
        deviceId as string,
        startDate,
        endDate
      );

      // 执行预测
      const forecast = this.performEnergyForecast(
        deviceId as string,
        historicalData,
        horizon as ForecastHorizon,
        method as string
      );

      // 缓存结果
      await cacheService.set(cacheKey, forecast, 3600); // 1小时缓存

      res.json({
        success: true,
        data: forecast,
      });
    } catch (error) {
      logger.error('Failed to get energy forecast:', error);
      throw error;
    }
  });

  /**
   * 获取能源优化建议
   */
  getOptimizationSuggestions = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceId } = req.params;

    try {
      // 获取最近30天的数据
      const endDate = new Date();
      const startDate = subDays(endDate, 30);
      
      const telemetryData = await s3Service.getDeviceTelemetryData(
        deviceId,
        startDate,
        endDate
      );

      // 分析数据并生成建议
      const analysis = {
        consumption: this.calculateEnergyConsumption(deviceId, telemetryData, AggregationPeriod.DAY),
        efficiency: this.calculateEnergyEfficiency(deviceId, telemetryData, 'historical'),
        patterns: this.analyzeUsagePatterns(telemetryData),
      };

      const suggestions = this.generateOptimizationSuggestions(analysis);

      res.json({
        success: true,
        data: {
          deviceId,
          period: { start: startDate, end: endDate },
          suggestions,
          potentialSavings: this.calculatePotentialSavings(suggestions),
        },
      });
    } catch (error) {
      logger.error('Failed to get optimization suggestions:', error);
      throw error;
    }
  });

  /**
   * 获取能源仪表板数据
   */
  getEnergyDashboard = asyncHandler(async (req: Request, res: Response): Promise<void> => {
    const { deviceIds, period = 'DAY' } = req.query;

    const endDate = new Date();
    const startDate = this.getPeriodStartDate(period as string);
    const targetDeviceIds = deviceIds ? (deviceIds as string).split(',') : [];

    try {
      // 获取所有设备数据
      const deviceDataMap = await s3Service.getMultipleDevicesTelemetryData(
        targetDeviceIds,
        startDate,
        endDate
      );

      // 计算各项指标
      const dashboard = {
        overview: {
          totalDevices: targetDeviceIds.length,
          activeDevices: deviceDataMap.size,
          period: { start: startDate, end: endDate },
        },
        consumption: {
          total: 0,
          byDevice: {} as Record<string, number>,
          trend: [] as any[],
        },
        efficiency: {
          average: 0,
          byDevice: {} as Record<string, number>,
        },
        cost: {
          total: 0,
          byDevice: {} as Record<string, number>,
          breakdown: {
            energy: 0,
            demand: 0,
            fixed: 0,
          },
        },
        alerts: [] as any[],
      };

      // 处理每个设备的数据
      for (const [deviceId, data] of deviceDataMap) {
        const consumption = this.calculateTotalConsumption(data);
        const efficiency = this.calculateAverageEfficiency(data);
        const cost = this.calculateSimpleCost(consumption);

        dashboard.consumption.total += consumption;
        dashboard.consumption.byDevice[deviceId] = consumption;
        dashboard.efficiency.byDevice[deviceId] = efficiency;
        dashboard.cost.total += cost;
        dashboard.cost.byDevice[deviceId] = cost;
      }

      // 计算平均效率
      const efficiencyValues = Object.values(dashboard.efficiency.byDevice);
      dashboard.efficiency.average = efficiencyValues.length > 0
        ? efficiencyValues.reduce((a, b) => a + b, 0) / efficiencyValues.length
        : 0;

      // 生成趋势数据
      dashboard.consumption.trend = this.generateTrendData(deviceDataMap, period as string);

      // 检查告警条件
      dashboard.alerts = this.checkEnergyAlerts(dashboard);

      res.json({
        success: true,
        data: dashboard,
      });
    } catch (error) {
      logger.error('Failed to get energy dashboard:', error);
      throw error;
    }
  });

  // 辅助方法

  /**
   * 计算能源消耗
   */
  private calculateEnergyConsumption(
    deviceId: string,
    telemetryData: any[],
    period: AggregationPeriod
  ): IEnergyConsumption[] {
    const consumptionData: IEnergyConsumption[] = [];
    
    // 按时间段分组数据
    const groupedData = this.groupDataByPeriod(telemetryData, period);

    Object.entries(groupedData).forEach(([periodKey, data]) => {
      const powerValues = data
        .map(d => d.metrics.power || 0)
        .filter(v => v > 0);

      if (powerValues.length === 0) return;

      // 计算消耗（简化计算）
      const avgPower = powerValues.reduce((a, b) => a + b, 0) / powerValues.length;
      const hours = this.getPeriodHours(period);
      const totalConsumption = (avgPower * hours) / 1000; // 转换为kWh

      // 假设峰谷电价
      const peakRatio = 0.6;
      const offPeakRatio = 0.4;

      const consumption: IEnergyConsumption = {
        deviceId,
        timestamp: new Date(periodKey),
        period,
        consumption: {
          total: totalConsumption,
          peak: totalConsumption * peakRatio,
          offPeak: totalConsumption * offPeakRatio,
          average: totalConsumption / hours,
        },
        cost: {
          total: totalConsumption * 0.15, // 假设均价0.15$/kWh
          peak: totalConsumption * peakRatio * 0.20,
          offPeak: totalConsumption * offPeakRatio * 0.10,
          currency: 'USD',
        },
        unit: EnergyUnit.KWH,
      };

      consumptionData.push(consumption);
    });

    return consumptionData;
  }

  /**
   * 计算能效
   */
  private calculateEnergyEfficiency(
    deviceId: string,
    telemetryData: any[],
    benchmarkType: string
  ): IEnergyEfficiency {
    // 计算各项指标
    const powerValues = telemetryData
      .map(d => d.metrics.power || 0)
      .filter(v => v > 0);

    const avgPower = powerValues.reduce((a, b) => a + b, 0) / powerValues.length;
    const powerFactorValues = telemetryData
      .map(d => d.metrics.powerFactor || 0.9)
      .filter(v => v > 0);
    
    const avgPowerFactor = powerFactorValues.reduce((a, b) => a + b, 0) / powerFactorValues.length;

    // 模拟效率计算
    const efficiency = avgPowerFactor * 0.95 * 100; // 简化的效率计算
    const loadFactor = 0.75; // 模拟负载率
    const utilizationRate = 0.82; // 模拟利用率

    // 基准值（模拟）
    const benchmarks = {
      industry: 85,
      target: 90,
      improvement: ((efficiency - 85) / 85) * 100,
    };

    return {
      deviceId,
      timestamp: new Date(),
      period: AggregationPeriod.DAY,
      metrics: {
        efficiency,
        powerFactor: avgPowerFactor,
        loadFactor,
        utilizationRate,
      },
      benchmarks,
    };
  }

  /**
   * 计算能源成本
   */
  private calculateEnergyCost(
    deviceId: string,
    telemetryData: any[],
    tariff: any,
    currency: string
  ): IEnergyCost[] {
    const costData: IEnergyCost[] = [];
    
    // 按天分组计算
    const dailyData = this.groupDataByPeriod(telemetryData, AggregationPeriod.DAY);

    Object.entries(dailyData).forEach(([date, data]) => {
      const totalEnergy = this.calculateDailyEnergy(data);
      
      // 根据费率结构计算成本
      const energyCost = totalEnergy * tariff.energyRate;
      const demandCost = tariff.demandRate * 10; // 模拟需求费用
      const fixedCost = tariff.fixedDaily;

      const cost: IEnergyCost = {
        deviceId,
        timestamp: new Date(date),
        period: AggregationPeriod.DAY,
        tariff: {
          name: tariff.name,
          type: tariff.type,
          rates: tariff.rates,
        },
        costs: {
          energy: energyCost,
          demand: demandCost,
          fixed: fixedCost,
          taxes: (energyCost + demandCost) * 0.08,
          total: energyCost + demandCost + fixedCost + (energyCost + demandCost) * 0.08,
        },
        currency,
      };

      costData.push(cost);
    });

    return costData;
  }

  /**
   * 执行能源预测
   */
  private performEnergyForecast(
    deviceId: string,
    historicalData: any[],
    horizon: ForecastHorizon,
    method: string
  ): IEnergyForecast {
    // 这里使用简单的移动平均作为预测（实际应使用ML模型）
    const dailyConsumption = this.calculateDailyConsumptionSeries(historicalData);
    const predictions = this.simpleMovingAverageForecast(dailyConsumption, horizon);

    return {
      deviceId,
      timestamp: new Date(),
      horizon,
      predictions,
      accuracy: {
        mape: 8.5, // 模拟值
        rmse: 12.3, // 模拟值
        confidence: 0.85,
      },
      factors: [
        { name: 'Seasonal Pattern', impact: 15, description: 'Summer cooling load increase' },
        { name: 'Weekend Effect', impact: -20, description: 'Reduced weekend consumption' },
        { name: 'Growth Trend', impact: 5, description: 'Gradual increase in baseline' },
      ],
      recommendations: [
        'Consider load shifting during peak hours',
        'Optimize HVAC schedules based on occupancy',
        'Implement demand response strategies',
      ],
    };
  }

  /**
   * 生成优化建议
   */
  private generateOptimizationSuggestions(analysis: any): any[] {
    const suggestions = [];

    // 基于效率的建议
    if (analysis.efficiency.metrics.efficiency < 85) {
      suggestions.push({
        id: 'eff-001',
        priority: Priority.HIGH,
        category: 'EQUIPMENT',
        title: 'Upgrade to High-Efficiency Equipment',
        description: 'Current efficiency is below industry standard. Consider upgrading to more efficient models.',
        potentialSavings: { energy: 15, cost: 2000, co2: 500 },
        implementationCost: 10000,
        paybackPeriod: 60,
      });
    }

    // 基于使用模式的建议
    if (analysis.patterns.peakUsageRatio > 0.7) {
      suggestions.push({
        id: 'opt-002',
        priority: Priority.MEDIUM,
        category: 'OPERATION',
        title: 'Implement Load Shifting',
        description: 'High peak usage detected. Shift non-critical loads to off-peak hours.',
        potentialSavings: { energy: 10, cost: 1500, co2: 300 },
        implementationCost: 2000,
        paybackPeriod: 16,
      });
    }

    return suggestions;
  }

  /**
   * 生成效率建议
   */
  private generateEfficiencyRecommendations(efficiency: IEnergyEfficiency): any[] {
    const recommendations = [];

    if (efficiency.metrics.powerFactor < 0.95) {
      recommendations.push({
        id: 'pf-001',
        priority: Priority.HIGH,
        category: 'EQUIPMENT',
        title: 'Install Power Factor Correction',
        description: `Power factor is ${efficiency.metrics.powerFactor.toFixed(2)}. Installing capacitor banks can improve it to 0.95+`,
        potentialSavings: { energy: 5, cost: 800, co2: 200 },
        implementationCost: 3000,
        paybackPeriod: 45,
        status: 'NEW',
      });
    }

    if (efficiency.metrics.efficiency < efficiency.benchmarks.industry) {
      recommendations.push({
        id: 'eff-002',
        priority: Priority.MEDIUM,
        category: 'MAINTENANCE',
        title: 'Schedule Preventive Maintenance',
        description: 'Efficiency is below industry benchmark. Regular maintenance can improve performance.',
        potentialSavings: { energy: 8, cost: 1200, co2: 350 },
        implementationCost: 500,
        paybackPeriod: 5,
        status: 'NEW',
      });
    }

    return recommendations;
  }

  // 工具方法

  private groupDataByPeriod(data: any[], period: AggregationPeriod): Record<string, any[]> {
    const grouped: Record<string, any[]> = {};

    data.forEach(item => {
      const key = this.getPeriodKey(new Date(item.timestamp), period);
      if (!grouped[key]) {
        grouped[key] = [];
      }
      grouped[key].push(item);
    });

    return grouped;
  }

  private getPeriodKey(date: Date, period: AggregationPeriod): string {
    switch (period) {
      case AggregationPeriod.HOUR:
        return format(date, 'yyyy-MM-dd HH:00');
      case AggregationPeriod.DAY:
        return format(date, 'yyyy-MM-dd');
      case AggregationPeriod.WEEK:
        return format(startOfDay(date), 'yyyy-[W]ww');
      case AggregationPeriod.MONTH:
        return format(date, 'yyyy-MM');
      case AggregationPeriod.YEAR:
        return format(date, 'yyyy');
      default:
        return format(date, 'yyyy-MM-dd');
    }
  }

  private getPeriodHours(period: AggregationPeriod): number {
    switch (period) {
      case AggregationPeriod.HOUR:
        return 1;
      case AggregationPeriod.DAY:
        return 24;
      case AggregationPeriod.WEEK:
        return 168;
      case AggregationPeriod.MONTH:
        return 720; // 平均
      case AggregationPeriod.YEAR:
        return 8760;
      default:
        return 24;
    }
  }

  private getTariffStructure(tariffId: string): any {
    // 模拟费率结构（实际应从数据库获取）
    return {
      name: 'Commercial Time-of-Use',
      type: TariffType.TIME_OF_USE,
      energyRate: 0.15, // $/kWh 平均
      demandRate: 15, // $/kW
      fixedDaily: 5, // $/day
      rates: [
        {
          name: 'Peak',
          rate: 0.20,
          unit: '$/kWh',
          timeSlots: [
            { startTime: '08:00', endTime: '22:00', days: [1, 2, 3, 4, 5] }
          ],
        },
        {
          name: 'Off-Peak',
          rate: 0.10,
          unit: '$/kWh',
          timeSlots: [
            { startTime: '22:00', endTime: '08:00', days: [1, 2, 3, 4, 5] },
            { startTime: '00:00', endTime: '23:59', days: [0, 6] }
          ],
        },
      ],
    };
  }

  private calculateDailyEnergy(data: any[]): number {
    const powerValues = data.map(d => d.metrics.power || 0);
    if (powerValues.length === 0) return 0;
    
    const avgPower = powerValues.reduce((a, b) => a + b, 0) / powerValues.length;
    return (avgPower * 24) / 1000; // kWh
  }

  private calculateTotalConsumption(data: any[]): number {
    return data
      .map(d => d.metrics.energy || 0)
      .reduce((a, b) => a + b, 0);
  }

  private calculateAverageEfficiency(data: any[]): number {
    const efficiencyValues = data
      .map(d => d.metrics.efficiency || d.metrics.powerFactor * 100 || 0)
      .filter(v => v > 0);
    
    return efficiencyValues.length > 0
      ? efficiencyValues.reduce((a, b) => a + b, 0) / efficiencyValues.length
      : 0;
  }

  private calculateSimpleCost(consumption: number): number {
    return consumption * 0.15; // $0.15/kWh 平均
  }

  private groupConsumptionData(data: IEnergyConsumption[], groupBy: string): any {
    // 实现分组逻辑
    return data;
  }

  private calculateConsumptionSummary(data: IEnergyConsumption[]): any {
    const total = data.reduce((sum, item) => sum + item.consumption.total, 0);
    const totalCost = data.reduce((sum, item) => sum + item.cost.total, 0);

    return {
      totalConsumption: total,
      totalCost,
      averageConsumption: data.length > 0 ? total / data.length : 0,
      peakConsumption: Math.max(...data.map(d => d.consumption.total)),
      periods: data.length,
    };
  }

  private analyzeCosts(costData: IEnergyCost[]): any {
    const totalCost = costData.reduce((sum, item) => sum + item.costs.total, 0);
    const energyCost = costData.reduce((sum, item) => sum + item.costs.energy, 0);
    const demandCost = costData.reduce((sum, item) => sum + item.costs.demand, 0);

    return {
      total: totalCost,
      breakdown: {
        energy: energyCost,
        demand: demandCost,
        fixed: costData.reduce((sum, item) => sum + item.costs.fixed, 0),
        taxes: costData.reduce((sum, item) => sum + item.costs.taxes, 0),
      },
      average: {
        daily: totalCost / costData.length,
        perDevice: totalCost / new Set(costData.map(d => d.deviceId)).size,
      },
      trend: this.calculateCostTrend(costData),
    };
  }

  private calculateCostTrend(costData: IEnergyCost[]): string {
    if (costData.length < 2) return 'STABLE';
    
    const firstHalf = costData.slice(0, Math.floor(costData.length / 2));
    const secondHalf = costData.slice(Math.floor(costData.length / 2));
    
    const firstAvg = firstHalf.reduce((sum, item) => sum + item.costs.total, 0) / firstHalf.length;
    const secondAvg = secondHalf.reduce((sum, item) => sum + item.costs.total, 0) / secondHalf.length;
    
    const change = ((secondAvg - firstAvg) / firstAvg) * 100;
    
    if (change > 5) return 'INCREASING';
    if (change < -5) return 'DECREASING';
    return 'STABLE';
  }

  private getForecastHistoricalStartDate(horizon: ForecastHorizon): Date {
    const today = new Date();
    
    switch (horizon) {
      case ForecastHorizon.DAY:
        return subDays(today, 30);
      case ForecastHorizon.WEEK:
        return subDays(today, 90);
      case ForecastHorizon.MONTH:
        return subDays(today, 365);
      case ForecastHorizon.QUARTER:
        return subDays(today, 365 * 2);
      case ForecastHorizon.YEAR:
        return subDays(today, 365 * 3);
      default:
        return subDays(today, 90);
    }
  }

  private calculateDailyConsumptionSeries(data: any[]): number[] {
    const dailyData = this.groupDataByPeriod(data, AggregationPeriod.DAY);
    return Object.values(dailyData).map(dayData => this.calculateDailyEnergy(dayData));
  }

  private simpleMovingAverageForecast(series: number[], horizon: ForecastHorizon): any[] {
    const windowSize = 7; // 7天移动平均
    const lastValues = series.slice(-windowSize);
    const average = lastValues.reduce((a, b) => a + b, 0) / windowSize;
    
    const forecastDays = this.getForecastDays(horizon);
    const predictions = [];
    const today = new Date();

    for (let i = 1; i <= forecastDays; i++) {
      const date = addDays(today, i);
      const variation = (Math.random() - 0.5) * 0.1 * average; // ±5%随机波动
      
      predictions.push({
        timestamp: date,
        predicted: average + variation,
        lower: (average + variation) * 0.9,
        upper: (average + variation) * 1.1,
      });
    }

    return predictions;
  }

  private getForecastDays(horizon: ForecastHorizon): number {
    switch (horizon) {
      case ForecastHorizon.DAY:
        return 1;
      case ForecastHorizon.WEEK:
        return 7;
      case ForecastHorizon.MONTH:
        return 30;
      case ForecastHorizon.QUARTER:
        return 90;
      case ForecastHorizon.YEAR:
        return 365;
      default:
        return 7;
    }
  }

  private analyzeUsagePatterns(data: any[]): any {
    // 分析使用模式
    const hourlyData = this.groupDataByPeriod(data, AggregationPeriod.HOUR);
    const peakHours = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21];
    
    let peakUsage = 0;
    let totalUsage = 0;

    Object.entries(hourlyData).forEach(([hourKey, hourData]) => {
      const hour = new Date(hourKey).getHours();
      const usage = this.calculateHourlyEnergy(hourData);
      
      totalUsage += usage;
      if (peakHours.includes(hour)) {
        peakUsage += usage;
      }
    });

    return {
      peakUsageRatio: totalUsage > 0 ? peakUsage / totalUsage : 0,
      averageHourlyUsage: totalUsage / Object.keys(hourlyData).length,
    };
  }

  private calculateHourlyEnergy(data: any[]): number {
    const powerValues = data.map(d => d.metrics.power || 0);
    if (powerValues.length === 0) return 0;
    
    const avgPower = powerValues.reduce((a, b) => a + b, 0) / powerValues.length;
    return avgPower / 1000; // kWh
  }

  private calculatePotentialSavings(suggestions: any[]): any {
    const totalSavings = suggestions.reduce((acc, suggestion) => {
      acc.energy += suggestion.potentialSavings.energy;
      acc.cost += suggestion.potentialSavings.cost;
      acc.co2 += suggestion.potentialSavings.co2;
      return acc;
    }, { energy: 0, cost: 0, co2: 0 });

    const totalInvestment = suggestions.reduce((sum, s) => sum + s.implementationCost, 0);
    const avgPayback = totalInvestment / (totalSavings.cost / 12); // 月

    return {
      annual: totalSavings,
      totalInvestment,
      averagePaybackMonths: avgPayback,
      roi: ((totalSavings.cost - totalInvestment) / totalInvestment) * 100,
    };
  }

  private getPeriodStartDate(period: string): Date {
    const now = new Date();
    
    switch (period) {
      case 'DAY':
        return startOfDay(now);
      case 'WEEK':
        return subDays(now, 7);
      case 'MONTH':
        return subDays(now, 30);
      case 'YEAR':
        return subDays(now, 365);
      default:
        return startOfDay(now);
    }
  }

  private generateTrendData(deviceDataMap: Map<string, any[]>, period: string): any[] {
    // 生成趋势数据
    const trendData = [];
    const now = new Date();
    
    for (let i = 6; i >= 0; i--) {
      const date = subDays(now, i);
      let dayTotal = 0;

      for (const [deviceId, data] of deviceDataMap) {
        const dayData = data.filter(d => {
          const dataDate = new Date(d.timestamp);
          return format(dataDate, 'yyyy-MM-dd') === format(date, 'yyyy-MM-dd');
        });
        
        dayTotal += this.calculateDailyEnergy(dayData);
      }

      trendData.push({
        date: format(date, 'yyyy-MM-dd'),
        value: dayTotal,
      });
    }

    return trendData;
  }

  private checkEnergyAlerts(dashboard: any): any[] {
    const alerts = [];

    // 检查高能耗
    if (dashboard.consumption.total > 1000) { // kWh阈值
      alerts.push({
        type: 'HIGH_CONSUMPTION',
        severity: 'WARNING',
        message: `Total consumption (${dashboard.consumption.total.toFixed(2)} kWh) exceeds threshold`,
        timestamp: new Date(),
      });
    }

    // 检查低效率
    if (dashboard.efficiency.average < 80) {
      alerts.push({
        type: 'LOW_EFFICIENCY',
        severity: 'WARNING',
        message: `Average efficiency (${dashboard.efficiency.average.toFixed(1)}%) is below target`,
        timestamp: new Date(),
      });
    }

    // 检查成本超支
    if (dashboard.cost.total > 500) { // $阈值
      alerts.push({
        type: 'HIGH_COST',
        severity: 'INFO',
        message: `Total cost ($${dashboard.cost.total.toFixed(2)}) exceeds budget`,
        timestamp: new Date(),
      });
    }

    return alerts;
  }
}

export const energyController = new EnergyController();