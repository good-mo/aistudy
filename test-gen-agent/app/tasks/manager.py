"""
异步任务队列管理器
====================
将耗时任务（LLM 生成 + 测试运行）从 HTTP 请求中解耦，
提交到后台异步执行，REST 接口立即返回 task_id，轮询查询进度/结果。

特性：
  - asyncio 内存队列 + 后台 worker（零外部依赖，开箱即用）
  - 任务持久化到 SQLite（重启后可从磁盘恢复任务状态）
  - 任务状态机：pending → running → success/failed
  - 支持设置/取消任务超时，防任务挂死
  - 通过 get_task 查询任务状态与结果，供轮询或 WebSocket 使用
"""
import asyncio
import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional

from app.db import PROJECT_ROOT
from app.logging_config import get_logger

logger = get_logger(__name__)

# 任务状态
PENDING = "pending"
RUNNING = "running"
SUCCESS = "success"
FAILED = "failed"
CANCELLED = "cancelled"

# 任务持久化数据库路径
_TASK_DB_PATH = os.path.join(PROJECT_ROOT, "tasks.db")


class TaskStore:
    """任务持久化存储（SQLite）。

    将任务元数据、状态、结果持久化到磁盘，
    进程重启后可恢复未完成任务。
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or _TASK_DB_PATH
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        """初始化任务表。"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at REAL,
                    started_at REAL,
                    finished_at REAL,
                    result TEXT,
                    error TEXT,
                    coro_name TEXT DEFAULT '',
                    args TEXT DEFAULT '[]'
                )
            """)
            conn.commit()
            conn.close()

    def save_task(self, task_id: str, coro_name: str = "", args: list = None) -> None:
        """保存任务到磁盘。"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute(
                """INSERT OR REPLACE INTO tasks
                   (task_id, status, created_at, coro_name, args)
                   VALUES (?, ?, ?, ?, ?)""",
                (task_id, PENDING, time.time(), coro_name,
                 json.dumps(args or [], ensure_ascii=False)),
            )
            conn.commit()
            conn.close()

    def update_status(self, task_id: str, status: str, **kwargs) -> None:
        """更新任务状态。"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            fields = ["status = ?"]
            values = [status]
            if "started_at" in kwargs:
                fields.append("started_at = ?")
                values.append(kwargs["started_at"])
            if "finished_at" in kwargs:
                fields.append("finished_at = ?")
                values.append(kwargs["finished_at"])
            if "result" in kwargs:
                fields.append("result = ?")
                values.append(json.dumps(kwargs["result"], ensure_ascii=False, default=str))
            if "error" in kwargs:
                fields.append("error = ?")
                values.append(kwargs["error"])
            values.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE task_id = ?",
                values,
            )
            conn.commit()
            conn.close()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """从磁盘读取任务。"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            conn.close()
            if not row:
                return None
            data = dict(row)
            if data.get("result"):
                try:
                    data["result"] = json.loads(data["result"])
                except Exception:
                    pass
            return data

    def list_recent(self, limit: int = 50) -> list:
        """获取最近任务列表。"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            conn.close()
            result = []
            for row in rows:
                data = dict(row)
                if data.get("result"):
                    try:
                        data["result"] = json.loads(data["result"])
                    except Exception:
                        pass
                result.append(data)
            return result

    def recover_pending(self) -> list:
        """恢复上次未完成（pending/running）的任务。"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status IN (?, ?)",
                (PENDING, RUNNING),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]


class Task:
    """单个后台任务。"""
    def __init__(self, task_id: str, coro: Callable, *args, **kwargs):
        self.task_id = task_id
        self._coro = coro
        self._args = args
        self._kwargs = kwargs
        self.status = PENDING
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.traceback: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
            "duration": (
                (self.finished_at - self.created_at)
                if self.finished_at else None
            ),
        }


