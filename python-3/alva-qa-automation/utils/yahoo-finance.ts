/**
 * utils/yahoo-finance.ts — Yahoo Finance 数据获取工具
 *
 * 通过 Yahoo Finance 公开接口获取实时行情数据，用于与 Alva 平台
 * 返回的金融数据进行交叉校验。
 *
 * 注意：真实环境请配置有效的 Yahoo Finance API key（YAHOO_API_KEY），
 * 框架内置了基于查询字符串 / quote 接口的轻量实现，便于测试。
 */
import axios from 'axios';
import { logger } from './logger';
import type { QuoteSnapshot } from './financial-data';

const YAHOO_BASE = process.env.YAHOO_API_BASE || 'https://query1.finance.yahoo.com/v8/finance/chart';

/** Yahoo Finance 单个标的的行情快照 */
export interface YahooQuote {
  symbol: string;
  price: number;
  previousClose: number;
  change: number;
  changePercent: number;
  volume: number;
  timestamp: string;
}

/**
 * 从 Yahoo Finance 拉取指定 symbol 的实时行情。
 * @param symbol 股票/指数代码，如 AAPL、0700.HK
 * @returns 标准化后的行情快照
 */
export async function fetchQuote(symbol: string): Promise<YahooQuote> {
  const url = `${YAHOO_BASE}/${encodeURIComponent(symbol)}?interval=1d&range=1d`;
  logger.debug(`请求 Yahoo Finance: ${url}`);

  try {
    const { data } = await axios.get(url, {
      timeout: 10_000,
      headers: { 'User-Agent': 'alva-qa-automation/1.0' },
    });

    const result = data?.chart?.result?.[0];
    const meta = result?.meta;
    if (!meta) {
      throw new Error(`Yahoo Finance 未返回有效数据 for ${symbol}`);
    }

    const price = meta.regularMarketPrice ?? meta.previousClose;
    const previousClose = meta.previousClose ?? price;
    const change = price - previousClose;
    const changePercent = previousClose ? (change / previousClose) * 100 : 0;

    const quote: YahooQuote = {
      symbol,
      price,
      previousClose,
      change: Number(change.toFixed(4)),
      changePercent: Number(changePercent.toFixed(4)),
      volume: meta.regularMarketVolume ?? 0,
      timestamp: new Date(meta.regularMarketTime * 1000).toISOString(),
    };
    logger.info(`获取 ${symbol} 行情: $${quote.price}`);
    return quote;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    logger.error(`Yahoo Finance 获取 ${symbol} 失败: ${msg}`);
    throw new Error(`Yahoo Finance 获取失败 ${symbol}: ${msg}`);
  }
}

/**
 * 批量获取多个 symbol 的行情，容忍单个失败。
 * @param symbols 标的列表
 * @returns 成功获取的行情列表（失败项被过滤并记录日志）
 */
export async function fetchQuotes(symbols: string[]): Promise<YahooQuote[]> {
  const results: YahooQuote[] = [];
  for (const symbol of symbols) {
    try {
      results.push(await fetchQuote(symbol));
    } catch (e) {
      logger.warn(`跳过 ${symbol}: ${e instanceof Error ? e.message : e}`);
    }
  }
  return results;
}

/**
 * 将 Yahoo 行情转换为框架统一的 QuoteSnapshot。
 */
export function toQuoteSnapshot(yahoo: YahooQuote): QuoteSnapshot {
  return {
    symbol: yahoo.symbol,
    price: yahoo.price,
    change: yahoo.change,
    changePercent: yahoo.changePercent,
    volume: yahoo.volume,
    marketCap: undefined,
    timestamp: yahoo.timestamp,
  };
}
