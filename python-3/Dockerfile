FROM python:3.12

RUN sed -i 's@deb.debian.org@mirrors.cloud.tencent.com@g' /etc/apt/sources.list.d/debian.sources

# Install additional development tools and dependencies
RUN apt-get update && \
    apt-get install -y \
            build-essential \
            cmake clang llvm-dev libclang-dev \
            git curl \
            wget unzip lsof nload htop net-tools dnsutils openssh-server vim && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install PyPI Artifact build and push tools
RUN pip install build \
    && pip install twine \
    && pip install poetry

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

# Install Python development VS Code extensions for code-server
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
    && code-server --install-extension cnbcool.cnb-welcome

# 指定字符集支持命令行输入中文（根据需要选择字符集）
ENV LANG C.UTF-8
ENV LANGUAGE C.UTF-8

# ---- 项目目录与依赖自动安装 ----
WORKDIR /workspace

# 复制依赖清单并自动安装（利用 Docker 层缓存，仅清单变化时重新安装）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt || \
    pip install --no-cache-dir -i https://mirrors.cloud.tencent.com/pypi/simple/ -r requirements.txt

# 复制项目源码
COPY . .

# 统一入口（可执行）
ENTRYPOINT ["python3", "run.py"]
