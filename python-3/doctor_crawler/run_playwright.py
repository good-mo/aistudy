#!/usr/bin/env python3
"""Playwright 爬虫入口脚本"""
from playwright_scraper.doctor_playwright import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
