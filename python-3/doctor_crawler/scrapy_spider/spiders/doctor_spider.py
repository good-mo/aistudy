import re
import time
from collections.abc import AsyncIterator

import scrapy
from scrapy.http import HtmlResponse

from scrapy_spider.items import DoctorItem
from scrapy_spider.hs300_codes import HS300_CODES


class DoctorSpider(scrapy.Spider):
    """爬取同花顺诊股页面，提取综合诊断信息。

    支持两种模式：
      - 单只股票：scrapy crawl doctor -a code=600000
      - 全部沪深300：scrapy crawl doctor  （默认）
                     或 scrapy crawl doctor -a code=all
    """

    name = "doctor"
    allowed_domains = ["10jqka.com.cn"]

    # 默认爬取全部沪深300成分股；可通过 -a code=600999 指定单只
    code = "all"

    async def start(self) -> AsyncIterator[scrapy.Request]:
        """兼容 Scrapy 2.13+ 的 start 方法"""
        for req in self._build_requests():
            yield req

    # 兼容 Scrapy < 2.13
    def start_requests(self):
        return list(self._build_requests())

    def _build_requests(self):
        """根据 code 参数生成待爬取请求列表。"""
        if self.code and self.code.strip().lower() not in ("all", "hs300", "300"):
            # 单只股票模式
            url = f"https://doctor.10jqka.com.cn/{self.code.strip()}/"
            self.logger.info(f"[单只模式] 爬取 {self.code}")
            yield scrapy.Request(
                url, callback=self.parse_page, dont_filter=True,
                meta={"stock_code": self.code.strip()},
            )
            return

        # 批量模式：遍历全部沪深300 成分股
        self.logger.info(f"[沪深300模式] 共 {len(HS300_CODES)} 只股票开始批量爬取")
        for code, name in HS300_CODES:
            url = f"https://doctor.10jqka.com.cn/{code}/"
            yield scrapy.Request(
                url, callback=self.parse_page, dont_filter=True,
                meta={"stock_code": code, "stock_name": name},
            )

    def parse_page(self, response: HtmlResponse):
        item = DoctorItem()
        item["url"] = response.url
        item["title"] = response.xpath("//title/text()").get("").strip()
        item["text"] = "\n".join(
            [t.strip() for t in response.xpath("//body//text()").getall() if t.strip()]
        )
        item["links"] = response.xpath("//a/@href").getall()
        item["sections"] = self._extract_sections(response)
        item["crawled_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # 补充股票代码 / 名称（从 meta 获取，作为备用）
        stock_code = response.meta.get("stock_code", "")
        stock_name = response.meta.get("stock_name", "")
        if stock_code:
            item["stock_code"] = stock_code
        if stock_name:
            item["hs300_name"] = stock_name

        # 提取综合诊断数据
        self._extract_diagnosis(response, item)

        # 日志打印成功提取的股票
        self.logger.info(
            f"[OK] {item.get('stock_name', response.meta.get('stock_code', ''))} "
            f"诊断分: {item.get('diagnosis_score', 'N/A')}"
        )

        yield item

    def _extract_diagnosis(self, response: HtmlResponse, item: DoctorItem):
        """提取综合诊断（总分、评级、趋势、各维度评分）"""

        # --- 股票名称 ---
        stock_name = response.xpath(
            "//div[contains(@class, 'stockname')]//text()"
        ).get("")
        if stock_name:
            item["stock_name"] = stock_name.strip()

        # --- 综合诊断总分与打败百分比 ---
        # 结构: <div class="stockvalue"><span class="bignum">6</span><span class="smallnum">.7</span></div>
        bignum = response.xpath("//div[contains(@class, 'stockvalue')]//span[@class='bignum']/text()").get("")
        smallnum = response.xpath("//div[contains(@class, 'stockvalue')]//span[@class='smallnum']/text()").get("")
        if bignum and smallnum:
            item["diagnosis_score"] = f"{bignum.strip()}{smallnum.strip()}"

        # 综合诊断描述: 综合诊断：6.7分 打败了99%的股票！
        diagnosis_text = response.xpath(
            "//div[contains(@class, 'stocktotal')]/text()"
        ).get("")
        if diagnosis_text:
            item["diagnosis_text"] = diagnosis_text.strip()

        # 从描述中提取打败百分比
        beat_match = re.search(r"打败了(\d+)%", item.get("diagnosis_text", ""))
        if beat_match:
            item["beat_percent"] = int(beat_match.group(1))

        # --- 投资评级（卖出/减持/中性/增持/买入） ---
        ratings = []
        active_rating = None
        rating_items = response.xpath(
            "//div[contains(@class, 'value_bar')]//li"
        )
        for li in rating_items:
            name = li.xpath(".//span/text()").get("")
            has_cur = bool(li.xpath(".//span[contains(@class, 'cur')]"))
            if name:
                name = name.strip()
                ratings.append({"name": name, "active": has_cur})
                if has_cur:
                    active_rating = name
        if ratings:
            item["ratings"] = ratings
        if active_rating:
            item["rating"] = active_rating

        # --- 短期/中期/长期趋势 ---
        for li in response.xpath("//div[contains(@class, 'value_info')]//li"):
            label = li.xpath(".//span/text()").get("")
            value = li.xpath(".//p/text()").get("")
            if label and value:
                label = label.strip().rstrip("：:")
                value = value.strip()
                if label == "短期趋势":
                    item["short_term"] = value
                elif label == "中期趋势":
                    item["mid_term"] = value
                elif label == "长期趋势":
                    item["long_term"] = value

        # --- 各维度评分（技术面/资金面/消息面/行业面/基本面） ---
        dimensions = []
        # 每个维度在 <div class="box2wrap xxx_score"> 中，包含 <span class="title">诊断结果：<em>X.X</em></span>
        for wrapper in response.xpath("//div[contains(@class, 'box2wrap')]"):
            # 判断维度名称
            cls = wrapper.xpath("@class").get("") or ""
            name = None
            if "technical_score" in cls:
                name = "技术面"
            elif "funds_score" in cls:
                name = "资金面"
            elif "message_score" in cls:
                name = "消息面"
            elif "trade_score" in cls:
                name = "行业面"
            elif "basic_score" in cls:
                name = "基本面"

            if not name:
                continue

            # 评分
            score = wrapper.xpath(
                ".//span[contains(@class, 'title')]//em/text()"
            ).get("")
            # 打败百分比（从灰色文字中提取）
            gray_text = wrapper.xpath(
                ".//span[contains(@class, 'gray')]/text()"
            ).get("")
            beat = None
            if gray_text:
                beat_match = re.search(r"打败了(\d+)%", gray_text)
                if beat_match:
                    beat = int(beat_match.group(1))

            dimensions.append({
                "name": name,
                "score": score.strip() if score else None,
                "beat": beat,
                "text": gray_text.strip() if gray_text else "",
            })

        if dimensions:
            item["dimensions"] = dimensions

    def _extract_sections(self, response: HtmlResponse):
        """按 h1-h6 标题将页面内容分块提取"""
        sections = []
        nodes = response.xpath(
            "//body//*[self::h1 or self::h2 or self::h3 "
            "or self::h4 or self::h5 or self::h6]"
        )
        for node in nodes:
            title = node.xpath("string(.)").get("").strip()
            if not title:
                continue
            # 当前标题到下一个标题之间的兄弟节点文本
            text = self._siblings_text(node)
            sections.append({"title": title, "text": text})
        return sections

    def _siblings_text(self, node):
        parts = []
        for sibling in node.xpath(
            "following-sibling::*[not(self::h1 or self::h2 or self::h3 "
            "or self::h4 or self::h5 or self::h6)]"
        ):
            # 遇到下一个标题停止
            t = sibling.xpath("string(.)").get("").strip()
            if not t:
                continue
            parts.append(t)
            # 简化：仅取紧随其后的若干内容
        return "\n".join(parts[:50])
