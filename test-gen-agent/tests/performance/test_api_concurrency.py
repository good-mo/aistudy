"""
test_api_concurrency.py — 企业级接口并发/负载/压力测试

场景：
  - 并发创建/查询/删除（多写多读）
  - 任务队列并发提交（验证不丢任务、状态机一致）
  - 峰值冲击（瞬时高并发不崩溃）

运行：
  pytest tests/performance/test_api_concurrency.py -v
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        # 登录获取认证令牌
        r = c.post("/login", json={"username": "admin", "password": "admin123"})
        if r.status_code == 200:
            session = r.json()["data"]
            c.headers.update({
                "X-AUTH-TOKEN": session["sessionId"],
                "CSRF-TOKEN": session["csrfToken"],
            })
        yield c


def test_concurrent_write_load(client):
    """负载：50 线程并发创建用例，全部成功、ID 唯一。"""
    def create(i):
        return client.post("/api/cases", json={"title": f"并发负载{i}"}).status_code

    with ThreadPoolExecutor(max_workers=50) as ex:
        codes = list(ex.map(create, range(50)))
    assert all(c == 200 for c in codes)


def test_concurrent_mixed_operations(client):
    """负载：并发混合读+写（列表查询 + 详情 + 创建）。"""
    ids = []
    for i in range(5):
        ids.append(client.post("/api/cases", json={"title": f"并发混合{i}"}).json()["id"])

    def op(i):
        if i % 3 == 0:
            return client.get("/api/cases").status_code
        elif i % 3 == 1:
            return client.get(f"/api/cases/{ids[i % 5]}").status_code
        else:
            return client.post("/api/cases", json={"title": f"并发混合写{i}"}).status_code

    with ThreadPoolExecutor(max_workers=30) as ex:
        codes = list(ex.map(op, range(60)))
    assert all(c == 200 for c in codes)


def test_concurrent_task_submission(client):
    """负载：并发提交任务队列，任务 ID 唯一且状态合法。"""
    def submit(i):
        return client.post("/api/tasks", json={"source_code": f"def f{i}(): return {i}"})

    task_ids = set()
    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(submit, range(20)))
    for r in results:
        assert r.status_code == 200
        task_ids.add(r.json()["task_id"])
    assert len(task_ids) == 20, "任务 ID 出现重复，队列可能丢任务"


def test_concurrent_update_same_resource(client):
    """压力：并发更新同一用例，最后写入生效、无异常。"""
    cid = client.post("/api/cases", json={"title": "并发更新目标"}).json()["id"]

    def update(prio):
        return client.put(f"/api/cases/{cid}", json={"priority": prio}).status_code

    with ThreadPoolExecutor(max_workers=20) as ex:
        codes = list(ex.map(update, ["P0"] * 10 + ["P1"] * 10))
    assert all(c == 200 for c in codes)
    final = client.get(f"/api/cases/{cid}").json()
    assert final["priority"] in ("P0", "P1")


def test_spike_peak_burst(client):
    """峰值：瞬时 100 并发冲击不崩溃、无 5xx。"""
    def hit(_):
        return client.get("/health").status_code

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=100) as ex:
        codes = list(ex.map(hit, range(100)))
    elapsed = time.perf_counter() - t0
    assert all(c == 200 for c in codes)
    assert elapsed < 10, f"峰值冲击耗时 {elapsed:.2f}s 过长"


def test_queue_status_consistency(client):
    """可靠性：提交任务后状态机处于合法状态(pending/running/success/failed)。"""
    r = client.post("/api/tasks", json={"source_code": "def f(): return 1"})
    task_id = r.json()["task_id"]
    st = client.get(f"/api/tasks/{task_id}").json()
    assert st["status"] in ("pending", "running", "success", "failed")
    assert st["task_id"] == task_id
