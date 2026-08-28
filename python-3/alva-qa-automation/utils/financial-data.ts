/**
 * utils/financial-data.ts — 金融数据校验工具
 *
 * 提供针对 Alva 金融分析平台返回的行情 / 估值数据的校验函数。
 * 支持区间范围、容差比例、字段类型等多种校验方式。
 */
import { logger } from './logger';

/** 资产类型 */
export type AssetType = 'stock' | 'fund' | 'index';

/** 行情快照数据结构 */
export interface QuoteSnapshot {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  marketCap?: number;
  timestamp: string;
}

/** 校验结果 */
export interface ValidationResult {
  symbol: string;
  field: string;
  passed: boolean;
  actual?: number;
  expected?: number;
  tolerance?: number;
  message: string;
}

/**
 * 校验数值是否在给定容差范围内。
 * @param actual   实际值
 * @param expected 期望值
 * @param tolerance 允许偏差比例（0~1，如 0.05 表示 ±5%）
 */
export function withinTolerance(
  actual: number,
  expected: number,
  tolerance = 0.05,
): boolean {
  if (expected === 0) return actual === 0;
  return Math.abs(actual - expected) / Math.abs(expected) <= tolerance;
}

/**
 * 校验数值是否处于闭区间 [min, max] 内。
 */
export function withinRange(actual: number, min: number, max: number): boolean {
  return actual >= min && actual <= max;
}

/**
 * 批量校验一组行情快照与预期值的容差匹配情况。
 * @param quotes      实际获取的行情快照
 * @param expected    预期值（symbol → 字段 → 期望值 & 容差）
 * @returns 所有字段的校验结果
 */
export function validateQuotesAgainstExpected(
  quotes: QuoteSnapshot[],
  expected: Record<
    string,
    Partial<Record<'price' | 'volume' | 'marketCap' | 'peRatio', { value: number; tolerance: number }>>
  >,
): ValidationResult[] {
  const results: ValidationResult[] = [];

  for (const quote of quotes) {
    const exp = expected[quote.symbol];
    if (!exp) {
      results.push({
        symbol: quote.symbol,
        field: 'symbol',
        passed: false,
        message: `未找到 symbol 的预期配置: ${quote.symbol}`,
      });
      continue;
    }

    for (const [field, config] of Object.entries(exp)) {
      const actual = (quote as unknown as Record<string, number>)[field];
      if (actual === undefined) {
        results.push({
          symbol: quote.symbol,
          field,
          passed: false,
          message: `行情数据缺少字段: ${field}`,
        });
        continue;
      }
      const tolerance = config?.tolerance ?? 0.05;
      const expectedValue = config?.value ?? 0;
      const passed = withinTolerance(actual, expectedValue, tolerance);
      results.push({
        symbol: quote.symbol,
        field,
        passed,
        actual,
        expected: expectedValue,
        tolerance,
        message: passed
          ? `✓ ${quote.symbol}.${field} 在容差内 (${actual})`
          : `✗ ${quote.symbol}.${field} 超出容差 (实际=${actual}, 期望=${expectedValue}, ±${tolerance * 100}%)`,
      });
    }
  }

  const failed = results.filter((r) => !r.passed);
  if (failed.length) {
    logger.warn(`金融数据校验发现 ${failed.length} 处异常`);
  } else {
    logger.info(`金融数据校验全部通过 (${results.length} 项)`);
  }
  return results;
}

/**
 * 断言所有校验结果均通过；若有失败则抛出异常。
 * 供 Playwright 测试断言使用。
 */
export function assertAllValidationsPass(results: ValidationResult[]): void {
  const failed = results.filter((r) => !r.passed);
  if (failed.length > 0) {
    const detail = failed.map((f) => f.message).join('\n');
    throw new Error(`金融数据校验失败 ${failed.length} 项:\n${detail}`);
  }
}
