#!/usr/bin/env bash
#
# run.sh — Alva QA 自动化测试框架主运行脚本
#
# 负责：环境安装 → 测试执行 → 报告生成 的全流程编排
# 用法：
#   ./run.sh             # 全流程（安装 + 执行 + 报告）
#   ./run.sh setup       # 仅安装环境
#   ./run.sh test        # 仅执行测试
#   ./run.sh report      # 仅生成报告
#   ./run.sh validate    # 仅校验金融数据
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[run.sh]${NC} $*"; }
warn() { echo -e "${YELLOW}[run.sh]${NC} $*"; }
err()  { echo -e "${RED}[run.sh]${NC} $*" >&2; }

run_setup() {
  log ">>> 第 1/4 步：安装测试环境依赖"
  bash scripts/setup.sh
}

run_validate() {
  log ">>> 第 2/4 步：校验金融数据"
  bash scripts/validate-data.sh
}

run_tests() {
  log ">>> 第 3/4 步：执行端到端测试"
  bash scripts/run-tests.sh
}

run_report() {
  log ">>> 第 4/4 步：生成测试报告"
  bash scripts/generate-report.sh
}

show_summary() {
  local json_file="reports/json/results.json"
  if [[ -f "$json_file" ]]; then
    echo ""
    log "==================== 测试结果汇总 ===================="
    node -e "
      const r = require('$json_file');
      const suites = r.suites || [];
      const stats = r.stats || {};
      console.log('  通过用例 :', stats.expected || 0);
      console.log('  失败用例 :', stats.unexpected || 0);
      console.log('  跳过用例 :', stats.skipped || 0);
      console.log('  执行耗时 :', ((stats.duration || 0)/1000).toFixed(2) + 's');
    " 2>/dev/null || warn "无法解析报告 JSON，请检查报告生成是否成功。"
    log "======================================================"
  fi
}

main() {
  local mode="${1:-all}"

  case "$mode" in
    setup)     run_setup ;;
    validate)  run_validate ;;
    test)      run_tests ;;
    report)    run_report ;;
    all)
      run_setup
      run_validate
      run_tests
      run_report
      show_summary
      ;;
    *)
      err "未知参数: $mode"
      err "用法: ./run.sh [setup|validate|test|report|all]"
      exit 1
      ;;
  esac

  log ">>> 完成！报告入口: reports/html/index.html"
}

main "$@"
