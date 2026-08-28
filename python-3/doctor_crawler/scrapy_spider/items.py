import scrapy


class DoctorItem(scrapy.Item):
    """同花顺诊股页面数据项"""
    url = scrapy.Field()          # 页面 URL
    title = scrapy.Field()        # 页面标题
    text = scrapy.Field()         # 页面全部可见文本
    sections = scrapy.Field()     # 分区块内容列表
    links = scrapy.Field()        # 页面内所有链接
    crawled_at = scrapy.Field()   # 抓取时间

    # 股票标识
    stock_code = scrapy.Field()   # 股票代码，如：600000
    hs300_name = scrapy.Field()   # 沪深300成分股名称（来自成分股列表）

    # 综合诊断数据
    stock_name = scrapy.Field()   # 股票名称和代码，如：招商证券（600999）
    diagnosis_score = scrapy.Field()    # 综合诊断评分，如：6.7
    diagnosis_text = scrapy.Field()     # 综合诊断描述，如：综合诊断：6.7分 打败了99%的股票！
    beat_percent = scrapy.Field()       # 打败的股票百分比，如：99

    # 投资评级（卖出/减持/中性/增持/买入）
    rating = scrapy.Field()       # 当前评级，如：增持
    ratings = scrapy.Field()      # 全部评级列表 [{name: 卖出, active: false}, ...]

    # 短期/中期/长期趋势
    short_term = scrapy.Field()   # 短期趋势描述
    mid_term = scrapy.Field()     # 中期趋势描述
    long_term = scrapy.Field()    # 长期趋势描述

    # 各维度评分
    dimensions = scrapy.Field()   # 维度评分列表 [{name: 技术面, score: 6.6, beat: 81}, ...]
