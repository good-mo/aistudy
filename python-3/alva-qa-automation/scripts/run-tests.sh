#!/usr/bin/env bash
#
# scripts/run-tests.sh — 测试执行脚本
#
# 负责调用 Playwright 执行端到端测试，支持按文件 / 按标签筛选。
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[run-tests.sh]${NC} $*"; }
err() { echo -e "${RED}[run-tests.sh]${NC} $*" >&2; }

# 确保环境已就绪
if [[ ! -d node_modules ]]; then
  log "检测到依赖未安装，先执行安装..."
  bash scripts/setup.sh
fi

# 确保报告目录存在
mkdir -p reports/html reports/json reports/screenshots reports/logs

# 收集参数：支持 -f <文件> / -g <grep 标签> 筛选
FILE_FILTER=""
GREP_FILTER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--file)
      FILE_FILTER="$2"
      shift 2
      ;;
    -g|--grep)
      GREP_FILTER="$2"
      shift 2
      ;;
    *)
      err "未知参数: $1"
      err "用法: bash scripts/run-tests.sh [-f <测试文件>] [-g <grep标签>]"
      exit 1
      ;;
  esac
done

CMD=(npx playwright test)

if [[ -n "$FILE_FILTER" ]]; then
  CMD+=("tests/$FILE_FILTER")
  log "按文件筛选执行: tests/$FILE_FILTER"
fi

if [[ -n "$GREP_FILTER" ]]; then
  CMD+=(--grep "$GREP_FILTER")
  log "按标签筛选执行: $GREP_FILTER"
fi

log "开始执行测试..."
"${CMD[@]}"

log "测试执行完成，报告输出至 reports/html/"
