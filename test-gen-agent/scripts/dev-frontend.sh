#!/usr/bin/env bash
#
# 本地调试 Frontend（MeterSphere Vue3 + Vite 前端 + FastAPI 后端）一键环境脚本
#
# 用法:
#   ./scripts/dev-frontend.sh            # 安装依赖并启动后端+前端
#   ./scripts/dev-frontend.sh setup      # 仅安装依赖（前后端）
#   ./scripts/dev-frontend.sh backend    # 仅启动 FastAPI 后端
#   ./scripts/dev-frontend.sh frontend   # 仅启动 Vite 前端 dev server
#   ./scripts/dev-frontend.sh check      # 仅检查本地环境
#
# 说明:
#   - 后端: FastAPI 默认监听 http://localhost:8000（VITE_DEV_DOMAIN 指向它）
#   - 前端: Vite dev server 将 /front、/api 等请求代理到后端
#   - 访问 http://localhost:5173 打开前端页面
#
# Node.js 自动安装:
#   - 脚本会读取 frontend/package.json 的 engines.node 字段来确定所需版本
#   - 若系统缺少 Node.js/npm，将自动通过官方 tarball 安装到 ~/.local
#   - 支持 x86_64 / arm64 两种架构

set -euo pipefail

# ---------- 配置 ----------
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
PYTHON="${PYTHON:-python3}"

# 默认 Node.js LTS 版本（前端 package.json engines.node 要求 >=18，这里用 20 LTS）
NODE_VERSION="${NODE_VERSION:-20.17.0}"

# ---------- 颜色输出 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[info]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC}   $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
err()   { echo -e "${RED}[err]${NC}  $*"; }

usage() {
  sed -n '1,22p' "$0" | grep -E '^# ' | sed 's/^# \{0,1\}//'
}

# ---------- 读取前端 engines.node 版本要求 ----------
get_required_node_version() {
  if [[ -f "${FRONTEND_DIR}/package.json" ]]; then
    # 使用 awk 提取 engines.node 字段（兼容换行格式）
    local node_req
    node_req="$(awk '/"engines"/,/\}/' "${FRONTEND_DIR}/package.json" | grep -o '"node"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"node"[[:space:]]*:[[:space:]]*"//; s/"$//' 2>/dev/null || true)"
    if [[ -n "$node_req" ]]; then
      echo "$node_req"
      return 0
    fi
  fi
  echo ">=18.0.0"
}

# ---------- 从版本要求提取最小主版本 ----------
get_min_major() {
  local req="$1"
  # 提取第一个数字块作为主版本号（如 ">=18.0.0" -> 18）
  local min_major
  min_major="$(echo "$req" | grep -oE '[0-9]+' | head -1)"
  if [[ -z "$min_major" ]]; then
    echo "20"
  else
    echo "$min_major"
  fi
}

# ---------- 检查 Node.js 是否满足版本要求 ----------
node_version_ok() {
  local required_major
  required_major="$(get_min_major "$(get_required_node_version)")"
  local current_major
  current_major="$(node -v 2>/dev/null | sed 's/^v//' | cut -d. -f1)"
  if [[ -z "$current_major" ]]; then
    return 1
  fi
  if (( current_major >= required_major )); then
    return 0
  else
    warn "Node.js ${current_major} < 要求的 ${required_major}，将安装 Node.js ${NODE_VERSION}"
    return 1
  fi
}

