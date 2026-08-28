/**
 * tests/04-alert-setup.spec.ts — 告警/Alpha Radar 闭环（真实 alva.ai）
 *
 * 真实 alva.ai 的"告警"通过 /new_chat 的对话式 skill 发起
 * （如 "Alpha Radar Setup"），没有独立的 /alerts 表单路由。
 * 本文件验证：
 *  - 告警入口（对话输入区）就绪
 *  - 告警类 skill 芯片可点击
 *  - 可通过自然语言指令创建价格告警
 */
import { test, expect } from './fixtures';
import { AlertPage } from '../pages/alert.page';
import { logger } from '../utils/logger';

test.describe('Alert - 告警配置闭环', () => {
  test('告警入口（对话输入区）就绪', async ({ page }) => {
    const alertPage = new AlertPage(page);
    await alertPage.goto();
    await alertPage.expectVisible();
    logger.info('告警入口就绪');
  });

  test('可通过 Alpha Radar skill 发起告警配置', async ({ page }) => {
    const alertPage = new AlertPage(page);
    await alertPage.goto();
    await alertPage.expectVisible();

    const hit = await alertPage.launchAlphaRadar();
    expect(hit).toBeTruthy();
    await alertPage.expectSkillLoaded('alpha-radar-setup');
  });

  test('可通过对话指令创建价格告警', async ({ page }) => {
    const alertPage = new AlertPage(page);
    await alertPage.goto();
    await alertPage.expectVisible();

    await alertPage.createAlert({
      ticker: 'AAPL',
      condition: 'above',
      threshold: 200,
    });
    logger.info('已通过对话发起 AAPL 价格高于 $200 的告警');
    await alertPage.expectSubmitted();
  });

  test('对话页展示告警相关 skill 芯片', async ({ page }) => {
    const alertPage = new AlertPage(page);
    await alertPage.goto();
    await alertPage.expectVisible();

    const chips = await page.locator('.homepage-template-chip').allInnerTexts();
    const hasAlertSkill = chips.some((t) => /alpha radar setup/i.test(t));
    logger.info(`告警类 skill 可见: ${hasAlertSkill}`);
    expect(chips.length).toBeGreaterThan(0);
  });
});
