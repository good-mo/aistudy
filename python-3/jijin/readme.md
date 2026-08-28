
docker build -t jijin-screening . && docker run --rm jijin-screening

# 普通运行（自动使用缓存）
python fund_screener.py

# 强制刷新所有数据
python fund_screener.py --refresh

python fund_screener.py --holdings          # 持仓分析（走缓存）
python fund_screener.py --holdings --refresh # 强制刷新净值数据

010855,
009665,
110030,
012590,
023722,
006989,
002701,
008332,
004585,
016709,
022769,
019624,
000356,
010214,
011499,
009037,
012895,
006060,
012081,
001135,
014847,
481006,
010737,
010378,

