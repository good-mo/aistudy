#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯 K 线接口 (web.ifzq.gtimg.cn) 完整测试工具
用于诊断接口是否可用、参数是否正确、数据是否正常
"""

import requests
import json
import time
import random
import sys
from datetime import datetime, timedelta


# ========== 配置 ==========
BASE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://stockapp.finance.qq.com/",
    "Accept": "application/json, text/plain, */*",
}
TIMEOUT = 15  # 秒


# ========== 工具函数 ==========
def build_url(stock_code, period="day", start_date="", end_date="",
              count=10, fq="qfq"):
    """
    构造请求 URL
    参数:
        stock_code: 股票代码，如 sh000001, sz000001, sh600519
        period:     K线周期 - day/week/month/m5/m15/m30/m60
        start_date: 开始日期 YYYY-MM-DD（分钟线可留空）
        end_date:   结束日期 YYYY-MM-DD（分钟线可留空）
        count:      数据条数，最大 640
        fq:         复权类型 - qfq(前复权) / hfq(后复权) / 空字符串(不复权)
    """
    param = f"{stock_code},{period},{start_date},{end_date},{count},{fq}"
    return f"{BASE_URL}?param={param}"


def safe_request(url, max_retries=2):
    """带重试和随机延迟的安全请求"""
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                wait = random.uniform(2, 5)
                print(f"  ⏳ 第 {attempt} 次重试，等待 {wait:.1f}s ...")
                time.sleep(wait)
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            return resp
        except requests.exceptions.Timeout:
            print(f"  ❌ 请求超时 (第 {attempt} 次)")
        except requests.exceptions.ConnectionError as e:
            print(f"  ❌ 连接失败: {e}")
        except Exception as e:
            print(f"  ❌ 未知错误: {e}")
    return None


def parse_kline_data(result_json, stock_code):
    """解析返回的 K 线数据，自动识别数据 key"""
    data = result_json.get("data", {})
    stock_data = data.get(stock_code, {})
    if not stock_data:
        return None, "返回数据中找不到该股票代码"
    # 腾讯接口返回的 key 不固定，需要自动探测
    possible_keys = [
        "qfqday", "qfqweek", "qfqmonth",
        "hfqday", "hfqweek", "hfqmonth",
        "day", "week", "month",
        "qfqm5", "qfqm15", "qfqm30", "qfqm60",
        "m5", "m15", "m30", "m60",
    ]
    for key in possible_keys:
        if key in stock_data and stock_data[key]:
            return key, stock_data[key]
    # 如果都不匹配，列出实际存在的 key
    available_keys = list(stock_data.keys())
    return None, f"未找到已知数据 key，实际返回的 keys: {available_keys}"


# ========== 测试函数 ==========
def test_connectivity():
    """测试 1: 基础连通性"""
    print("=" * 60)
    print("【测试 1】基础连通性测试")
    print("=" * 60)
    # 修复：使用真实近期日期，而非未来日期
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    url = build_url("sh000001", "day", start, end, 5, "qfq")
    print(f"请求 URL:\n  {url}\n")
    resp = safe_request(url)
    if resp is None:
        print("❌ 结论: 接口不可达，可能是网络问题或接口已下线\n")
        return False
    print(f"HTTP 状态码: {resp.status_code}")
    print(f"响应头 Content-Type: {resp.headers.get('Content-Type', '未知')}")
    print(f"响应长度: {len(resp.text)} 字符")
    if resp.status_code != 200:
        print(f"❌ 结论: HTTP 状态码异常 ({resp.status_code})")
        print(f"响应内容: {resp.text[:500]}\n")
        return False
    # 尝试解析 JSON
    try:
        result = resp.json()
        print(f"JSON 解析: ✅ 成功")
        print(f"code 字段: {result.get('code', '不存在')}")
        print(f"msg 字段: {result.get('msg', '不存在')}")
        if result.get("code") == 0:
            print("✅ 结论: 接口连通正常，返回数据正常\n")
            return True
        else:
            print(f"⚠️ 结论: 接口连通但返回异常 code\n")
            print(f"完整返回: {json.dumps(result, ensure_ascii=False, indent=2)[:1000]}\n")
            return False
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
        print(f"响应前 500 字符: {resp.text[:500]}\n")
        return False


def test_kline_data(stock_code="sh000001", period="day", days_back=10):
    """测试 2: K 线数据获取"""
    print("=" * 60)
    print(f"【测试 2】K 线数据获取 - {stock_code} {period}")
    print("=" * 60)
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    url = build_url(stock_code, period, start, end, 640, "qfq")
    print(f"请求参数: {stock_code} | {period} | {start}~{end} | 前复权\n")
    resp = safe_request(url)
    if resp is None:
        print("❌ 请求失败\n")
        return
    try:
        result = resp.json()
    except:
        print(f"❌ JSON 解析失败\n")
        return
    if result.get("code") != 0:
        print(f"❌ 接口返回错误: code={result.get('code')}, msg={result.get('msg')}\n")
        return
    data_key, data = parse_kline_data(result, stock_code)
    if data_key is None:
        print(f"❌ 数据解析失败: {data}\n")
        return
    print(f"✅ 数据 key: {data_key}")
    print(f"✅ 数据条数: {len(data)}")
    # 展示前 3 条和后 3 条
    print(f"\n前 3 条数据:")
    print(f"  {'日期':<12} {'开盘':>8} {'收盘':>8} {'最高':>8} {'最低':>8} {'成交量':>12}")
    print(f"  {'-'*68}")
    for row in data[:3]:
        if len(row) >= 6:
            # 修复：row[0], row[1]... 替代之前的 HTML 标签
            print(f"  {row[0]:<12} {row[1]:>8} {row[2]:>8} {row[3]:>8} {row[4]:>8} {row[5]:>12}")
    if len(data) > 6:
        print(f"  ...")
    for row in data[-3:]:
        if len(row) >= 6:
            print(f"  {row[0]:<12} {row[1]:>8} {row[2]:>8} {row[3]:>8} {row[4]:>8} {row[5]:>12}")
    print()


def test_all_periods(stock_code="sh000001"):
    """测试 3: 各周期 K 线"""
    print("=" * 60)
    print(f"【测试 3】各周期 K 线测试 - {stock_code}")
    print("=" * 60)
    periods = ["day", "week", "month"]
    for period in periods:
        url = build_url(stock_code, period, "", "", 5, "qfq")
        resp = safe_request(url)
        if resp is None:
            print(f"  {period:>6}: ❌ 请求失败")
            continue
        try:
            result = resp.json()
            data_key, data = parse_kline_data(result, stock_code)
            if data_key and data:
                print(f"  {period:>6}: ✅ {len(data)} 条 (key={data_key})")
            else:
                print(f"  {period:>6}: ⚠️ 无数据 ({data})")
        except:
            print(f"  {period:>6}: ❌ 解析失败")
    print()


def test_all_fq_types(stock_code="sh600519"):
    """测试 4: 各复权类型"""
    print("=" * 60)
    print(f"【测试 4】复权类型测试 - {stock_code}")
    print("=" * 60)
    fq_types = [("qfq", "前复权"), ("hfq", "后复权"), ("", "不复权")]
    for fq_code, fq_name in fq_types:
        url = build_url(stock_code, "day", "", "", 3, fq_code)
        resp = safe_request(url)
        if resp is None:
            print(f"  {fq_name}: ❌ 请求失败")
            continue
        try:
            result = resp.json()
            data_key, data = parse_kline = parse_kline_data(result, stock_code)
            if data_key and data:
                latest_close = data[-1][2]  # 修复：data[-1][2]
                print(f"  {fq_name}: ✅ 最新收盘价={latest_close} (key={data_key})")
            else:
                print(f"  {fq_name}: ⚠️ 无数据")
        except:
            print(f"  {fq_name}: ❌ 解析失败")
    print()


def test_minute_kline(stock_code="sh000001"):
    """测试 5: 分钟级 K 线（可能不支持）"""
    print("=" * 60)
    print(f"【测试 5】分钟级 K 线测试 - {stock_code}")
    print("=" * 60)
    minute_periods = ["m5", "m15", "m30", "m60"]
    for period in minute_periods:
        url = build_url(stock_code, period, "", "", 5, "qfq")
        resp = safe_request(url)
        if resp is None:
            print(f"  {period:>4}: ❌ 请求失败")
            continue
        try:
            result = resp.json()
            data_key, data = parse_kline_data(result, stock_code)
            if data_key and data:
                print(f"  {period:>4}: ✅ {len(data)} 条 (key={data_key})")
            else:
                print(f"  {period:>4}: ⚠️ 无数据 (该周期可能不支持)")
        except:
            print(f"  {period:>4}: ❌ 解析失败")
    print()


def test_multiple_stocks():
    """测试 6: 多股票批量测试"""
    print("=" * 60)
    print("【测试 6】多股票批量测试")
    print("=" * 60)
    stocks = [
        ("sh000001", "上证指数"),
        ("sz399001", "深证成指"),
        ("sh600519", "贵州茅台"),
        ("sz000001", "平安银行"),
        ("sh601398", "工商银行"),
    ]
    for code, name in stocks:
        url = build_url(code, "day", "", "", 3, "qfq")
        resp = safe_request(url)
        if resp is None:
            print(f"  {code} ({name}): ❌ 请求失败")
            continue
        try:
            result = resp.json()
            data_key, data = parse_kline_data(result, code)
            if data_key and data:
                latest = data[-1]
                # 修复：latest[0], latest[2]
                print(f"  {code} ({name}): ✅ 最新 {latest[0]} 收盘={latest[2]}")
            else:
                print(f"  {code} ({name}): ⚠️ 无数据")
        except:
            print(f"  {code} ({name}): ❌ 解析失败")
    print()


def test_raw_response():
    """测试 7: 查看原始返回（调试用）"""
    print("=" * 60)
    print("【测试 7】原始返回内容（调试用）")
    print("=" * 60)
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    url = build_url("sh000001", "day", start, end, 5, "qfq")
    resp = safe_request(url)
    if resp is None:
        print("❌ 请求失败，无法获取原始返回\n")
        return
    print(f"HTTP 状态码: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type')}")
    print(f"\n原始响应 (前 2000 字符):")
    print("-" * 40)
    print(resp.text[:2000])
    print("-" * 40)
    # 尝试格式化 JSON
    try:
        result = resp.json()
        print(f"\n格式化 JSON:")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
    except:
        print("\n⚠️ 响应不是有效 JSON")
    print()


# ========== 主程序 ==========
def main():
    print("\n" + "🔍" * 20)
    print("  腾讯 K 线接口诊断工具")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔍" * 20 + "\n")
    # 可选参数  # 修复：sys.argv[1]
    stock = sys.argv[1] if len(sys.argv) > 1 else "sh000001"
    # 按顺序执行测试
    ok = test_connectivity()
    if not ok:
        print("⚠️ 基础连通性测试失败，后续测试可能也会失败")
        print("  建议: 检查网络连接、换 IP（手机热点）、等待 30 分钟后重试\n")
    test_kline_data(stock, "day", 10)
    test_all_periods(stock)
    test_all_fq_types()
    test_minute_kline(stock)
    test_multiple_stocks()
    test_raw_response()
    print("=" * 60)
    print("【诊断完成】")
    print("=" * 60)
    print("""
如果所有测试都失败，可能原因:
  1. IP 被临时限流 → 换网络（手机热点）或等待 30 分钟
  2. 接口已下线 → 切换到 BaoStock / AkShare 等替代方案
  3. DNS 问题 → 尝试更换 DNS (114.114.114.114)

如果部分成功部分失败，可能原因:
  1. 某些股票无数据 → 换其他股票测试
  2. 分钟线不支持 → 这是已知限制，分钟线用另一个接口
""")


if __name__ == "__main__":
    main()