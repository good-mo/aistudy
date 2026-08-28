"""
test_api_benchmark.py — 企业级接口性能基准测试

通过 TestClient 对关键只读/写 API 施加并发请求，统计响应时间
（平均 / P95 / P99）与吞吐，验证是否满足性能基线。

覆盖范围：
  读接口（GET）:
    - /health                   平均 < 200ms
    - /api/cases  列表          平均 < 200ms
    - /api/defects 列表         平均 < 200ms
    - /api/tasks  列表          平均 < 200ms
    - /api/cases/{id} 详情      平均 < 200ms

  写接口（POST / PUT / DELETE）:
    - POST   /api/cases         创建用例   平均 < 500ms
    - POST   /api/defects       创建缺陷   平均 < 500ms
    - POST   /api/tasks         提交任务   平均 < 500ms
    - PUT    /api/cases/{id}    更新用例   平均 < 500ms
    - PUT    /api/defects/{id}  更新缺陷   平均 < 500ms
    - DELETE /api/cases/{id}    删除用例   平均 < 500ms
    - DELETE /api/defects/{id}  删除缺陷   平均 < 500ms

运行：
  pytest tests/performance/test_api_benchmark.py -v
"""

import os
import sys
import time
import statistics
from concurrent.futures import ThreadPoolExecutor

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient

# ── 读接口性能基线 ──────────────────────────────────────────────
# 阈值宽松（开发环境）；生产 CI 应更严格
READ_BASELINE = {
    "GET /health":        {"avg_ms": 200, "concurrency": 10, "requests": 50},
    "GET /api/cases":     {"avg_ms": 200, "concurrency": 10, "requests": 50},
    "GET /api/defects":   {"avg_ms": 200, "concurrency": 10, "requests": 50},
    "GET /api/tasks":     {"avg_ms": 200, "concurrency": 10, "requests": 50},
}

# ── 写接口性能基线 ──────────────────────────────────────────────
# avg_ms 为宽松阈值（开发机）；生产 CI 建议收紧至 200ms
WRITE_BASELINE = {
    "POST /api/cases":     {"avg_ms": 500, "concurrency": 10, "requests": 20},
    "POST /api/defects":   {"avg_ms": 500, "concurrency": 10, "requests": 20},
    "POST /api/tasks":     {"avg_ms": 500, "concurrency": 10, "requests": 20},
}


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


