export interface IDevice {
  deviceId: string;
  thingName: string;
  thingType?: string;
  attributes: {
    deviceType: string;
    location?: string;
    firmware?: string;
    serialNumber?: string;
    [key: string]: any;
  };
  status: DeviceStatus;
  connectionState: ConnectionState;
  lastSeen?: Date;
  createdAt: Date;
  updatedAt: Date;
  certificateArn?: string;
  metadata?: Record<string, any>;
}

export enum DeviceStatus {
  ACTIVE = 'ACTIVE',
  INACTIVE = 'INACTIVE',
  MAINTENANCE = 'MAINTENANCE',
  ERROR = 'ERROR',
}

export enum ConnectionState {
  CONNECTED = 'CONNECTED',
  DISCONNECTED = 'DISCONNECTED',
  UNKNOWN = 'UNKNOWN',
}

export interface IDeviceShadow {
  state: {
    desired?: Record<string, any>;
    reported?: Record<string, any>;
    delta?: Record<string, any>;
  };
  metadata?: {
    desired?: Record<string, any>;
    reported?: Record<string, any>;
  };
  version?: number;
  timestamp?: number;
}

export interface IDeviceCommand {
  commandId: string;
  deviceId: string;
  type: CommandType;
  payload: Record<string, any>;
  status: CommandStatus;
  createdAt: Date;
  executedAt?: Date;
  result?: any;
  error?: string;
}

export enum CommandType {
  REBOOT = 'REBOOT',
  UPDATE_CONFIG = 'UPDATE_CONFIG',
  FIRMWARE_UPDATE = 'FIRMWARE_UPDATE',
  DIAGNOSTIC = 'DIAGNOSTIC',
  CUSTOM = 'CUSTOM',
}

export enum CommandStatus {
  PENDING = 'PENDING',
  SENT = 'SENT',
  ACKNOWLEDGED = 'ACKNOWLEDGED',
  EXECUTED = 'EXECUTED',
  FAILED = 'FAILED',
  TIMEOUT = 'TIMEOUT',
}