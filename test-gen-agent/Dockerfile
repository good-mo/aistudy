# ════════════════════════════════════════════════════════════
# Stage 1: 构建 MeterSphere 前端
# ════════════════════════════════════════════════════════════
FROM node:20-bullseye AS frontend-builder

WORKDIR /build

# 复制前端工程与依赖清单
COPY frontend/package.json frontend/package-lock.json* ./

# 安装依赖（MeterSphere 官方工程存在 peer 冲突，需 --legacy-peer-deps）
RUN npm install --legacy-peer-deps --no-audit --no-fund

# 复制前端源码并构建
COPY frontend/ ./
RUN npx vite build --config ./config/vite.config.prod.ts

# ════════════════════════════════════════════════════════════
# Stage 2: 运行时（Python 后端 + 前端产物）
# ════════════════════════════════════════════════════════════
FROM python:3.12

RUN sed -i 's@deb.debian.org@mirrors.cloud.tencent.com@g' /etc/apt/sources.list.d/debian.sources

# 安装基础工具（含 Node.js 20 LTS 与 npm，用于前端开发调试）
RUN apt-get update && \
    apt-get install -y \
            build-essential \
            cmake clang llvm-dev libclang-dev \
            git curl \
            wget unzip lsof nload htop net-tools dnsutils openssh-server vim \
            nodejs npm && \
    # 若 apt 默认 Node 版本过旧（<18），通过 Nodesource 安装 Node.js 20
    if ! node -v 2>/dev/null | grep -qE '^v(18|20|22|24)'; then \
      curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
      apt-get install -y nodejs; \
    fi && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装 PyPI 构建工具
RUN pip install build \
    && pip install "fastapi[standard]" \
    && pip install uv \
    && pip install LangGraph

# 安装 Python VS Code 扩展（开发环境）
RUN curl -fsSL https://code-server.dev/install.sh | sh \
    && code-server --install-extension ms-python.python \
    && code-server --install-extension ms-python.flake8 \
    && code-server --install-extension ms-python.black-formatter \
    && code-server --install-extension ms-python.mypy-type-checker \
    && code-server --install-extension ms-python.pylint \
    && code-server --install-extension formulahendry.code-runner \
    && code-server --install-extension ms-toolsai.jupyter \
    && code-server --install-extension ms-python.debugpy \
    && code-server --install-extension tencent-cloud.coding-copilot \
    && code-server --install-extension MS-CEINTL.vscode-language-pack-zh-hans \
    && code-server --install-extension batisteo.vscode-django

# 指定字符集支持命令行输入中文
ENV LANG=C.UTF-8
ENV LANGUAGE=C.UTF-8

# 复制应用代码与依赖清单
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/
COPY requirements.txt ./
COPY scripts/ ./scripts/

# 复制前端构建产物（MeterSphere 前端，供 /ms/ 前缀服务）
COPY --from=frontend-builder /build/dist ./frontend/dist/

# 安装运行时依赖
RUN pip install -r requirements.txt

# 应用监听端口
EXPOSE 8000

# 启动入口
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
