/**
 * tests/fixtures.ts — 共享测试夹具
 *
 * 封装 Playwright test 对象，注入全局日志与基础配置。
 */
import { test as base, expect } from '@playwright/test';
import { logger } from '../utils/logger';

/** 扩展的测试上下文 */
export const test = base.extend({
  // 在每个测试开始时输出日志
  page: async ({ page }, use) => {
    logger.info(`测试开始: ${test.info().title}`);
    await use(page);
    logger.info(`测试结束: ${test.info().title}`);
  },
});

export { expect };
