/**
 * tests/01-onboarding.spec.ts — 登录/入口测试（真实 alva.ai）
 *
 * 基于 alva.ai 真实页面结构：
 *  - 登录页 /login：社交登录 login-popup-{google|twitter|telegram|discord} + 邮箱输入
 *  - 访问受保护路由会 302 到 /login?returnTo=...
 *  - 侧边栏登录入口 data-testid="sidebar-login"
 *
 * 注：真实平台**无独立注册页**，账号体系走社交/邮箱登录，
 * 因此本文件聚焦"登录入口可用 + 受保护路由引导登录"的真实闭环。
 */
import { test, expect } from './fixtures';
import { LoginPage } from '../pages/login.page';
import { ChatPage } from '../pages/chat.page';
import { logger } from '../utils/logger';

test.describe('Onboarding - 登录与入口', () => {
  test('登录页可正常渲染且提供社交登录入口', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.expectVisible();

    // 四个社交登录入口均存在
    for (const provider of ['google', 'twitter', 'telegram', 'discord'] as const) {
      await expect(loginPage.socialButtons[provider]).toBeVisible();
    }
    await loginPage.expectEmailInputVisible();
    logger.info('登录页渲染完整：4 个社交入口 + 邮箱输入');
  });

  test('访问受保护路由会引导到登录页', async ({ page }) => {
    // 未登录访问 /settings 应被重定向到 /login
    await page.goto('/settings');
    await page.waitForLoadState('domcontentloaded');
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
    await expect(page.locator('[data-testid="login-popup-google"]')).toBeVisible();
    logger.info('受保护路由正确引导至登录页');
  });

  test('侧边栏登录入口可点击', async ({ page }) => {
    const chatPage = new ChatPage(page);
    await chatPage.goto();
    await chatPage.expectReady();
    await chatPage.clickLogin();
    logger.info('侧边栏登录入口可点击');
  });

  test('登录页可输入邮箱', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    const email = `qa+${Date.now()}@test.com`;
    await loginPage.fillEmail(email);
    await expect(loginPage.emailInput).toHaveValue(email);
    logger.info(`邮箱输入正常: ${email}`);
  });
});
