export interface ITelemetryData {
  deviceId: string;
  timestamp: Date;
  metrics: IMetrics;
  location?: ILocation;
  metadata?: Record<string, any>;
}

export interface IMetrics {
  temperature?: number;
  humidity?: number;
  pressure?: number;
  voltage?: number;
  current?: number;
  power?: number;
  energy?: number;
  frequency?: number;
  powerFactor?: number;
  [key: string]: any;
}

export interface ILocation {
  latitude: number;
  longitude: number;
  altitude?: number;
  accuracy?: number;
}

export interface IAggregatedData {
  deviceId: string;
  metric: string;
  period: AggregationPeriod;
  startTime: Date;
  endTime: Date;
  values: {
    min: number;
    max: number;
    avg: number;
    sum: number;
    count: number;
    stdDev?: number;
  };
  unit?: string;
}

export enum AggregationPeriod {
  MINUTE = 'MINUTE',
  HOUR = 'HOUR',
  DAY = 'DAY',
  WEEK = 'WEEK',
  MONTH = 'MONTH',
  YEAR = 'YEAR',
}

export interface ITelemetryQuery {
  deviceId?: string;
  deviceIds?: string[];
  metrics?: string[];
  startTime: Date;
  endTime: Date;
  aggregation?: {
    period: AggregationPeriod;
    functions: AggregationFunction[];
  };
  limit?: number;
  offset?: number;
  orderBy?: 'timestamp' | 'deviceId';
  order?: 'ASC' | 'DESC';
}

export enum AggregationFunction {
  MIN = 'MIN',
  MAX = 'MAX',
  AVG = 'AVG',
  SUM = 'SUM',
  COUNT = 'COUNT',
  STDDEV = 'STDDEV',
}

export interface ITimeSeriesPoint {
  timestamp: Date;
  value: number;
  unit?: string;
  quality?: DataQuality;
}

export enum DataQuality {
  GOOD = 'GOOD',
  UNCERTAIN = 'UNCERTAIN',
  BAD = 'BAD',
}

export interface IDataExport {
  format: ExportFormat;
  data: ITelemetryData[] | IAggregatedData[];
  metadata: {
    exportDate: Date;
    recordCount: number;
    startTime: Date;
    endTime: Date;
    devices: string[];
    metrics: string[];
  };
}

export enum ExportFormat {
  JSON = 'JSON',
  CSV = 'CSV',
  EXCEL = 'EXCEL',
  PDF = 'PDF',
}