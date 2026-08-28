"""StockWatcher 综合买卖建议（多维度指标融合）单元测试。

覆盖 monitor.py 中新增的综合评分逻辑：
    - _tech_score_to_100：技术信号归一化
    - _composite_score：多维度融合
    - _composite_level：综合分 → 买卖建议
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.domains.stock_watch.monitor import StockWatcher


class TestTechScoreTo100:
    def test_normalize_mid(self):
        w = StockWatcher(watch_list={})
        # score=0（中性）→ 50
        assert w._tech_score_to_100(0) == 50.0

    def test_normalize_strong_buy(self):
        w = StockWatcher(watch_list={})
        # score=25（强买入上限）→ 100
        assert w._tech_score_to_100(25) == 100.0

    def test_normalize_strong_sell(self):
        w = StockWatcher(watch_list={})
        # score=-25 → 0
        assert w._tech_score_to_100(-25) == 0.0

    def test_normalize_clamp(self):
        w = StockWatcher(watch_list={})
        # 超出范围时被夹取到 [0,100]
        assert w._tech_score_to_100(100) == 100.0
        assert w._tech_score_to_100(-100) == 0.0

    def test_none(self):
        w = StockWatcher(watch_list={})
        assert w._tech_score_to_100(None) is None


class _FakeSnap:
    """用于构造各维度评分的假快照对象。"""

    def __init__(self, score):
        self.score = score


class TestCompositeScore:
    def _watcher(self):
        return StockWatcher(watch_list={})

    def test_all_dims_present(self):
        w = self._watcher()
        indicators = {
            "fundamental": _FakeSnap(80),
            "money_flow": _FakeSnap(70),
            "advanced": _FakeSnap(60),
            "risk": _FakeSnap(20),
        }
        # safety = 100 - 20 = 80
        # composite = 50*.4 + 80*.2 + 70*.15 + 60*.15 + 80*.1
        #           = 20 + 16 + 10.5 + 9 + 8 = 63.5
        c = w._composite_score(50.0, indicators)
        assert c is not None
        assert abs(c - 63.5) < 0.01

    def test_partial_dims(self):
        w = self._watcher()
        indicators = {
            "fundamental": _FakeSnap(80),
            "money_flow": _FakeSnap(None),
            "advanced": _FakeSnap(None),
            "risk": _FakeSnap(None),
        }
        # 只有 tech(40%) 与 fundamental(20%) 可用，权重归一
        # composite = (50*.4 + 80*.2) / (0.4+0.2) = (20+16)/0.6 = 60
        c = w._composite_score(50.0, indicators)
        assert c is not None
        assert abs(c - 60.0) < 0.01

    def test_all_none(self):
        w = self._watcher()
        indicators = {
            "fundamental": _FakeSnap(None),
            "money_flow": _FakeSnap(None),
            "advanced": _FakeSnap(None),
            "risk": _FakeSnap(None),
        }
        assert w._composite_score(None, indicators) is None


class TestCompositeLevel:
    def test_strong_buy(self):
        assert StockWatcher._composite_level(80) == "🟢 强买入"

    def test_buy(self):
        assert StockWatcher._composite_level(65) == "🔵 买入"

    def test_hold(self):
        assert StockWatcher._composite_level(50) == "⚪ 观望"

    def test_sell(self):
        assert StockWatcher._composite_level(35) == "🟠 卖出"

    def test_strong_sell(self):
        assert StockWatcher._composite_level(20) == "🔴 强卖出"

    def test_boundaries(self):
        # 边界值
        assert StockWatcher._composite_level(75) == "🟢 强买入"
        assert StockWatcher._composite_level(74.9) == "🔵 买入"
        assert StockWatcher._composite_level(60) == "🔵 买入"
        assert StockWatcher._composite_level(40) == "🟠 卖出"
        assert StockWatcher._composite_level(25) == "🔴 强卖出"

    def test_none(self):
        assert StockWatcher._composite_level(None) == "⚪ 观望"
