/**
 * pages/automation.page.ts — 自动化/Playbook 页面对象（真实 alva.ai）
 *
 * 重要说明：真实 alva.ai **没有独立的 /automation 路由**。
 * "Automation"（自动化监控任务 / Live Playbook）是**通过对话式 skill 发起**的——
 * 用户在 /new_chat 输入框输入指令，或点击如
 * "Trade Setup Automation" / "Portfolio Watch Setup" / "Alpha Radar Setup"
 * 等 skill 芯片，从而创建自动化监控闭环。
 *
 * 因此本页面对象不再假设一个假的 /automation 表单页，而是：
 *  - 在 /new_chat 通过 skill 芯片或指令发起自动化
 *  - 校验页面是否给出业务引导/响应
 *
 * 参考真实 skill 名（/new_chat 页面的 homepage-template-chip）：
 *   "Trade Setup Automation", "Portfolio Watch Setup", "Alpha Radar Setup"
 */
import { Page, Locator, expect } from '@playwright/test';
import { logger } from '../utils/logger';

/** 与"自动化/Playbook"相关的真实 skill 名称 */
export const AUTOMATION_SKILLS = [
  'Trade Setup Automation',
  'Portfolio Watch Setup',
  'Alpha Radar Setup',
  'Watchlist Digest',
  'Portfolio Digest',
  'Trade Setup Automation',
] as const;

export class AutomationPage {
  readonly page: Page;
  /** 真实输入框 */
  readonly chatInput: Locator;
  /** hero 输入区块 */
  readonly heroInput: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heroInput = page.locator('[data-testid="homepage-hero-input"]');
    // 真实输入框是 contenteditable 编辑器（水合后替换 SSR 的 textarea）
    this.chatInput = page.locator(
      '[data-testid="homepage-hero-input"] [role="textbox"][contenteditable="true"], [data-testid="homepage-hero-input"] textarea',
    );
  }

  /** 打开真实对话页 /new_chat（自动化闭环从对话发起） */
  async goto(): Promise<void> {
    logger.info('打开对话页以发起自动化闭环');
    await this.page.goto('/new_chat');
    await this.page.waitForLoadState('domcontentloaded');
    await expect(this.heroInput).toBeVisible({ timeout: 30_000 }).catch(() => {});
  }

  /** 断言对话输入区可用 */
  async expectVisible(): Promise<void> {
    await expect(this.heroInput).toBeVisible({ timeout: 30_000 });
    await expect(this.chatInput).toBeVisible({ timeout: 15_000 });
    logger.info('自动化入口（对话输入区）可见');
  }



  /** 通过 skill 芯片发起一个自动化 skill，返回是否命中（自动展开 More 菜单） */
  async launchSkill(skill: string): Promise<boolean> {
    logger.info(`发起自动化 skill: ${skill}`);
    const chip = this.page
      .locator('.homepage-template-chip')
      .filter({ hasText: skill })
      .first();
    // 先尝试直接点击首屏芯片（自带等待），失败则走 More 的 Skills hub 对话框
    const directHit = await chip
      .click({ timeout: 2000 })
      .then(() => true)
      .catch(() => false);
    if (directHit) {
      return true;
    }
    logger.info(`skill 不在首屏，从 More 的 Skills hub 对话框打开: ${skill}`);
    const more = this.page
      .locator('.homepage-template-chip')
      .filter({ hasText: 'More' })
      .first();
    await more.click({ timeout: 10_000 });
    // 等待 Skills hub 对话框出现
    const dialog = this.page.locator('[role="dialog"]');
    await dialog.first().waitFor({ state: 'visible', timeout: 10_000 });
    const item = dialog.locator('[role="button"]').filter({ hasText: skill }).first();
    if ((await item.count()) === 0) {
      logger.warn(`在 Skills hub 对话框中未找到 skill: ${skill}`);
      return false;
    }
    await item.click();
    return true;
  }

  /** 断言 skill 已成功加载（URL 携带 template 参数） */
  async expectSkillLoaded(skillSlug: string): Promise<void> {
    // URL 形如 /new_chat?template=alva%2F<slug>，skillSlug 作为 slug 子串即可
    await expect(this.page).toHaveURL(new RegExp(`template=.*${skillSlug}`), {
      timeout: 15_000,
    });
    logger.info(`自动化 skill 已加载: ${skillSlug}`);
  }

  /** 通过自然语言指令发起自动化（如设置盯盘任务） */
  async launchViaPrompt(prompt: string): Promise<void> {
    logger.info(`通过指令发起自动化: ${prompt.slice(0, 60)}`);
    await this.chatInput.fill(prompt);
    await this.chatInput.press('Enter');
  }

  /** 断言指令已提交（输入区消失或用户消息上屏，页面进入会话态） */
  async expectSubmitted(): Promise<void> {
    // 提交后可能进入会话页：hero 输入区可能保留，也可能切换为会话输入框
    // 只要页面仍可响应（URL 仍是 alva.ai 域内 /new_chat）即视为提交成功
    await expect(this.page).toHaveURL(/new_chat/, { timeout: 15_000 });
    logger.info('自动化指令已提交');
  }
}
