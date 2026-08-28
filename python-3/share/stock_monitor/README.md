# stock_monitor 模块化架构

将原本的单文件 `stock_monitor.py`（1806 行）重构为清晰的分层模块化架构。

> ⚠️ 兼容性：原 `stock_monitor.py` 文件**完整保留**，作为独立运行的脚本入口
> （`share/Dockerfile` 仍指向它），两者互不影响。

## 架构总览

```
share/
├── stock_monitor.py          # 原单文件（保留，独立运行入口）
└── stock_monitor/            # 模块化包（专业架构）
    ├── __init__.py           # 包入口，导出 StockMonitor / MonitorConfig
    ├── main.py               # 命令行入口（python -m stock_monitor.main）
    ├── config.py             # 配置：监控列表 / 预警设置 / 信号参数
    ├── constants.py          # 常量：API 地址、代码映射、默认阈值
    ├── api.py                # 腾讯财经数据客户端（实时行情 + 日K线）
    ├── indicators.py         # 纯函数技术指标（EMA/SMA/MACD/KDJ/RSI/布林）
    ├── notifier.py           # 桌面通知
    ├── display.py            # 终端展示与格式化
    ├── monitor.py            # 主监控器（编排数据/信号/展示/循环）
    └── signals/              # 多因子信号子系统
        ├── __init__.py
        ├── factors.py        # 因子实现（MA/MACD/KDJ/RSI/布林/量能）
        └── engine.py         # 综合评分引擎（共振/衰减/大盘加成）
```

## 模块职责

| 模块 | 职责 |
|------|------|
| `config` | 数据类集中管理监控列表、预警阈值、买卖信号参数、刷新间隔、冷却期 |
| `constants` | 腾讯 API 地址、HTTP 头、股票代码→腾讯代码映射 |
| `api` | 封装行情/K 线 HTTP 请求、解析与重试，返回 `DataFrame` / `list` |
| `indicators` | 无状态技术指标计算；`KdjState` 提供 KDJ 递归状态 |
| `signals/factors` | 每个因子一个类，实现统一 `evaluate(row, ctx) -> FactorResult` 接口 |
| `signals/engine` | 汇总各因子、共振加成、时间衰减、大盘加成、输出信号等级 |
| `notifier` | 桌面通知（plyer，可选） |
| `display` | 表格渲染、信号/预警打印、数字格式化 |
| `monitor` | `StockMonitor` 主类，编排完整盯盘流程 |

## 运行方式

```bash
# 方式一：使用模块化架构（推荐）
cd share && python -m stock_monitor.main

# 方式二：使用原单文件（兼容 Docker）
cd share && python stock_monitor.py
```

## 设计要点

1. **依赖注入**：`StockMonitor(config, client)` 可注入自定义配置与数据客户端，便于测试。
2. **单一职责**：每个因子独立类，互不耦合，新增因子只需实现 `evaluate` 并加入
   `SignalEngine.FACTOR_CLASSES`。
3. **纯函数指标**：`indicators` 模块无状态，便于单元测试；KDJ 通过 `KdjState`
   显式管理递归前值。
4. **上下文对象**：`IndicatorContext` 屏蔽底层存储结构，因子只通过 `prices/highs/lows`
   等接口访问数据。
