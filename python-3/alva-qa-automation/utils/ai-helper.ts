/**
 * utils/ai-helper.ts — AI 辅助断言
 *
 * 通过 AI 接口辅助对 Alva 平台的智能分析结果进行自然语言断言。
 * 用于校验 AI 生成的买卖建议、投资分析等内容是否包含关键信息。
 *
 * 默认使用本地规则匹配（启发式），可通过 AI_ENDPOINT / AI_API_KEY
 * 配置接入真实 LLM 服务。
 */
import axios from 'axios';
import { logger } from './logger';

const AI_ENDPOINT = process.env.AI_ENDPOINT || '';
const AI_API_KEY = process.env.AI_API_KEY || '';

/** 断言结果 */
export interface AiAssertionResult {
  passed: boolean;
  reason: string;
}

/** 关键字检查配置 */
interface KeywordCheck {
  /** 期望文本中包含的关键词 */
  keywords: string[];
  /** 是否为"全部必须包含"模式；false 表示至少包含一个 */
  all?: boolean;
}

/**
 * 本地启发式关键词校验：检查 AI 分析文本是否包含关键信息。
 * 无需外部 AI 服务即可运行。
 */
export function checkKeywordsInText(
  text: string,
  { keywords, all = true }: KeywordCheck,
): AiAssertionResult {
  if (!text) {
    return { passed: false, reason: 'AI 返回文本为空' };
  }
  const lower = text.toLowerCase();
  const missing = keywords.filter((k) => !lower.includes(k.toLowerCase()));
  const passed = all ? missing.length === 0 : missing.length < keywords.length;
  return {
    passed,
    reason: passed
      ? `文本包含所需关键词 ✓`
      : `文本缺少关键词: ${missing.join(', ')}`,
  };
}

/**
 * 调用远程 AI 接口进行语义化断言。
 * 需要配置 AI_ENDPOINT 与 AI_API_KEY。
 * @param prompt  发给 AI 的判定提示词
 * @param content 待判定内容
 */
export async function callAiAssertion(
  prompt: string,
  content: string,
): Promise<AiAssertionResult> {
  if (!AI_ENDPOINT || !AI_API_KEY) {
    logger.warn('未配置 AI_ENDPOINT/AI_API_KEY，退回本地关键词校验');
    return { passed: false, reason: '未配置 AI 服务，使用本地校验替代' };
  }

  try {
    const { data } = await axios.post(
      AI_ENDPOINT,
      { prompt, content },
      {
        timeout: 15_000,
        headers: { Authorization: `Bearer ${AI_API_KEY}` },
      },
    );
    const verdict = String(data?.verdict ?? data?.result ?? '').toLowerCase();
    return {
      passed: verdict.includes('pass') || verdict.includes('true') || verdict === '1',
      reason: String(data?.reason ?? verdict),
    };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    logger.error(`AI 断言调用失败: ${msg}`);
    return { passed: false, reason: `AI 调用失败: ${msg}` };
  }
}

/**
 * 校验 AI 生成的买卖建议是否包含"买入/卖出/持有"等关键操作信号，
 * 且包含具体的价格或百分比信息。
 */
export function validateInvestmentAdvice(text: string): AiAssertionResult {
  const operation = checkKeywordsInText(text, {
    keywords: ['买入', '卖出', '持有', 'buy', 'sell', 'hold'],
    all: false,
  });
  if (!operation.passed) {
    return { passed: false, reason: 'AI 建议缺少明确的买卖操作信号' };
  }

  // 校验是否包含数字（价格 / 百分比）
  const hasNumber = /[-+]?\d+(\.\d+)?%?/.test(text);
  if (!hasNumber) {
    return { passed: false, reason: 'AI 建议缺少具体数值（价格/百分比）' };
  }

  return { passed: true, reason: 'AI 建议包含操作信号与具体数值 ✓' };
}
