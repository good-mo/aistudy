FROM python:3.12-slim

WORKDIR /app

# 设置时区为上海（UTC+8），确保 datetime.now() 返回正确时间
RUN apt-get update && \
    apt-get install -y tzdata && \
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
# pandas, numpy: 数据处理和技术指标计算
# requests: 腾讯财经 / 东方财富 API 请求
RUN pip install --no-cache-dir \
        pandas==2.2.3 \
        numpy==2.1.3 \
        requests==2.32.3

# 复制程序文件
COPY fund_screener.py .

# 设置字符集支持中文输出
ENV LANG=C.UTF-8
ENV LANGUAGE=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TZ=Asia/Shanghai

# 运行基金筛选程序
CMD ["python", "fund_screener.py"]
