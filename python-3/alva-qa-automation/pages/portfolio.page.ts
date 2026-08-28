/**
 * pages/portfolio.page.ts — 投资组合页面对象（真实 alva.ai）
 *
 * 基于 alva.ai 真实 `/portfolio` 页面的 DOM 结构。
 * 未登录状态下页面展示引导态："Connect your first account"、
 * "Your Trading, One Dashboard"，并提供 Add / Settings / Alva Agent 入口。
 */
import { Page, Locator, expect } from '@playwright/test';
import { logger } from '../utils/logger';

export class PortfolioPage {
  readonly page: Page;
  /** 添加资产/账户按钮 */
  readonly addButton: Locator;
  /** 组合设置按钮 */
  readonly settingsButton: Locator;
  /** 连接第一个账户 CTA（未连接引导态） */
  readonly connectFirstAccount: Locator;
  /** 连接到 Alva Agent */
  readonly alvaAgentLink: Locator;
  /** 侧边栏登录入口 */
  readonly sidebarLogin: Locator;

  constructor(page: Page) {
    this.page = page;
    this.addButton = page.getByRole('button', { name: 'Add', exact: true });
    this.settingsButton = page.getByRole('button', { name: 'Settings', exact: true });
    this.connectFirstAccount = page.getByRole('button', { name: /connect your first account/i });
    this.alvaAgentLink = page.getByRole('button', { name: /alva agent/i });
    this.sidebarLogin = page.locator('[data-testid="sidebar-login"]');
  }

  /** 打开真实组合页 /portfolio */
  async goto(): Promise<void> {
    logger.info('打开投资组合页 /portfolio');
    await this.page.goto('/portfolio');
    await this.page.waitForLoadState('domcontentloaded');
  }

  /** 断言组合页已渲染（标题与引导态可见） */
  async expectVisible(): Promise<void> {
    await expect(this.page.getByRole('heading', { name: /portfolio/i }).first()).toBeVisible({
      timeout: 15_000,
    });
    // 未登录时应有"连接账户"引导
    await expect(this.connectFirstAccount).toBeVisible({ timeout: 15_000 });
    logger.info('投资组合页可见（含连接账户引导态）');
  }

  /** 点击"连接第一个账户" */
  async clickConnectFirstAccount(): Promise<void> {
    await this.connectFirstAccount.click();
    logger.info('点击连接第一个账户');
  }

  /** 点击 Add */
  async clickAdd(): Promise<void> {
    await this.addButton.click();
    logger.info('点击 Add');
  }

  /** 点击 Settings */
  async clickSettings(): Promise<void> {
    await this.settingsButton.click();
    logger.info('点击 Settings');
  }

  /** 断言需要登录（出现 sidebar-login 入口） */
  async expectLoginPromptVisible(): Promise<void> {
    await expect(this.sidebarLogin).toBeVisible();
  }
}
