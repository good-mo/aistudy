/**
 * pages/explore.page.ts — 探索页面对象（真实 alva.ai）
 *
 * 基于 alva.ai 真实 `/explore` 页面的 DOM 结构。
 * 页面展示社区 playbook 卡片，每张卡片含：
 *  - 链接：/u/{author}/playbooks/{slug}
 *  - 标题、作者、简介、价格/公开状态、订阅人数等
 */
import { Page, Locator, expect } from '@playwright/test';
import { logger } from '../utils/logger';

export class ExplorePage {
  readonly page: Page;
  /** 探索页 playbook 卡片容器（链接到 /u/.../playbooks/...） */
  readonly playbookLinks: Locator;
  /** 侧边栏登录入口 */
  readonly sidebarLogin: Locator;

  constructor(page: Page) {
    this.page = page;
    this.playbookLinks = page.locator('a[href*="/playbooks/"]');
    this.sidebarLogin = page.locator('[data-testid="sidebar-login"]');
  }

  /** 打开真实探索页 /explore */
  async goto(): Promise<void> {
    logger.info('打开探索页 /explore');
    await this.page.goto('/explore');
    await this.page.waitForLoadState('domcontentloaded');
  }

  /** 断言探索页已渲染 */
  async expectVisible(): Promise<void> {
    await expect(this.page.getByText('Explore', { exact: true }).first()).toBeVisible({
      timeout: 15_000,
    });
    logger.info('探索页可见');
  }

  /** 断言存在可浏览的 playbook 卡片 */
  async expectPlaybooksVisible(): Promise<void> {
    await expect(this.playbookLinks.first()).toBeVisible({ timeout: 15_000 });
    const count = await this.playbookLinks.count();
    logger.info(`探索页共展示 ${count} 个 playbook 卡片`);
  }

  /** 打开第一个 playbook 卡片 */
  async openFirstPlaybook(): Promise<void> {
    const first = this.playbookLinks.first();
    await first.waitFor({ state: 'visible', timeout: 15_000 });
    const href = await first.getAttribute('href');
    logger.info(`打开 playbook: ${href}`);
    await first.click();
  }

  /** 统计当前可见的 playbook 数量 */
  async countPlaybooks(): Promise<number> {
    return this.playbookLinks.count();
  }
}