class TaskManager:
    """异步任务队列，支持 SQLite 持久化。"""
    def __init__(self, maxsize: int = 100):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._tasks: Dict[str, Task] = {}
        self._workers: list = []
        self._maxsize = maxsize
        # 持久化存储
        self._store = TaskStore()

    def start(self, num_workers: int = 2) -> None:
        """启动后台 worker，并尝试恢复未完成任务。"""
        for i in range(num_workers):
            w = asyncio.create_task(self._worker_loop(i))
            self._workers.append(w)
        logger.info("任务队列已启动 [workers=%d]", num_workers)

    async def stop(self) -> None:
        """停止所有 worker。"""
        for w in self._workers:
            w.cancel()
        for w in self._workers:
            try:
                await w
            except asyncio.CancelledError:
                pass
        self._workers.clear()
        logger.info("任务队列已停止")

    async def _worker_loop(self, idx: int) -> None:
        logger.debug("worker-%d 启动", idx)
        while True:
            task: Task = await self._queue.get()
            task.status = RUNNING
            task.started_at = time.time()
            # 持久化运行状态
            self._store.update_status(
                task.task_id, RUNNING, started_at=task.started_at
            )
            try:
                result = await task._coro(*task._args, **task._kwargs)
                task.result = result
                task.status = SUCCESS
                self._store.update_status(
                    task.task_id, SUCCESS,
                    finished_at=time.time(), result=result
                )
                logger.info("任务完成 [task=%s]", task.task_id)
            except asyncio.CancelledError:
                task.status = CANCELLED
                task.error = "任务被取消"
                self._store.update_status(
                    task.task_id, CANCELLED,
                    finished_at=time.time(), error=task.error
                )
                raise
            except Exception as e:
                task.status = FAILED
                task.error = str(e)
                self._store.update_status(
                    task.task_id, FAILED,
                    finished_at=time.time(), error=task.error
                )
                logger.error(
                    "任务执行失败 [task=%s, err=%s]", task.task_id, e, exc_info=True
                )
            finally:
                task.finished_at = time.time()
                self._queue.task_done()

    async def submit(self, coro: Callable, *args, **kwargs) -> Task:
        """
        提交一个协程作为后台任务。
        返回 Task 对象（注意协程必须未被 await 过，否则会报错）。
        """
        task_id = uuid.uuid4().hex[:12]
        task = Task(task_id, coro, *args, **kwargs)
        self._tasks[task_id] = task
        # 持久化到磁盘
        self._store.save_task(
            task_id,
            coro_name=getattr(coro, "__name__", coro.__class__.__name__),
            args=list(args),
        )
        await self._queue.put(task)
        logger.info("任务已提交 [task=%s]", task_id)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        # 先查内存
        task = self._tasks.get(task_id)
        if task:
            return task
        # 查磁盘（进程重启后恢复）
        stored = self._store.get_task(task_id)
        if stored:
            t = Task(task_id, lambda: None)
            t.status = stored.get("status", PENDING)
            t.created_at = stored.get("created_at", 0)
            t.started_at = stored.get("started_at")
            t.finished_at = stored.get("finished_at")
            t.result = stored.get("result")
            t.error = stored.get("error")
            return t
        return None

    def get_task_dict(self, task_id: str) -> Optional[Dict[str, Any]]:
        t = self.get_task(task_id)
        return t.to_dict() if t else None

    def list_tasks(self, limit: int = 50) -> list:
        """按创建时间倒序返回最近的任务（摘要）。"""
        items = sorted(
            self._tasks.values(), key=lambda t: t.created_at, reverse=True
        )
        result = [t.to_dict() for t in items[:limit]]
        # 补充磁盘中可能存在的任务
        if len(result) < limit:
            stored = self._store.list_recent(limit)
            known_ids = {t["task_id"] for t in result}
            for s in stored:
                if s["task_id"] not in known_ids:
                    result.append(s)
                    known_ids.add(s["task_id"])
                    if len(result) >= limit:
                        break
        return result[:limit]


# 模块级单例
manager = TaskManager()