# ---------- 自动安装 Node.js ----------
install_node() {
  info "自动安装 Node.js ${NODE_VERSION}..."

  local arch
  arch="$(uname -m)"
  case "$arch" in
    x86_64|amd64) arch="x64" ;;
    aarch64|arm64) arch="arm64" ;;
    *)
      err "不支持的架构: ${arch}，请手动安装 Node.js"
      return 1
      ;;
  esac

  local os
  os="$(uname -s)"
  case "$os" in
    Linux) os="linux" ;;
    Darwin) os="darwin" ;;
    *)
      err "不支持的操作系统: ${os}，请手动安装 Node.js"
      return 1
      ;;
  esac

  local node_install_dir="${HOME}/.local/node-${NODE_VERSION}"
  local node_bin_dir="${node_install_dir}/bin"

  if [[ ! -x "${node_bin_dir}/node" ]]; then
    info "下载 Node.js ${NODE_VERSION} (${os}-${arch})..."
    local tarball="node-v${NODE_VERSION}-${os}-${arch}.tar.xz"
    local url="https://nodejs.org/dist/v${NODE_VERSION}/${tarball}"

    local tmp_dir
    tmp_dir="$(mktemp -d)"
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "${url}" -o "${tmp_dir}/${tarball}"
    elif command -v wget >/dev/null 2>&1; then
      wget -q "${url}" -O "${tmp_dir}/${tarball}"
    else
      err "未找到 curl 或 wget，无法下载 Node.js"
      rm -rf "${tmp_dir}"
      return 1
    fi

    mkdir -p "${node_install_dir}"
    tar -xJf "${tmp_dir}/${tarball}" -C "${node_install_dir}" --strip-components=1
    rm -rf "${tmp_dir}"
  fi

  # 将 Node.js 加入 PATH
  export PATH="${node_bin_dir}:${PATH}"
  if ! grep -q "${node_bin_dir}" "${HOME}/.bashrc" 2>/dev/null; then
    echo "export PATH=\"${node_bin_dir}:\$PATH\"" >> "${HOME}/.bashrc"
    info "已将 Node.js 路径添加到 ~/.bashrc"
  fi
  if ! grep -q "${node_bin_dir}" "${HOME}/.profile" 2>/dev/null; then
    echo "export PATH=\"${node_bin_dir}:\$PATH\"" >> "${HOME}/.profile"
    info "已将 Node.js 路径添加到 ~/.profile"
  fi

  if command -v node >/dev/null 2>&1; then
    ok "node: $(node -v)"
  else
    err "Node.js 安装失败，请手动安装"
    return 1
  fi
  if command -v npm >/dev/null 2>&1; then
    ok "npm: $(npm -v)"
  else
    warn "npm 未随 Node.js 安装，尝试单独安装..."
    # npm 包含在 Node.js 发行包中，通常不需要单独安装
  fi
}

# ---------- 确保 Node.js/npm 可用 ----------
ensure_node() {
  if command -v npm >/dev/null 2>&1; then
    local current_major
    current_major="$(node -v 2>/dev/null | sed 's/^v//' | cut -d. -f1)"
    local required_major
    required_major="$(get_min_major "$(get_required_node_version)")"
    if [[ -n "$current_major" ]] && (( current_major >= required_major )); then
      ok "Node.js/npm 已就绪 (node $(node -v), npm $(npm -v))"
      return 0
    fi
    warn "Node.js ${current_major} 不满足 engines.node 要求 (>=${required_major})，将重新安装..."
    install_node
    return $?
  fi

  if command -v node >/dev/null 2>&1; then
    warn "检测到 node 但缺少 npm，尝试重新安装 Node.js..."
  else
    err "未安装 npm，自动安装 Node.js..."
  fi
  install_node
}

# ---------- 检查前端依赖是否已安装 ----------
frontend_deps_ok() {
  [[ -d "${FRONTEND_DIR}/node_modules" ]]
}

# ---------- 检查后端依赖是否已安装 ----------
backend_deps_ok() {
  "${PYTHON}" -c "import fastapi, uvicorn" 2>/dev/null
}

