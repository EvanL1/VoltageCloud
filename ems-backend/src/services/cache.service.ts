import Redis from 'ioredis';
import { appConfig } from '../config/app.config';
import { createLogger } from '../utils/logger';

const logger = createLogger('CacheService');

export class CacheService {
  private redis: Redis;
  private isConnected: boolean = false;

  constructor() {
    this.redis = new Redis({
      host: appConfig.redis.host,
      port: appConfig.redis.port,
      password: appConfig.redis.password,
      retryStrategy: (times) => {
        const delay = Math.min(times * 50, 2000);
        return delay;
      },
      reconnectOnError: (err) => {
        const targetError = 'READONLY';
        if (err.message.includes(targetError)) {
          return true;
        }
        return false;
      },
    });

    this.redis.on('connect', () => {
      this.isConnected = true;
      logger.info('Redis connected successfully');
    });

    this.redis.on('error', (error) => {
      this.isConnected = false;
      logger.error('Redis connection error:', error);
    });

    this.redis.on('close', () => {
      this.isConnected = false;
      logger.warn('Redis connection closed');
    });
  }

  /**
   * 检查Redis连接状态
   */
  isReady(): boolean {
    return this.isConnected && this.redis.status === 'ready';
  }

  /**
   * 获取缓存值
   */
  async get<T>(key: string): Promise<T | null> {
    try {
      if (!this.isReady()) {
        logger.warn('Redis not ready, skipping cache get');
        return null;
      }

      const value = await this.redis.get(key);
      if (!value) {
        return null;
      }

      return JSON.parse(value) as T;
    } catch (error) {
      logger.error(`Failed to get cache key ${key}:`, error);
      return null;
    }
  }

  /**
   * 设置缓存值
   */
  async set<T>(
    key: string,
    value: T,
    ttl: number = appConfig.redis.ttl
  ): Promise<boolean> {
    try {
      if (!this.isReady()) {
        logger.warn('Redis not ready, skipping cache set');
        return false;
      }

      const serialized = JSON.stringify(value);
      if (ttl > 0) {
        await this.redis.setex(key, ttl, serialized);
      } else {
        await this.redis.set(key, serialized);
      }

      return true;
    } catch (error) {
      logger.error(`Failed to set cache key ${key}:`, error);
      return false;
    }
  }

  /**
   * 删除缓存值
   */
  async delete(key: string): Promise<boolean> {
    try {
      if (!this.isReady()) {
        logger.warn('Redis not ready, skipping cache delete');
        return false;
      }

      await this.redis.del(key);
      return true;
    } catch (error) {
      logger.error(`Failed to delete cache key ${key}:`, error);
      return false;
    }
  }

  /**
   * 批量删除缓存
   */
  async deletePattern(pattern: string): Promise<number> {
    try {
      if (!this.isReady()) {
        logger.warn('Redis not ready, skipping cache delete pattern');
        return 0;
      }

      const keys = await this.redis.keys(pattern);
      if (keys.length === 0) {
        return 0;
      }

      return await this.redis.del(...keys);
    } catch (error) {
      logger.error(`Failed to delete cache pattern ${pattern}:`, error);
      return 0;
    }
  }

  /**
   * 检查键是否存在
   */
  async exists(key: string): Promise<boolean> {
    try {
      if (!this.isReady()) {
        return false;
      }

      const result = await this.redis.exists(key);
      return result === 1;
    } catch (error) {
      logger.error(`Failed to check cache key existence ${key}:`, error);
      return false;
    }
  }

  /**
   * 设置键的过期时间
   */
  async expire(key: string, ttl: number): Promise<boolean> {
    try {
      if (!this.isReady()) {
        return false;
      }

      const result = await this.redis.expire(key, ttl);
      return result === 1;
    } catch (error) {
      logger.error(`Failed to set expiry for cache key ${key}:`, error);
      return false;
    }
  }

  /**
   * 获取键的剩余生存时间
   */
  async ttl(key: string): Promise<number> {
    try {
      if (!this.isReady()) {
        return -1;
      }

      return await this.redis.ttl(key);
    } catch (error) {
      logger.error(`Failed to get TTL for cache key ${key}:`, error);
      return -1;
    }
  }

