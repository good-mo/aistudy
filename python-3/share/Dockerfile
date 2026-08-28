FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（plyer 桌面通知需要的 dbus 相关库）
RUN apt-get update && \
    apt-get install -y \
        libdbus-1-3 \
        libglib2.0-0 \
        tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
RUN pip install --no-cache-dir \
        pandas \
        plyer \
        requests

# 复制程序文件
COPY stock_monitor.py .

# 设置字符集支持中文输出
ENV LANG=C.UTF-8
ENV LANGUAGE=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TZ=Asia/Shanghai

# 启动盯盘程序
CMD ["python", "stock_monitor.py"]