# ---------- 环境检查 ----------
check_env() {
  info "检查本地环境..."
  local node_missing=0

  if command -v node >/dev/null 2>&1; then
    local node_v; node_v="$(node -v 2>/dev/null || echo '?')"
    ok "node: ${node_v}"
    local major; major="${node_v#v}"; major="${major%%.*}"
    local required_major
    required_major="$(get_min_major "$(get_required_node_version)")"
    if (( major < required_major )); then
      warn "node 版本 < ${required_major}，不满足 frontend/package.json engines 要求"
      node_missing=1
    fi
  else
    err "未安装 node，将自动安装 Node.js >= 18"; node_missing=1
  fi

  if command -v npm >/dev/null 2>&1; then
    ok "npm: $(npm -v)"
  else
    err "未安装 npm"; node_missing=1
  fi

  if command -v "${PYTHON}" >/dev/null 2>&1; then
    ok "${PYTHON}: $("${PYTHON}" --version 2>&1)"
  else
    err "未安装 ${PYTHON}，请先安装 Python 3"
  fi

  if frontend_deps_ok; then ok "frontend 依赖已安装"; else warn "frontend 依赖未安装（运行 setup）"; fi
  if backend_deps_ok;  then ok "backend 依赖已安装";  else warn "backend 依赖未安装（运行 setup）"; fi

  return "$node_missing"
}

# ---------- 安装依赖 ----------
setup() {
  # 1. 确保 Node.js/npm 可用（自动安装所需版本）
  ensure_node

  # 2. 后端依赖
  info "安装后端依赖..."
  if [[ -f "${ROOT_DIR}/requirements.txt" ]]; then
    "${PYTHON}" -m pip install -r "${ROOT_DIR}/requirements.txt"
  else
    warn "未找到 ${ROOT_DIR}/requirements.txt，跳过后端依赖"
  fi

  # 3. 前端依赖（官方工程存在 peer 冲突，需 --legacy-peer-deps）
  info "安装前端依赖（npm install --legacy-peer-deps）..."
  if command -v npm >/dev/null 2>&1; then
    (cd "${FRONTEND_DIR}" && npm install --legacy-peer-deps --no-audit --no-fund)
  else
    err "npm 安装失败，无法安装前端依赖"
    return 1
  fi

  ok "依赖安装完成"
}

# ---------- 启动后端 ----------
start_backend() {
  info "启动 FastAPI 后端 @ http://localhost:${BACKEND_PORT}"
  if ! backend_deps_ok; then
    err "后端依赖未安装，请先运行: ${BASH_SOURCE[0]} setup"
    return 1
  fi
  # 若缺少 .env，从模板复制
  if [[ ! -f "${ROOT_DIR}/.env" && -f "${ROOT_DIR}/.env.example" ]]; then
    cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
    warn "已生成 ${ROOT_DIR}/.env（模板），请编辑填入 OPENAI_API_KEY 后再启动"
  fi
  (cd "${ROOT_DIR}" && "${PYTHON}" -m uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT}" --reload)
}

# ---------- 启动前端 ----------
start_frontend() {
  info "启动 Vite dev server @ http://localhost:${FRONTEND_PORT}"
  if ! frontend_deps_ok; then
    err "frontend 依赖未安装，请先运行: ${BASH_SOURCE[0]} setup"
    return 1
  fi
  # 确保 .env.development 里 VITE_DEV_DOMAIN 指向后端
  (cd "${FRONTEND_DIR}" && npm run dev -- --host)
}

# ---------- 主流程 ----------
main() {
  local cmd="${1:-all}"

  case "$cmd" in
    all)
      check_env || true
      if ! frontend_deps_ok || ! backend_deps_ok; then
        info "检测到依赖未完整安装，先执行 setup..."
        setup
      fi
      info "同时启动后端与前端（Ctrl+C 结束）..."
      start_backend &
      local bg_pid=$!
      trap 'kill "$bg_pid" 2>/dev/null || true' EXIT
      start_frontend
      wait "$bg_pid"
      ;;
    setup)  setup ;;
    backend) start_backend ;;
    frontend) start_frontend ;;
    check)  check_env || exit 1 ;;
    help|-h|--help) usage ;;
    *)
      err "未知命令: $cmd"
      usage
      exit 1
      ;;
  esac
}

main "$@"
