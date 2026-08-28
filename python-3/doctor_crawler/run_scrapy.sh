#!/usr/bin/env bash
# Scrapy 爬虫运行脚本
# 用法：
#   ./run_scrapy.sh                # 爬取全部沪深300 成分股综合诊断
#   ./run_scrapy.sh 600999         # 爬取单只股票（如招商证券）
set -e
cd "$(dirname "$0")"

mkdir -p data

CODE="${1:-all}"
OUTPUT="data/doctor_scrapy.json"

if [ "$CODE" = "all" ] || [ "$CODE" = "hs300" ] || [ "$CODE" = "300" ]; then
    echo "[INFO] 开始批量爬取沪深300全部成分股综合诊断..."
    scrapy crawl doctor -o "${OUTPUT}"
else
    echo "[INFO] 爬取单只股票 ${CODE}..."
    scrapy crawl doctor -a "code=${CODE}" -o "${OUTPUT}"
fi

echo "[OK] 数据已保存到 ${OUTPUT}"
