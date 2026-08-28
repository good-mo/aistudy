/**
 * utils/logger.ts — 日志工具
 *
 * 基于 winston 的统一日志记录，输出到控制台与文件。
 * 支持日志级别过滤，便于在 CI 与本地开发中分别查看。
 */
import winston from 'winston';
import fs from 'fs';
import path from 'path';

// 确保日志目录存在
const logDir = path.resolve(__dirname, '../reports/logs');
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true });
}

const logLevel = process.env.ALVA_LOG_LEVEL || (process.env.CI ? 'info' : 'debug');

/**
 * 全局 logger 实例。
 * - 控制台输出带颜色与时间戳
 * - 文件输出到 reports/logs/qa.log
 */
export const logger = winston.createLogger({
  level: logLevel,
  format: winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    winston.format.errors({ stack: true }),
    winston.format.splat(),
    winston.format.printf(({ timestamp, level, message, ...meta }) => {
      const metaStr = Object.keys(meta).length ? ` ${JSON.stringify(meta)}` : '';
      return `[${timestamp}] [${level.toUpperCase()}] ${message}${metaStr}`;
    }),
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize({ all: true }),
        winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
        winston.format.printf(({ timestamp, level, message, ...meta }) => {
          const metaStr = Object.keys(meta).length ? ` ${JSON.stringify(meta)}` : '';
          return `[${timestamp}] [${level}] ${message}${metaStr}`;
        }),
      ),
    }),
    new winston.transports.File({ filename: path.join(logDir, 'qa.log') }),
  ],
});

/** 便捷访问：导出各日志级别方法 */
export const log = {
  debug: (msg: string, meta?: object) => logger.debug(msg, meta),
  info: (msg: string, meta?: object) => logger.info(msg, meta),
  warn: (msg: string, meta?: object) => logger.warn(msg, meta),
  error: (msg: string, meta?: object) => logger.error(msg, meta),
};

export default logger;
