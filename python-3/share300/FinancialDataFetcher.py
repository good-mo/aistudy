import os
import time
from datetime import datetime
from typing import Dict, List, Optional
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
class FinancialDataFetcher:
    """东方财富财务数据获取器（并发获取 + CSV持久化）"""
    CACHE_FILE = "hs300_financial_data.csv"
    CACHE_EXPIRE_DAYS = 7
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://data.eastmoney.com/",
        })
        self._lock = threading.Lock()
    # ==================== 对外接口 ====================
    def get_financial_data(self, codes: List[str]) -> Dict[str, Dict]:
        """
        获取财务数据（智能缓存）
        1. 检查本地CSV缓存是否有效
        2. 有效则直接读取，无效则并发获取并缓存
        """
        if not codes:
            return {}
        cache = self._load_cache(codes)
        if cache is not None:
            return cache
        print(f"📊 正在从东方财富API并发获取 {len(codes)} 只股票的最新财报...")
        results = self._fetch_all_concurrent(codes)
        if results:
            self._save_cache(results)
            print(f"💾 已保存到 {os.path.abspath(self.CACHE_FILE)}")
        print(f"✅ 财务数据获取完成，成功 {len(results)} 只\n")
        return results
    def force_update(self, codes: List[str]) -> Dict[str, Dict]:
        """强制更新缓存（删除旧文件后重新获取）"""
        print("🔄 强制更新财务数据...")
        if os.path.exists(self.CACHE_FILE):
            os.remove(self.CACHE_FILE)
        return self.get_financial_data(codes)
    # ==================== CSV缓存读写 ====================
    def _load_cache(self, codes: List[str]) -> Optional[Dict[str, Dict]]:
        """检查并读取本地CSV缓存"""
        if not os.path.exists(self.CACHE_FILE):
            return None
        try:
            df = pd.read_csv(self.CACHE_FILE, encoding='utf-8-sig')
            # 检查数据是否有效
            if df.empty or 'update_date' not in df.columns:
                return None
            # 检查更新日期是否过期
            update_date_str = df['update_date'].iloc[0]
            update_date = datetime.strptime(update_date_str, '%Y-%m-%d')
            today = datetime.today()
            days_since_update = (today - update_date).days
            if days_since_update > self.CACHE_EXPIRE_DAYS:
                print(f"📄 财务缓存已过期（{days_since_update}天），重新获取...")
                return None
            # 检查必要列是否存在
            required_columns = ['code', 'report_date', 'security_name', 'roe', 'profit_growth',
                               'debt_ratio', 'eps', 'bvps', 'net_profit', 'revenue']
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                print(f"📄 缓存数据缺少必要列：{missing_cols}，重新获取...")
                return None
            # 检查数据覆盖度
            df_codes = set(df['code'].astype(str).tolist())
            missing = [c for c in codes if c not in df_codes]
            if len(missing) > len(codes) * 0.2:  # 缺失超过20%
                print(f"📄 缓存数据不完整（缺失 {len(missing)} 只），更新...")
                return None
            df = df.replace('', pd.NA)
            results = {}
            for _, row in df.iterrows():
                code = str(row['code'])
                if code not in codes:
                    continue
                results[code] = {
                    'report_date': str(row['report_date']) if pd.notna(row.get('report_date')) else None,
                    'security_name': str(row['security_name']) if pd.notna(row.get('security_name')) else None,
                    'roe': self._safe_float(row.get('roe')),
                    'profit_growth': self._safe_float(row.get('profit_growth')),
                    'debt_ratio': self._safe_float(row.get('debt_ratio')),
                    'eps': self._safe_float(row.get('eps')),
                    'bvps': self._safe_float(row.get('bvps')),
                    'net_profit': self._safe_float(row.get('net_profit')),
                    'revenue': self._safe_float(row.get('revenue')),
                }
            report_date = df['report_date'].iloc[0] if 'report_date' in df.columns else 'unknown'
            print(f"📄 从本地缓存加载财务数据：{len(results)} 只（报告期: {report_date}）")
            return results
        except Exception as e:
            print(f"⚠️ 读取缓存失败: {e}")
            return None
    def _save_cache(self, results: Dict[str, Dict]):
        """保存为CSV（保持沪深300最新一期财报数据）"""
        try:
            records = []
            for code, data in results.items():
                records.append({
                    'code': code,
                    'report_date': data.get('report_date'),
                    'security_name': data.get('security_name'),
                    'roe': data.get('roe'),
                    'profit_growth': data.get('profit_growth'),
                    'debt_ratio': data.get('debt_ratio'),
                    'eps': data.get('eps'),
                    'bvps': data.get('bvps'),
                    'net_profit': data.get('net_profit'),
                    'revenue': data.get('revenue'),
                    'update_date': datetime.now().strftime('%Y-%m-%d'),
                })
            df = pd.DataFrame(records)
            # 固定列顺序
            df = df[['code', 'report_date', 'security_name', 'roe', 'profit_growth',
                     'debt_ratio', 'eps', 'bvps', 'net_profit', 'revenue', 'update_date']]
            df = df.sort_values('code')
            df.to_csv(self.CACHE_FILE, index=False, encoding='utf-8-sig', na_rep='')
        except Exception as e:
            print(f"⚠️ 保存缓存失败: {e}")
    # ==================== 并发请求 ====================
    def _fetch_all_concurrent(self, codes: List[str]) -> Dict[str, Dict]:
        """并发获取全部财务数据（5线程）"""
        results = {}
        total = len(codes)
        completed = 0
        def fetch_with_progress(code: str) -> Optional[tuple]:
            nonlocal completed
            data = self._fetch_single(code)
            with self._lock:
                nonlocal completed
                completed += 1
                if completed % 30 == 0 or completed == total:
                    print(f"  进度: {completed}/{total}")
            time.sleep(0.2)  # 限速，避免触发反爬
            return (code, data) if data else None
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_code = {executor.submit(fetch_with_progress, code): code for code in codes}
            for future in as_completed(future_to_code):
                result = future.result()
                if result:
                    code, data = result
                    results[code] = data
        return results
    def _fetch_single(self, code: str) -> Optional[Dict]:
        """单只股票财务数据（取最近2期计算增速）"""
        url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        params = {
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
            "pageSize": "2",
            "pageNumber": "1",
            "reportName": "RPT_FCI_PERFORMANCEE",
            "columns": "ALL",
            "source": "WEB",
            "client": "WEB",
            "filter": f'(SECURITY_CODE="{code}")',
        }
        try:
            resp = self._session.get(url, params=params, timeout=10)
            data = resp.json()
            if not data.get("result") or not data["result"].get("data"):
                return None
            items = data["result"]["data"]
            if not items:
                return None
            latest = items[0]
            # 计算净利润同比增速
            profit_growth = None
            if len(items) >= 2:
                curr_profit = items[0].get("PARENT_NETPROFIT_SQ")
                prev_profit = items[1].get("PARENT_NETPROFIT_SQ")
                if curr_profit is not None and prev_profit is not None and prev_profit != 0:
                    profit_growth = ((curr_profit - prev_profit) / prev_profit) * 100
            # 负债率字段兼容
            debt_ratio = latest.get("DEBT_ASSET_RATIO") or latest.get("DEBT_RATIO")
            return {
                'report_date': latest.get("REPORT_DATE"),
                'security_name': latest.get("SECURITY_NAME_ABBR"),
                'roe': self._to_float(latest.get("WEIGHTAVG_ROE")),
                'profit_growth': profit_growth,
                'debt_ratio': self._to_float(debt_ratio),
                'eps': self._to_float(latest.get("BASIC_EPS")),
                'bvps': self._to_float(latest.get("PARENT_BVPS")),
                'net_profit': self._to_float(latest.get("PARENT_NETPROFIT_SQ")),
                'revenue': self._to_float(latest.get("TOTAL_OPERATE_INCOME_SQ")),
            }
        except Exception:
            return None
    # ==================== 工具方法 ====================
    @staticmethod
    def _to_float(val):
        try:
            if val is None or str(val) in ("", "-", "--", "None"):
                return None
            return float(val)
        except (ValueError, TypeError):
            return None
    @staticmethod
    def _safe_float(val):
        if pd.isna(val):
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None