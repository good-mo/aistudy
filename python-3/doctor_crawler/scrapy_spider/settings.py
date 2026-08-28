# Scrapy settings for doctor_crawler
BOT_NAME = "scrapy_spider"

SPIDER_MODULES = ["scrapy_spider.spiders"]
NEWSPIDER_MODULE = "scrapy_spider.spiders"

# 遵守 robots.txt
ROBOTSTXT_OBEY = False

# 请求并发设置（批量爬取 300 只股票时适当调高并发）
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 4
DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = True

# 禁止 cookie
COOKIES_ENABLED = False

# 设置 UA，避免被目标站点拦截
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# 输出编码
FEED_EXPORT_ENCODING = "utf-8"

# 失败重试
RETRY_ENABLED = True
RETRY_TIMES = 2
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]
DOWNLOAD_TIMEOUT = 30