  /**
   * 使用缓存或回退到函数获取数据
   */
  async getOrSet<T>(
    key: string,
    fallbackFn: () => Promise<T>,
    ttl: number = appConfig.redis.ttl
  ): Promise<T> {
    // 先尝试从缓存获取
    const cached = await this.get<T>(key);
    if (cached !== null) {
      logger.debug(`Cache hit for key: ${key}`);
      return cached;
    }

    // 缓存未命中，执行回退函数
    logger.debug(`Cache miss for key: ${key}`);
    const value = await fallbackFn();

    // 将结果存入缓存
    await this.set(key, value, ttl);

    return value;
  }

  /**
   * 批量获取缓存
   */
  async mget<T>(keys: string[]): Promise<Map<string, T>> {
    try {
      if (!this.isReady() || keys.length === 0) {
        return new Map();
      }

      const values = await this.redis.mget(...keys);
      const result = new Map<string, T>();

      keys.forEach((key, index) => {
        const value = values[index];
        if (value) {
          try {
            result.set(key, JSON.parse(value) as T);
          } catch (error) {
            logger.error(`Failed to parse cache value for key ${key}:`, error);
          }
        }
      });

      return result;
    } catch (error) {
      logger.error('Failed to batch get cache keys:', error);
      return new Map();
    }
  }

  /**
   * 批量设置缓存
   */
  async mset<T>(
    items: Map<string, T>,
    ttl: number = appConfig.redis.ttl
  ): Promise<boolean> {
    try {
      if (!this.isReady() || items.size === 0) {
        return false;
      }

      const pipeline = this.redis.pipeline();

      items.forEach((value, key) => {
        const serialized = JSON.stringify(value);
        if (ttl > 0) {
          pipeline.setex(key, ttl, serialized);
        } else {
          pipeline.set(key, serialized);
        }
      });

      await pipeline.exec();
      return true;
    } catch (error) {
      logger.error('Failed to batch set cache keys:', error);
      return false;
    }
  }

  /**
   * 增加计数器
   */
  async increment(key: string, by: number = 1): Promise<number | null> {
    try {
      if (!this.isReady()) {
        return null;
      }

      return await this.redis.incrby(key, by);
    } catch (error) {
      logger.error(`Failed to increment cache key ${key}:`, error);
      return null;
    }
  }

  /**
   * 减少计数器
   */
  async decrement(key: string, by: number = 1): Promise<number | null> {
    try {
      if (!this.isReady()) {
        return null;
      }

      return await this.redis.decrby(key, by);
    } catch (error) {
      logger.error(`Failed to decrement cache key ${key}:`, error);
      return null;
    }
  }

  /**
   * 清空所有缓存（慎用）
   */
  async flush(): Promise<boolean> {
    try {
      if (!this.isReady()) {
        return false;
      }

      await this.redis.flushdb();
      logger.warn('All cache entries have been flushed');
      return true;
    } catch (error) {
      logger.error('Failed to flush cache:', error);
      return false;
    }
  }

  /**
   * 关闭Redis连接
   */
  async close(): Promise<void> {
    await this.redis.quit();
    logger.info('Redis connection closed');
  }
}

// 缓存键生成器
export class CacheKeyGenerator {
  static device(deviceId: string): string {
    return `device:${deviceId}`;
  }

  static deviceList(page: number, limit: number): string {
    return `devices:list:${page}:${limit}`;
  }

  static deviceShadow(deviceId: string): string {
    return `device:${deviceId}:shadow`;
  }

  static telemetry(deviceId: string, date: string): string {
    return `telemetry:${deviceId}:${date}`;
  }

  static latestTelemetry(deviceId: string): string {
    return `telemetry:${deviceId}:latest`;
  }

  static aggregation(deviceId: string, metric: string, period: string, date: string): string {
    return `aggregation:${deviceId}:${metric}:${period}:${date}`;
  }

  static energy(type: string, deviceId: string, period: string): string {
    return `energy:${type}:${deviceId}:${period}`;
  }

  static user(userId: string): string {
    return `user:${userId}`;
  }

  static session(sessionId: string): string {
    return `session:${sessionId}`;
  }

  static apiRateLimit(ip: string, endpoint: string): string {
    return `ratelimit:${ip}:${endpoint}`;
  }
}

// 导出单例
export const cacheService = new CacheService();