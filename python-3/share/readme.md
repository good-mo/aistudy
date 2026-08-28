# stock_monitor 盯盘程序

两种运行方式：

```bash
# 1. 原单文件（Docker 默认入口）
python stock_monitor.py

# 2. 模块化专业架构（推荐，结构说明见 stock_monitor/README.md）
python -m stock_monitor.main
```

Docker 构建运行：

```bash
docker build -t stock-monitor /workspace/share && docker run -it --rm stock-monitor
```
