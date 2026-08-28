/**
 * pages/chat.page.ts — 对话页面对象（真实 alva.ai）
 *
 * 基于 alva.ai 真实 `/new_chat` 页面的 DOM 结构重写。
 * 真实平台是一个聊天式 AI 投资助手：核心交互是在
 * `[data-testid="homepage-hero-input"]` 中的 textarea 输入指令，
 * 或点击模板 skill 芯片（Backtest / Smart Screener / Alpha Radar 等）
 * 来发起业务闭环。
 *
 * 参考真实路由：/new_chat（对话）、/portfolio、/explore、/login
 */
import { Page, Locator, expect } from '@playwright/test';
import { logger } from '../utils/logger';

/** 侧边栏主导航项 */
export type SidebarNav = 'new_chat' | 'explore' | 'portfolio' | 'markets';

/** 模板 skill 名称（真实 /new_chat 页面上可点击的芯片） */
export const CHAT_SKILLS = [
  'Fintwit Roundtable',
  'Asset Deepdive',
  'Backtest',
  'Smart Screener',
  'Theme Tracker',
  'AI Digest',
  'Earnings',
  'Catalyst Calendar',
  'Competitive Landscape',
  'Peer Comps',
  'DCF Valuation',
  'Idea Generation',
  'Morning Note',
  'Valuation Update',
  'Sector Overview',
  'Ticker Read',
  'Watchlist Digest',
  'Portfolio Digest',
  'Why the Move',
  'Quick Backtest',
  'What investors care about',
  'Alvest — Trading Agent',
  'Pre-earning Analysis',
  'Alpha Radar Setup',
] as const;

export class ChatPage {
  readonly page: Page;

  /** 真实输入区：homepage-hero-input 区块内的 textarea */
  readonly heroInput: Locator;
  /** 真实 textarea（按 placeholder 定位，最稳） */
  readonly chatInput: Locator;
  /** 发起语音输入按钮 */
  readonly voiceInputButton: Locator;
  /** 添加 mention/file 按钮 */
  readonly attachButton: Locator;
  /** 侧边栏登录入口 */
  readonly sidebarLogin: Locator;

  constructor(page: Page) {
    this.page = page;
    // 真实平台输入框是 hero 区块内的 contenteditable 编辑器（Lexical），
    // SSR 阶段是 textarea，水合后变为 role=textbox 的可编辑 div
    this.heroInput = page.locator('[data-testid="homepage-hero-input"]');
    this.chatInput = page.locator(
      '[data-testid="homepage-hero-input"] [role="textbox"][contenteditable="true"], [data-testid="homepage-hero-input"] textarea',
    );
    this.voiceInputButton = page.getByRole('button', { name: /start voice input/i });
    this.attachButton = page.getByRole('button', { name: /add mention or file/i });
    this.sidebarLogin = page.locator('[data-testid="sidebar-login"]');
  }

  /** 打开真实对话页面 /new_chat */
  async goto(): Promise<void> {
    logger.info('打开对话页面 /new_chat');
    await this.page.goto('/new_chat');
    await this.page.waitForLoadState('domcontentloaded');
    // 等待 hero 输入区真正渲染（Next.js 水合完成）
    await expect(this.heroInput).toBeVisible({ timeout: 30_000 }).catch(() => {});
  }

  /** 断言对话页已就绪（输入框可见） */
  async expectReady(): Promise<void> {
    await expect(this.heroInput).toBeVisible({ timeout: 30_000 });
    await expect(this.chatInput).toBeVisible({ timeout: 15_000 });
    logger.info('对话页输入框可见');
  }

  /** 输入一条消息 */
  async inputMessage(message: string): Promise<void> {
    logger.info(`输入对话消息: ${message.slice(0, 60)}`);
    await this.chatInput.fill(message);
  }

  /** 点击某个模板 skill 芯片，返回是否命中 */
  async clickSkill(skill: string): Promise<boolean> {
    logger.info(`点击 skill 芯片: ${skill}`);
    const chip = this.page
      .locator('.homepage-template-chip')
      .filter({ hasText: skill })
      .first();
    if ((await chip.count()) === 0) {
      logger.warn(`skill 芯片未找到: ${skill}`);
      return false;
    }
    // 若芯片在当前视口不可见（折叠在 More 菜单内），先点击 More 展开
    if (!(await chip.isVisible().catch(() => false))) {
      logger.info(`skill 在 More 菜单内，先展开: ${skill}`);
      const more = this.page
        .locator('.homepage-template-chip')
        .filter({ hasText: 'More' })
        .first();
      if (await more.isVisible().catch(() => false)) {
        await more.click();
        await this.page.waitForTimeout(500);
      }
    }
    await chip.click();
    return true;
  }

  /** 通过侧边栏跳转到指定导航 */
  async navigateTo(nav: SidebarNav): Promise<void> {
    const urlMap: Record<SidebarNav, string> = {
      new_chat: '/new_chat',
      explore: '/explore',
      portfolio: '/portfolio',
      markets: '/markets',
    };
    logger.info(`侧边栏导航到: ${nav}`);
    await this.page.goto(urlMap[nav]);
    await this.page.waitForLoadState('domcontentloaded');
  }

  /** 断言页面显示指定 skill 芯片 */
  async expectSkillVisible(skill: string): Promise<void> {
    await expect(
      this.page.locator('.homepage-template-chip').filter({ hasText: skill }).first(),
    ).toBeVisible();
  }

  /** 点击侧边栏登录入口 */
  async clickLogin(): Promise<void> {
    await this.sidebarLogin.click();
    logger.info('点击侧边栏登录入口');
  }
}
