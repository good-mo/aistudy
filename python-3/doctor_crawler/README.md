# 同花顺股票行情爬虫 (Doctor Crawler)

使用 **Playwright** 和 **Scrapy** 爬取同花顺个股诊股页面
`https://doctor.10jqka.com.cn/{code}/` 中的综合诊断数据。

支持**批量爬取沪深300全部成分股**的综合诊断数据。

## 目录结构

```
doctor_crawler/
├── requirements.txt            # Python 依赖
├── README.md                   # 项目说明
├── run_scrapy.sh               # 运行 Scrapy 爬虫脚本
├── run_playwright.py           # 运行 Playwright 脚本
├── scrapy_spider/              # Scrapy 爬虫
│   ├── __init__.py
│   ├── hs300_codes.py          # 沪深300 成分股代码列表
│   ├── items.py                # Scrapy 数据项定义
│   ├── settings.py             # Scrapy 配置
│   └── spiders/
│       ├── __init__.py
│       └── doctor_spider.py    # 主爬虫
├── playwright_scraper/         # Playwright 爬虫
│   └── __init__.py
└── data/                       # 抓取结果输出目录
```

## 安装依赖

```bash
pip install -r requirements.txt

# Playwright 还需要安装浏览器
playwright install chromium
```

## 使用方法

### 1. Scrapy 爬虫

**批量爬取沪深300全部成分股：**

```bash
cd doctor_crawler
./run_scrapy.sh
# 或直接
scrapy crawl doctor -o data/doctor_scrapy.json
```

**爬取单只股票（如招商证券 600999）：**

```bash
cd doctor_crawler
./run_scrapy.sh 600999
# 或直接
scrapy crawl doctor -a code=600999 -o data/doctor_scrapy.json
```

### 2. Playwright 爬虫

```bash
cd doctor_crawler
python run_playwright.py
```

## 数据输出

- Scrapy: `data/doctor_scrapy.json`
- Playwright: `data/doctor_playwright.html` 与 `data/doctor_playwright.json`

## Scrapy 提取的字段

爬虫爬取每只股票时提取以下综合诊断数据：

| 字段 | 说明 | 示例 |
|------|------|------|
| `stock_code` | 股票代码 | `600999` |
| `hs300_name` | 沪深300成分股名称 | `招商证券` |
| `stock_name` | 页面显示的股票名称和代码 | `招商证券（600999）` |
| `diagnosis_score` | 综合诊断评分 | `6.7` |
| `diagnosis_text` | 综合诊断描述 | `综合诊断：6.7分 打败了99%的股票！` |
| `beat_percent` | 打败的股票百分比 | `99` |
| `rating` | 当前投资评级 | `增持` |
| `ratings` | 全部评级列表 | `[{name: 卖出, active: false}, ...]` |
| `short_term` | 短期趋势 | `股价的强势特征已经确立，短线可能回调。` |
| `mid_term` | 中期趋势 | `回落整理中且下跌有加速趋势。` |
| `long_term` | 长期趋势 | `已有105家主力机构披露...` |
| `dimensions` | 各维度评分列表 | `[{name: 技术面, score: 6.6, beat: 81}, ...]` |

`dimensions` 包含五个维度：技术面、资金面、消息面、行业面、基本面。

## 目标页面

`https://doctor.10jqka.com.cn/{股票代码}/`
同花顺「诊股」页面，包含个股基本面、资金流向、技术面、机构评级等信息。

## 沪深300 成分股

成分股列表保存在 `scrapy_spider/hs300_codes.py` 中，共 300 只，
数据来源为 `share300_core/config/constants.py`。
