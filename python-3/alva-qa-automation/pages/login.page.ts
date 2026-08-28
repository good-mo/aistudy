/**
 * pages/login.page.ts — 登录页面对象（真实 alva.ai）
 *
 * 基于 alva.ai 真实 `/login` 页面 DOM 结构。
 * 真实平台登录入口：
 *  - 社交登录按钮：data-testid = login-popup-{google|twitter|telegram|discord}
 *  - 邮箱登录：input[placeholder="Login with Email"]
 *  - 访问受保护路由（如 /settings、/portfolio 深层）会 302 到 /login?returnTo=...
 */
import { Page, Locator, expect } from '@playwright/test';
import { logger } from '../utils/logger';

export type SocialProvider = 'google' | 'twitter' | 'telegram' | 'discord';

export class LoginPage {
  readonly page: Page;
  /** 邮箱输入框 */
  readonly emailInput: Locator;
  /** 各社交登录按钮 */
  readonly socialButtons: Record<SocialProvider, Locator>;

  constructor(page: Page) {
    this.page = page;
    this.emailInput = page.locator('input[placeholder="Login with Email"], input[type="email"]');
    this.socialButtons = {
      google: page.locator('[data-testid="login-popup-google"]'),
      twitter: page.locator('[data-testid="login-popup-twitter"]'),
      telegram: page.locator('[data-testid="login-popup-telegram"]'),
      discord: page.locator('[data-testid="login-popup-discord"]'),
    };
  }

  /** 打开登录页（真实路由 /login） */
  async goto(): Promise<void> {
    logger.info('打开登录页 /login');
    await this.page.goto('/login');
    await this.page.waitForLoadState('domcontentloaded');
  }

  /** 断言登录页已渲染（Google 登录按钮可见） */
  async expectVisible(): Promise<void> {
    await expect(this.socialButtons.google).toBeVisible({ timeout: 15_000 });
    logger.info('登录页可见');
  }

  /** 点击指定社交登录入口 */
  async loginWith(provider: SocialProvider): Promise<void> {
    logger.info(`通过 ${provider} 发起登录`);
    await this.socialButtons[provider].click();
  }

  /** 输入邮箱（邮箱登录的第一步） */
  async fillEmail(email: string): Promise<void> {
    logger.info(`输入登录邮箱: ${email}`);
    await this.emailInput.fill(email);
  }

  /** 断言存在邮箱输入框 */
  async expectEmailInputVisible(): Promise<void> {
    await expect(this.emailInput).toBeVisible();
  }
}
