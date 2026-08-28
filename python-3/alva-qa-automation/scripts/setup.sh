#!/usr/bin/env bash
#
# scripts/setup.sh — 环境安装脚本
#
# 负责安装 Node 依赖与 Playwright 浏览器，并校验 Node 版本。
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[setup.sh]${NC} $*"; }
warn() { echo -e "${YELLOW}[setup.sh]${NC} $*"; }
err()  { echo -e "${RED}[setup.sh]${NC} $*" >&2; }

# 1. 校验 Node 版本
check_node() {
  log "校验 Node.js 版本..."
  if ! command -v node >/dev/null 2>&1; then
    err "未检测到 Node.js，请先安装 Node.js >= 18"
    exit 1
  fi
  local node_major
  node_major="$(node -v | sed 's/v\([0-9]*\).*/\1/')"
  if [[ "$node_major" -lt 18 ]]; then
    err "Node.js 版本过低（当前 $(node -v)），需 >= 18"
    exit 1
  fi
  log "Node.js 版本: $(node -v) ✓"
}

# 2. 安装 npm 依赖
install_deps() {
  log "安装 npm 依赖..."
  if [[ ! -d node_modules ]]; then
    npm install --no-audit --no-fund
  else
    npm install --no-audit --no-fund || warn "npm install 失败，尝试继续"
  fi
  log "npm 依赖安装完成 ✓"
}

# 3. 安装 Playwright 浏览器
install_browsers() {
  log "安装 Playwright Chromium 浏览器..."
  npx playwright install chromium --with-deps
  log "Playwright 浏览器安装完成 ✓"
}

# 4. 初始化报告目录
init_reports() {
  log "初始化报告目录..."
  mkdir -p reports/html reports/json reports/screenshots reports/logs
  touch reports/html/.gitkeep reports/json/.gitkeep reports/screenshots/.gitkeep reports/logs/.gitkeep
}

main() {
  log "=== 开始环境安装 ==="
  check_node
  install_deps
  install_browsers
  init_reports
  log "=== 环境安装完成 ==="
}

main "$@"
