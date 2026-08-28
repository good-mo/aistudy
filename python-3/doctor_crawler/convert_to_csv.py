#!/usr/bin/env python3
"""将 doctor_scrapy.json 中的综合诊断数据转换为 CSV 并按综合评分降序排列。

用法：
    python3 convert_to_csv.py                 # 使用默认路径
    python3 convert_to_csv.py <json路径> <csv路径>
"""
import json
import csv
import sys

def get_dim_score(item, dim_name):
    """从 dimensions 列表中提取指定维度的评分"""
    for dim in item.get('dimensions', []):
        if dim.get('name') == dim_name:
            return dim.get('score', '')
    return ''

def main():
    # 默认路径
    json_path = 'data/doctor_scrapy.json'
    csv_path = 'data/doctor_scrapy.csv'
    
    if len(sys.argv) >= 2:
        json_path = sys.argv[1]
    if len(sys.argv) >= 3:
        csv_path = sys.argv[2]
    
    # 读取 JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 按综合评分降序排列（无评分的排最后）
    def get_score(item):
        try:
            return float(item.get('diagnosis_score', 0))
        except (ValueError, TypeError):
            return 0
    
    data.sort(key=get_score, reverse=True)
    
    # CSV 列定义
    columns = [
        '股票代码', '股票名称', '综合诊断评分', '打败百分比(%)', '投资评级',
        '短期趋势', '中期趋势', '长期趋势',
        '技术面评分', '资金面评分', '消息面评分', '行业面评分', '基本面评分'
    ]
    
    rows = []
    for item in data:
        stock_name = item.get('hs300_name', item.get('stock_name', ''))
        # 清理股票名称格式（如 "平安银行（000001）" -> "平安银行"）
        if isinstance(stock_name, str):
            stock_name = stock_name.split('（')[0].split('(')[0].strip()
        
        row = {
            '股票代码': item.get('stock_code', ''),
            '股票名称': stock_name,
            '综合诊断评分': item.get('diagnosis_score', ''),
            '打败百分比(%)': item.get('beat_percent', ''),
            '投资评级': item.get('rating', ''),
            '短期趋势': item.get('short_term', ''),
            '中期趋势': item.get('mid_term', ''),
            '长期趋势': item.get('long_term', ''),
            '技术面评分': get_dim_score(item, '技术面'),
            '资金面评分': get_dim_score(item, '资金面'),
            '消息面评分': get_dim_score(item, '消息面'),
            '行业面评分': get_dim_score(item, '行业面'),
            '基本面评分': get_dim_score(item, '基本面'),
        }
        rows.append(row)
    
    # 写入 CSV（UTF-8 with BOM，Excel 兼容）
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✅ CSV 已生成: {csv_path} ({len(rows)} 行)")
    print(f"   排序方式: 综合诊断评分降序")

if __name__ == '__main__':
    main()
