#!/usr/bin/env bash
#
# scripts/generate-report.sh — 报告生成脚本
#
# 负责汇总 Playwright 测试结果，生成 HTML / JSON / 文本摘要报告。
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[generate-report.sh]${NC} $*"; }
warn() { echo -e "${YELLOW}[generate-report.sh]${NC} $*"; }
err()  { echo -e "${RED}[generate-report.sh]${NC} $*" >&2; }

JSON_FILE="reports/json/results.json"

# 1. 校验结果文件存在
if [[ ! -f "$JSON_FILE" ]]; then
  err "未找到测试结果文件: $JSON_FILE，请先执行测试。"
  exit 1
fi

# 2. 生成文本摘要
log "生成测试摘要..."
node -e "
const fs = require('fs');
const r = JSON.parse(fs.readFileSync('$JSON_FILE', 'utf8'));
const stats = r.stats || {};
const lines = [
  '==========================================',
  '        Alva QA 自动化测试报告',
  '==========================================',
  '总用例数   : ' + (stats.expected + stats.unexpected || 0),
  '通过       : ' + (stats.expected || 0),
  '失败       : ' + (stats.unexpected || 0),
  '跳过       : ' + (stats.skipped || 0),
  '耗时       : ' + ((stats.duration || 0)/1000).toFixed(2) + 's',
  '==========================================',
  ''
];
console.log(lines.join('\n'));

// 输出失败用例明细
const suites = r.suites || [];
const failures = [];
(function walk(s){
  (s.suites || []).forEach(walk);
  (s.specs || []).forEach(sp => {
    (sp.tests || []).forEach(t => {
      t.results.forEach(res => {
        if (res.status === 'failed' || res.status === 'timedOut') {
          failures.push(sp.title);
        }
      });
    });
  });
})({ suites });
if (failures.length) {
  console.log('失败用例明细:');
  failures.forEach(f => console.log('  - ' + f));
}
" > reports/summary.txt 2>&1 || warn "摘要生成失败，查看详细报告"

cat reports/summary.txt

# 3. 提示 HTML 报告入口
log "HTML 报告: reports/html/index.html"
log "JSON 报告: reports/json/results.json"
log "文本摘要:  reports/summary.txt"

exit 0
