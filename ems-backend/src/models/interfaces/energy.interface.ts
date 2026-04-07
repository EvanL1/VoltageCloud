export interface IEnergyConsumption {
  deviceId: string;
  timestamp: Date;
  period: AggregationPeriod;
  consumption: {
    total: number;
    peak: number;
    offPeak: number;
    average: number;
  };
  cost: {
    total: number;
    peak: number;
    offPeak: number;
    currency: string;
  };
  unit: EnergyUnit;
  metadata?: Record<string, any>;
}

export enum EnergyUnit {
  KWH = 'kWh',
  MWH = 'MWh',
  GWH = 'GWh',
  JOULE = 'J',
  KILOJOULE = 'kJ',
  MEGAJOULE = 'MJ',
}

export interface IEnergyEfficiency {
  deviceId: string;
  timestamp: Date;
  period: AggregationPeriod;
  metrics: {
    efficiency: number; // 百分比
    powerFactor: number;
    loadFactor: number;
    utilizationRate: number;
  };
  benchmarks: {
    industry: number;
    target: number;
    improvement: number; // 相对于基准的改进百分比
  };
  recommendations?: IEfficiencyRecommendation[];
}

export interface IEfficiencyRecommendation {
  id: string;
  priority: Priority;
  category: RecommendationCategory;
  title: string;
  description: string;
  potentialSavings: {
    energy: number;
    cost: number;
    co2: number;
  };
  implementationCost: number;
  paybackPeriod: number; // 月
  status: RecommendationStatus;
}

export enum Priority {
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW',
}

export enum RecommendationCategory {
  EQUIPMENT = 'EQUIPMENT',
  OPERATION = 'OPERATION',
  MAINTENANCE = 'MAINTENANCE',
  BEHAVIOR = 'BEHAVIOR',
}

export enum RecommendationStatus {
  NEW = 'NEW',
  REVIEWED = 'REVIEWED',
  APPROVED = 'APPROVED',
  IN_PROGRESS = 'IN_PROGRESS',
  COMPLETED = 'COMPLETED',
  REJECTED = 'REJECTED',
}

export interface IEnergyCost {
  deviceId: string;
  timestamp: Date;
  period: AggregationPeriod;
  tariff: {
    name: string;
    type: TariffType;
    rates: ITariffRate[];
  };
  costs: {
    energy: number;
    demand: number;
    fixed: number;
    taxes: number;
    total: number;
  };
  currency: string;
  breakdown?: ICostBreakdown[];
}

export enum TariffType {
  FLAT = 'FLAT',
  TIME_OF_USE = 'TIME_OF_USE',
  TIERED = 'TIERED',
  DEMAND = 'DEMAND',
  DYNAMIC = 'DYNAMIC',
}

export interface ITariffRate {
  name: string;
  rate: number;
  unit: string;
  timeSlots?: ITimeSlot[];
  tiers?: ITier[];
}

export interface ITimeSlot {
  startTime: string; // HH:MM
  endTime: string;   // HH:MM
  days: number[];    // 0-6, 0=Sunday
}

export interface ITier {
  min: number;
  max: number;
  rate: number;
}

export interface ICostBreakdown {
  category: string;
  amount: number;
  percentage: number;
  details?: Record<string, any>;
}

export interface IEnergyForecast {
  deviceId: string;
  timestamp: Date;
  horizon: ForecastHorizon;
  predictions: IForecastPoint[];
  accuracy: {
    mape: number; // Mean Absolute Percentage Error
    rmse: number; // Root Mean Square Error
    confidence: number;
  };
  factors: IForecastFactor[];
  recommendations?: string[];
}

export enum ForecastHorizon {
  DAY = 'DAY',
  WEEK = 'WEEK',
  MONTH = 'MONTH',
  QUARTER = 'QUARTER',
  YEAR = 'YEAR',
}

export interface IForecastPoint {
  timestamp: Date;
  predicted: number;
  lower: number; // 置信区间下限
  upper: number; // 置信区间上限
  actual?: number; // 如果已有实际值
}

export interface IForecastFactor {
  name: string;
  impact: number; // -100 到 100
  description: string;
}

export interface IEnergyReport {
  id: string;
  type: ReportType;
  period: {
    start: Date;
    end: Date;
  };
  devices: string[];
  metrics: string[];
  summary: {
    totalConsumption: number;
    totalCost: number;
    avgEfficiency: number;
    co2Emissions: number;
  };
  sections: IReportSection[];
  generatedAt: Date;
  generatedBy: string;
  format?: ExportFormat;
}

export enum ReportType {
  DAILY = 'DAILY',
  WEEKLY = 'WEEKLY',
  MONTHLY = 'MONTHLY',
  QUARTERLY = 'QUARTERLY',
  ANNUAL = 'ANNUAL',
  CUSTOM = 'CUSTOM',
}

export interface IReportSection {
  title: string;
  type: SectionType;
  data: any;
  charts?: IChartConfig[];
  tables?: ITableConfig[];
}

export enum SectionType {
  SUMMARY = 'SUMMARY',
  CONSUMPTION = 'CONSUMPTION',
  COST = 'COST',
  EFFICIENCY = 'EFFICIENCY',
  COMPARISON = 'COMPARISON',
  FORECAST = 'FORECAST',
}

export interface IChartConfig {
  type: ChartType;
  title: string;
  data: any;
  options?: Record<string, any>;
}

export enum ChartType {
  LINE = 'LINE',
  BAR = 'BAR',
  PIE = 'PIE',
  AREA = 'AREA',
  SCATTER = 'SCATTER',
  HEATMAP = 'HEATMAP',
}

export interface ITableConfig {
  columns: ITableColumn[];
  data: any[];
  options?: Record<string, any>;
}

export interface ITableColumn {
  key: string;
  title: string;
  type: 'string' | 'number' | 'date' | 'boolean';
  format?: string;
  sortable?: boolean;
}

// 导入必要的类型
import { AggregationPeriod } from './telemetry.interface';
import { ExportFormat } from './telemetry.interface';