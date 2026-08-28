import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright 全局配置
 * - 面向 Alva 金融分析平台 Web UI 的端到端测试
 * - 支持通过环境变量覆盖基础 URL、重试次数与并行度
 */
export default defineConfig({
  testDir: './tests',
  // 对真实外部站点 alva.ai 串行执行，避免并发被限流导致不稳定
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [
    ['html', { outputFolder: 'reports/html' }],
    ['json', { outputFile: 'reports/json/results.json' }],
    ['list'],
  ],
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    // 基础 URL：通过环境变量注入，默认指向 Alva 平台真实地址
    baseURL: process.env.ALVA_BASE_URL || 'https://alva.ai/',
    // 始终收集并保留截图 / 日志 / trace，供报告目录留存
    trace: 'on',
    screenshot: 'on',
    video: 'on',
    // 测试产物输出目录
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  outputDir: 'reports/screenshots',
});
