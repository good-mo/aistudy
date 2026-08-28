/**
 * pages/alert.page.ts — 告警页面对象（真实 alva.ai）
 *
 * 重要说明：真实 alva.ai **没有独立的 /alerts 路由表单页**。
 * "Alert"（价格/指标告警 / Alpha Radar）同样是**通过对话式 skill 发起**的——
 * 用户在 /new_chat 输入"帮我设置 AAPL 价格超过 200 的告警"等指令，
 * 或点击 "Alpha Radar Setup" 等 skill 芯片来配置告警闭环。
 * （登录后侧边栏会出现 Alerts 标签，但那是登录态能力，本框架对齐未登录入口。）
 */
import { Page, Locator, expect } from '@playwright/test';
import { logger } from '../utils/logger';

/** 与"告警/雷达"相关的真实 skill 名称 */
export const ALERT_SKILLS = ['Alpha Radar Setup', 'Why the Move'] as const;

/** 告警配置参数（对话式指令） */
export interface AlertConfig {
  name?: string;
  ticker: string;
  /** 告警条件：above / below */
  condition: 'above' | 'below';
  threshold: number;
}

export class AlertPage {
  readonly page: Page;
  readonly heroInput: Locator;
  readonly chatInput: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heroInput = page.locator('[data-testid="homepage-hero-input"]');
    // 真实输入框是 contenteditable 编辑器（水合后替换 SSR 的 textarea）
    this.chatInput = page.locator(
      '[data-testid="homepage-hero-input"] [role="textbox"][contenteditable="true"], [data-testid="homepage-hero-input"] textarea',
    );
  }

  /** 打开真实对话页 /new_chat（告警闭环从对话发起） */
  async goto(): Promise<void> {
    logger.info('打开对话页以发起告警配置');
    await this.page.goto('/new_chat');
    await this.page.waitForLoadState('domcontentloaded');
    await expect(this.heroInput).toBeVisible({ timeout: 30_000 }).catch(() => {});
  }

  /** 断言告警入口（对话输入区）可用 */
  async expectVisible(): Promise<void> {
    await expect(this.heroInput).toBeVisible({ timeout: 30_000 });
    await expect(this.chatInput).toBeVisible({ timeout: 15_000 });
    logger.info('告警入口（对话输入区）可见');
  }

  /** 通过对话指令创建一条告警 */
  async createAlert(config: AlertConfig): Promise<void> {
    const dir = config.condition === 'above' ? '超过' : '低于';
    const prompt = `请为 ${config.ticker} 设置价格${dir} $${config.threshold} 的告警`;
    logger.info(`通过对话发起告警: ${prompt}`);
    await this.chatInput.fill(prompt);
    await this.chatInput.press('Enter');
  }

  /** 通过 Alpha Radar 这个告警类 skill 发起 */
  async launchAlphaRadar(): Promise<boolean> {
    return this.launchSkill('Alpha Radar Setup');
  }

  /** 断言 skill 已成功加载（URL 携带 template 参数） */
  async expectSkillLoaded(skillSlug: string): Promise<void> {
    // URL 形如 /new_chat?template=alva%2F<slug>，skillSlug 作为 slug 子串即可
    await expect(this.page).toHaveURL(new RegExp(`template=.*${skillSlug}`), {
      timeout: 15_000,
    });
    logger.info(`告警类 skill 已加载: ${skillSlug}`);
  }

  /** 通过 skill 芯片发起（自动展开 More 菜单） */
  async launchSkill(skill: string): Promise<boolean> {
    logger.info(`发起告警类 skill: ${skill}`);
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

  /** 断言告警指令已提交（页面进入会话态） */
  async expectSubmitted(): Promise<void> {
    await expect(this.page).toHaveURL(/new_chat/, { timeout: 15_000 });
    logger.info('告警指令已提交');
  }
}
