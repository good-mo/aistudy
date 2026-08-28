#!/usr/bin/env bash
#
# scripts/validate-data.sh — 金融数据校验脚本
#
# 负责校验 test-data 目录中的金融数据（tickers / expected-values）格式与
# 合理性，确保测试数据在进入测试前是合法、完整的。
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[validate-data.sh]${NC} $*"; }
warn() { echo -e "${YELLOW}[validate-data.sh]${NC} $*"; }
err()  { echo -e "${RED}[validate-data.sh]${NC} $*" >&2; }

TICKERS_FILE="test-data/tickers.json"
EXPECTED_FILE="test-data/expected-values.json"

# 1. 文件存在性检查
check_files() {
  local ok=1
  [[ -f "$TICKERS_FILE" ]] || { err "缺少 $TICKERS_FILE"; ok=0; }
  [[ -f "$EXPECTED_FILE" ]] || { err "缺少 $EXPECTED_FILE"; ok=0; }
  [[ "$ok" -eq 1 ]] || exit 1
  log "测试数据文件存在 ✓"
}

# 2. 校验 tickers.json
validate_tickers() {
  log "校验 $TICKERS_FILE ..."
  node -e "
    const t = require('./$TICKERS_FILE');
    if (!Array.isArray(t.tickers)) throw new Error('tickers 必须是数组');
    if (t.tickers.length === 0) throw new Error('tickers 数组为空');
    const seen = new Set();
    for (const tk of t.tickers) {
      if (!/^[A-Z0-9.^\-]{1,15}$/.test(tk.symbol || '')) throw new Error('非法 ticker symbol: ' + tk.symbol);
      if (seen.has(tk.symbol)) throw new Error('重复 symbol: ' + tk.symbol);
      seen.add(tk.symbol);
      if (typeof tk.name !== 'string' || !tk.name) throw new Error('缺少名称: ' + tk.symbol);
    }
    console.log('  校验通过: ' + t.tickers.length + ' 个 ticker ✓');
  " || { err "tickers.json 校验失败"; exit 1; }
}

# 3. 校验 expected-values.json
validate_expected() {
  log "校验 $EXPECTED_FILE ..."
  node -e "
    const e = require('./$EXPECTED_FILE');
    if (!Array.isArray(e.assets)) throw new Error('assets 必须是数组');
    if (e.assets.length === 0) throw new Error('assets 数组为空');
    for (const a of e.assets) {
      if (!a.symbol) throw new Error('缺少 symbol');
      if (typeof a.tolerance !== 'number' || a.tolerance < 0 || a.tolerance > 1) {
        throw new Error('非法 tolerance（应介于 0~1）: ' + a.symbol);
      }
      for (const field of ['price', 'volume', 'marketCap', 'peRatio']) {
        if (field in a && a[field] !== null && typeof a[field] !== 'number') {
          throw new Error('字段 ' + field + ' 必须为数字（或 null）: ' + a.symbol);
        }
      }
    }
    console.log('  校验通过: ' + e.assets.length + ' 个资产 ✓');
  " || { err "expected-values.json 校验失败"; exit 1; }
}

main() {
  log "=== 开始金融数据校验 ==="
  check_files
  validate_tickers
  validate_expected
  log "=== 金融数据校验通过 ==="
}

main "$@"
