import time
import random
from urllib.parse import urlencode
import requests  # 导入 requests 模块
def get_hs300_stocks() -> List[str]:
    """
    从东方财富网获取沪深300指数的成分股代码，增加重试和随机等待
    """
    url = "http://17.push2.eastmoney.com/api/qt/clist/get"
    params = {
        'fid': 'f3',
        'po': '1',
        'pz': '500',
        'pn': '1',
        'np': '1',
        'fltt': '2',
        'invt': '2',
        'wb': 'bfq',
        'fs': 'm:0+t:3,m:0+t:2,m:0+t:1,m:1+t:2,m:1+t:1,m:1+t:3,m:1+t:4,m:1+t:5,m:1+t:6,m:1+t:7,m:1+t:8',
        'stat': '1',
        'st': '2'
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/"
    }
    
    max_retries = 5
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries + 1):
        try:
            # 构建完整的URL
            full_url = f"{url}?{urlencode(params)}"
            
            # 发送请求，随机添加一点延迟
            time.sleep(random.uniform(0.5, 1.5))
            
            response = requests.get(full_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data['code'] == 0:
                stocks = data['data']['diff']
                codes = [stock['fc'] for stock in stocks]
                return codes
            else:
                print(f"Request failed with code {data['code']}: {data.get('msg', '')}")
                
        except requests.exceptions.RequestException as e:
            if attempt == max_retries:
                print(f"Max retries exceeded. Failed to fetch HS300 stocks: {e}")
                return []
            else:
                wait_time = min(retry_delay * (2 ** attempt), 60)
                print(f"Attempt {attempt + 1} failed. Retrying in {wait_time:.0f} seconds...")
                time.sleep(wait_time)
                
    return []
def main():
    # 尝试多次获取沪深300股票代码
    for _ in range(3):
        hs300_codes = get_hs300_stocks()
        if hs300_codes:
            break
        time.sleep(10)  # 等待一段时间后再次尝试
    
    if not hs300_codes:
        print("Failed to retrieve HS300 stock codes after multiple attempts. Exiting.")
        return
    # 初始化数据抓取器
    fetcher = FinancialDataFetcher()
    
    # 获取财务数据（智能缓存）
    financial_data = fetcher.get_financial_data(hs300_codes)
    
    # 或者强制更新缓存
    # financial_data = fetcher.force_update(hs300_codes)
    
    # 打印结果（截断展示）
    for code, data in list(financial_data.items())[:5]:  # 展示前5条数据
        print(f"{code}: {data}")
if __name__ == "__main__":
    main()