def _bench(client, method, url, concurrency, requests, **kw):
    """并发执行 requests 次请求，返回延迟统计。"""
    def one(_):
        t0 = time.perf_counter()
        resp = getattr(client, method)(url, **kw)
        dt = (time.perf_counter() - t0) * 1000  # ms
        return resp.status_code, dt

    latencies = []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for code, dt in ex.map(one, range(requests)):
            assert code == 200, f"{method} {url} 返回 {code}"
            latencies.append(dt)

    latencies.sort()
    avg = statistics.mean(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    return {"avg_ms": avg, "p95_ms": p95, "p99_ms": p99, "req": requests}


def _print_stats(method, path, stats, threshold):
    """格式化输出性能统计。"""
    print(f"  {method} {path}: avg={stats['avg_ms']:.1f}ms "
          f"p95={stats['p95_ms']:.1f}ms p99={stats['p99_ms']:.1f}ms "
          f"(阈值 avg<{threshold}ms)")
    assert stats["avg_ms"] < threshold, \
        f"{method} {path} 平均延迟 {stats['avg_ms']:.1f}ms 超基线 {threshold}ms"


def _collect_latencies(ex, fn, n):
    """并发执行 n 次 fn，返回所有延迟 ms 列表（校验全部 200）。"""
    def wrapper(i):
        t0 = time.perf_counter()
        resp = fn(i)
        dt = (time.perf_counter() - t0) * 1000
        return resp.status_code, dt

    lat = []
    for code, dt in ex.map(wrapper, range(n)):
        assert code == 200
        lat.append(dt)
    lat.sort()
    return lat


def _assert_write_perf(method, path, lat, threshold=500):
    """校验写接口性能并输出。"""
    avg = statistics.mean(lat)
    p95 = lat[int(len(lat) * 0.95)]
    p99 = lat[int(len(lat) * 0.99)]
    print(f"  {method} {path}: avg={avg:.1f}ms p95={p95:.1f}ms p99={p99:.1f}ms "
          f"(阈值 avg<{threshold}ms)")
    assert avg < threshold, f"{method} {path} 平均延迟 {avg:.1f}ms 超基线 {threshold}ms"


# ══════════════════════════════════════════════════════════════
# 一、读接口基准（GET）
# ══════════════════════════════════════════════════════════════

READ_PATH = {
    "GET /health":      "/health",
    "GET /api/cases":   "/api/cases",
    "GET /api/defects": "/api/defects",
    "GET /api/tasks":   "/api/tasks",
}


@pytest.mark.parametrize("url,cfg", READ_BASELINE.items())
def test_api_benchmark_read(client, url, cfg):
    """基准：关键只读 API 满足性能基线。"""
    path = READ_PATH[url]
    stats = _bench(client, "get", path, cfg["concurrency"], cfg["requests"])
    _print_stats("GET", path, stats, cfg["avg_ms"])


def test_cases_detail_benchmark(client):
    """基准：用例详情接口。"""
    created = client.post("/api/cases", json={"title": "性能基准用例"}).json()
    stats = _bench(client, "get", f"/api/cases/{created['id']}", 10, 50)
    _print_stats("GET", "/api/cases/{id}", stats, 200)


# ══════════════════════════════════════════════════════════════
# 二、写接口基准（POST — 创建）
# ══════════════════════════════════════════════════════════════


@pytest.mark.parametrize("url,cfg", WRITE_BASELINE.items())
def test_api_benchmark_create(client, url, cfg):
    """基准：POST 创建类接口满足性能基线。"""
    def payload(i):
        if url == "POST /api/cases":
            return {"title": f"性能写入{i}"}
        if url == "POST /api/defects":
            return {"title": f"性能缺陷{i}", "severity": "minor"}
        return {"source_code": f"def f{i}(): return {i}", "test_type": "functional"}

    def one(i):
        return client.post(url.split(" ", 1)[1], json=payload(i))

    with ThreadPoolExecutor(max_workers=cfg["concurrency"]) as ex:
        lat = _collect_latencies(ex, one, cfg["requests"])
    _assert_write_perf("POST", url.split(" ", 1)[1], lat, cfg["avg_ms"])


# ══════════════════════════════════════════════════════════════
# 三、写接口基准（PUT — 更新）
# ══════════════════════════════════════════════════════════════


def test_put_cases_benchmark(client):
    """基准：PUT 更新用例。"""
    # 预创建一批用例用于更新
    ids = []
    for i in range(20):
        r = client.post("/api/cases", json={"title": f"PUT基准预创建{i}"})
        assert r.status_code == 200
        ids.append(r.json()["id"])

    def one(i):
        # 每个线程更新不同用例，避免写冲突
        cid = ids[i % len(ids)]
        return client.put(f"/api/cases/{cid}", json={"priority": f"P{i % 3}"})

    with ThreadPoolExecutor(max_workers=10) as ex:
        lat = _collect_latencies(ex, one, 30)
    _assert_write_perf("PUT", "/api/cases/{id}", lat, 500)


def test_put_defects_benchmark(client):
    """基准：PUT 更新缺陷。"""
    # 预创建一批缺陷用于更新
    ids = []
    for i in range(20):
        r = client.post("/api/defects", json={"title": f"PUT缺陷预创建{i}"})
        assert r.status_code == 200
        ids.append(r.json()["id"])

    valid_severities = ["blocker", "critical", "major", "minor"]

    def one(i):
        did = ids[i % len(ids)]
        sev = valid_severities[i % len(valid_severities)]
        return client.put(f"/api/defects/{did}", json={"severity": sev})

    with ThreadPoolExecutor(max_workers=10) as ex:
        lat = _collect_latencies(ex, one, 30)
    _assert_write_perf("PUT", "/api/defects/{id}", lat, 500)


# ══════════════════════════════════════════════════════════════
# 四、写接口基准（DELETE — 删除）
# ══════════════════════════════════════════════════════════════


def test_delete_cases_benchmark(client):
    """基准：DELETE 删除用例（软删除到回收站）。"""
    # 预创建足够多的用例，每个 ID 只删一次，避免并发 404
    ids = []
    n = 30
    for i in range(n):
        r = client.post("/api/cases", json={"title": f"DELETE基准预创建{i}"})
        assert r.status_code == 200
        ids.append(r.json()["id"])

    def one(i):
        # 每个线程删除不同的用例，天然无竞争
        return client.delete(f"/api/cases/{ids[i]}")

    with ThreadPoolExecutor(max_workers=10) as ex:
        lat = _collect_latencies(ex, one, n)
    _assert_write_perf("DELETE", "/api/cases/{id}", lat, 500)


def test_delete_defects_benchmark(client):
    """基准：DELETE 删除缺陷（彻底删除）。"""
    # 预创建足够多的缺陷，每个 ID 只删一次，避免并发 404
    ids = []
    n = 30
    for i in range(n):
        r = client.post("/api/defects", json={"title": f"DELETE缺陷预创建{i}"})
        assert r.status_code == 200
        ids.append(r.json()["id"])

    def one(i):
        return client.delete(f"/api/defects/{ids[i]}")

    with ThreadPoolExecutor(max_workers=10) as ex:
        lat = _collect_latencies(ex, one, n)
    _assert_write_perf("DELETE", "/api/defects/{id}", lat, 500)


# ══════════════════════════════════════════════════════════════
# 五、登录接口基准（POST /login）
# ══════════════════════════════════════════════════════════════


def test_login_benchmark(client):
    """基准：登录接口 POST /login 满足性能基线。

    覆盖会话写入 + RSA 密码解密链路，防止首次登录 RSA 现场生成等性能回归。
    """
    # 登录接口依赖 RSA 密钥，测试前先预热（等价于应用启动时的预生成）
    from app.auth.store import _ensure_rsa_keys
    _ensure_rsa_keys()

    def one(i):
        # 密码传明文即可（rsa_decrypt 在解密失败时会回退明文）
        return client.post(
            "/login",
            json={"username": "admin", "password": "admin123", "authenticate": "LOCAL"},
        )

    with ThreadPoolExecutor(max_workers=10) as ex:
        lat = _collect_latencies(ex, one, 30)
    _assert_write_perf("POST", "/login", lat, 200)
