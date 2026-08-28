"""使用 Playwright 渲染并抓取同花顺诊股页面全部内容"""

import asyncio
import json
import os
import time
from pathlib import Path

from playwright.async_api import async_playwright

TARGET_URL = "https://doctor.10jqka.com.cn/600999/"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"


async def fetch_page(page, url: str) -> dict:
    # 等待页面加载，并滚动到底部以触发懒加载内容
    await page.goto(url, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(3000)

    # 多次滚动到底部，确保动态内容全部加载
    for _ in range(5):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1500)

    # 收集页面信息
    data = {
        "url": page.url,
        "title": await page.title(),
        "html": await page.content(),  # 渲染后的完整 HTML
        "text": await page.evaluate(
            "() => document.body.innerText"
        ),
        "links": await page.evaluate(
            "() => Array.from(document.querySelectorAll('a')).map(a => a.href)"
        ),
        "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return data


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        try:
            data = await fetch_page(page, TARGET_URL)
        finally:
            await browser.close()

    # 保存完整 HTML
    html_path = OUTPUT_DIR / "doctor_playwright.html"
    html_path.write_text(data["html"], encoding="utf-8")

    # 保存结构化数据（去掉超大 html 字段）
    summary = {k: v for k, v in data.items() if k != "html"}
    json_path = OUTPUT_DIR / "doctor_playwright.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[OK] HTML 已保存到: {html_path}")
    print(f"[OK] JSON 已保存到: {json_path}")
    print(f"[INFO] 抓取页面标题: {summary.get('title')}")


if __name__ == "__main__":
    asyncio.run(main())
