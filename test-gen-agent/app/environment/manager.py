"""
环境状态可视化 + 容器环境拉起 + 告警模块
====================================
提供：
  - 环境注册与状态追踪（在线/离线/异常/维护中）
  - 容器环境一键拉起（基于 Docker Compose / 单容器）
  - 环境告警（健康检查失败、资源超限、服务异常自动触发通知）
"""
import json
import os
import sqlite3
import subprocess
import time
import uuid
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

# 统一使用 Database 连接池管理
from app.core.database import Database

# 环境状态
ENV_STATUS_ONLINE = "online"
ENV_STATUS_OFFLINE = "offline"
ENV_STATUS_ERROR = "error"
ENV_STATUS_MAINTENANCE = "maintenance"
ENV_STATUS_LAUNCHING = "launching"

VALID_STATUSES = {
    ENV_STATUS_ONLINE, ENV_STATUS_OFFLINE,
    ENV_STATUS_ERROR, ENV_STATUS_MAINTENANCE,
    ENV_STATUS_LAUNCHING,
}

# 告警级别
ALERT_LEVEL_INFO = "info"
ALERT_LEVEL_WARNING = "warning"
ALERT_LEVEL_CRITICAL = "critical"

VALID_ALERT_LEVELS = {ALERT_LEVEL_INFO, ALERT_LEVEL_WARNING, ALERT_LEVEL_CRITICAL}



def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("environments.db")


def _init_db() -> None:
    """初始化表结构（使用独立临时连接）。"""
    conn = _get_conn()
    try:
        # 环境表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS environments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                env_type TEXT DEFAULT 'docker',
                status TEXT DEFAULT 'offline',
                endpoint TEXT DEFAULT '',
                docker_compose_path TEXT DEFAULT '',
                container_name TEXT DEFAULT '',
                image TEXT DEFAULT '',
                health_check_url TEXT DEFAULT '',
                owner TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                last_checked_at REAL,
                last_status_change REAL,
                error_message TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL,
                deleted INTEGER DEFAULT 0,
                deleted_at REAL
            )
        """)
        # 迁移：为历史库补充软删除列
        cols = [r[1] for r in conn.execute("PRAGMA table_info(environments)").fetchall()]
        if "deleted" not in cols:
            conn.execute("ALTER TABLE environments ADD COLUMN deleted INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE environments ADD COLUMN deleted_at REAL")
        # 告警记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                env_id TEXT,
                env_name TEXT DEFAULT '',
                level TEXT DEFAULT 'warning',
                message TEXT DEFAULT '',
                detail TEXT DEFAULT '',
                status TEXT DEFAULT 'open',
                created_at REAL,
                resolved_at REAL
            )
        """)
        conn.commit()
    finally:
        pass  # shared cached conn


_init_db()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    for k in ("tags",):
        if data.get(k):
            try:
                data[k] = json.loads(data[k])
            except (json.JSONDecodeError, TypeError):
                pass
    return data


# ═══════════════════════════════════════════════════════════
# 环境 CRUD
# ═══════════════════════════════════════════════════════════

def register_environment(
    name: str,
    description: str = "",
    env_type: str = "docker",
    endpoint: str = "",
    docker_compose_path: str = "",
    container_name: str = "",
    image: str = "",
    health_check_url: str = "",
    owner: str = "",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """注册新环境。"""
    env_id = uuid.uuid4().hex[:12]
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO environments
               (id, name, description, env_type, status, endpoint,
                docker_compose_path, container_name, image,
                health_check_url, owner, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (env_id, name, description, env_type, ENV_STATUS_OFFLINE,
             endpoint, docker_compose_path, container_name, image,
             health_check_url, owner, json.dumps(tags or []), now, now),
        )
        conn.commit()
        logger.info("环境已注册 [id=%s, name=%s]", env_id, name)
        return get_environment(env_id) or {"id": env_id}
    finally:
        pass  # shared cached conn


def get_environment(env_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM environments WHERE id = ?", (env_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        pass  # shared cached conn


def list_environments(
    status: Optional[str] = None,
    env_type: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        query = "SELECT * FROM environments WHERE (deleted IS NULL OR deleted = 0)"
        params: List = []
        if status and status in VALID_STATUSES:
            query += " AND status = ?"
            params.append(status)
        if env_type:
            query += " AND env_type = ?"
            params.append(env_type)
        if search:
            query += " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY updated_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def update_environment(env_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    existing = get_environment(env_id)
    if not existing:
        return None

    allowed = {"name", "description", "env_type", "endpoint", "status",
               "docker_compose_path", "container_name", "image",
               "health_check_url", "owner", "tags", "error_message",
               "last_checked_at", "last_status_change"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}

    if "tags" in updates and isinstance(updates["tags"], list):
        updates["tags"] = json.dumps(updates["tags"])
    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise ValueError(f"无效环境状态: {updates['status']}")

    if not updates:
        return existing

    updates["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [env_id]

    conn = _get_conn()
    try:
        conn.execute(f"UPDATE environments SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return get_environment(env_id)
    finally:
        pass  # shared cached conn


def delete_environment(env_id: str, permanent: bool = False) -> bool:
    """删除环境。默认软删除（进入回收站），permanent=True 时彻底删除。"""
    conn = _get_conn()
    try:
        if permanent:
            cur = conn.execute("DELETE FROM environments WHERE id = ?", (env_id,))
        else:
            cur = conn.execute(
                "UPDATE environments SET deleted = 1, deleted_at = ? WHERE id = ? AND (deleted IS NULL OR deleted = 0)",
                (time.time(), env_id),
            )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def list_trash_environments() -> List[Dict[str, Any]]:
    """列出回收站中的环境。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM environments WHERE deleted = 1 ORDER BY deleted_at DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def restore_environment(env_id: str) -> bool:
    """从回收站恢复环境。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE environments SET deleted = 0, deleted_at = NULL WHERE id = ? AND deleted = 1",
            (env_id,),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


# ═══════════════════════════════════════════════════════════
# 容器环境拉起 / 停止
# ═══════════════════════════════════════════════════════════

def _is_docker_available() -> bool:
    """检查 Docker 是否可用。"""
    try:
        result = subprocess.run(
            ["docker", "--version"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def launch_environment(env_id: str) -> Dict[str, Any]:
    """
    拉起环境容器。
    支持两种方式：
      1. Docker Compose: 指定 docker_compose_path
      2. 单容器: 指定 image + container_name
    """
    env = get_environment(env_id)
    if not env:
        raise ValueError(f"环境 {env_id} 不存在")

    if not _is_docker_available():
        update_environment(env_id, status=ENV_STATUS_ERROR,
                           error_message="Docker 不可用")
        _create_alert(env_id, env["name"], ALERT_LEVEL_CRITICAL,
                      "环境启动失败", "Docker 命令不可用，无法拉起容器")
        return {"success": False, "error": "Docker 不可用"}

    update_environment(env_id, status=ENV_STATUS_LAUNCHING)

    try:
        if env.get("docker_compose_path"):
            result = subprocess.run(
                ["docker", "compose", "-f", env["docker_compose_path"], "up", "-d"],
                capture_output=True, timeout=120,
            )
            command_desc = f"docker compose -f {env['docker_compose_path']} up -d"
        elif env.get("container_name") and env.get("image"):
            result = subprocess.run(
                ["docker", "run", "-d", "--name", env["container_name"], env["image"]],
                capture_output=True, timeout=120,
            )
            command_desc = f"docker run -d --name {env['container_name']} {env['image']}"
        else:
            update_environment(env_id, status=ENV_STATUS_ERROR,
                               error_message="缺少容器配置（compose 文件或 image）")
            _create_alert(env_id, env["name"], ALERT_LEVEL_WARNING,
                          "环境启动失败", "缺少容器配置信息")
            return {"success": False, "error": "缺少容器配置"}

        if result.returncode == 0:
            update_environment(env_id, status=ENV_STATUS_ONLINE,
                               error_message="", last_status_change=time.time())
            logger.info("环境已拉起 [id=%s, cmd=%s]", env_id, command_desc)
            return {"success": True, "command": command_desc,
                    "output": result.stdout.decode("utf-8", errors="replace")[:500]}
        else:
            error_msg = result.stderr.decode("utf-8", errors="replace")[:500]
            update_environment(env_id, status=ENV_STATUS_ERROR, error_message=error_msg)
            _create_alert(env_id, env["name"], ALERT_LEVEL_CRITICAL,
                          "环境启动失败", error_msg)
            return {"success": False, "error": error_msg}

    except subprocess.TimeoutExpired:
        update_environment(env_id, status=ENV_STATUS_ERROR,
                           error_message="容器启动超时")
        _create_alert(env_id, env["name"], ALERT_LEVEL_CRITICAL,
                      "环境启动超时", "容器启动超过 120 秒未完成")
        return {"success": False, "error": "容器启动超时"}
    except Exception as e:
        update_environment(env_id, status=ENV_STATUS_ERROR, error_message=str(e))
        _create_alert(env_id, env["name"], ALERT_LEVEL_CRITICAL,
                      "环境启动异常", str(e))
        return {"success": False, "error": str(e)}


def stop_environment(env_id: str) -> Dict[str, Any]:
    """停止环境容器。"""
    env = get_environment(env_id)
    if not env:
        raise ValueError(f"环境 {env_id} 不存在")

    if not _is_docker_available():
        return {"success": False, "error": "Docker 不可用"}

    try:
        if env.get("docker_compose_path"):
            result = subprocess.run(
                ["docker", "compose", "-f", env["docker_compose_path"], "down"],
                capture_output=True, timeout=60,
            )
        elif env.get("container_name"):
            result = subprocess.run(
                ["docker", "stop", env["container_name"]],
                capture_output=True, timeout=60,
            )
        else:
            return {"success": False, "error": "缺少容器配置"}

        if result.returncode == 0:
            update_environment(env_id, status=ENV_STATUS_OFFLINE,
                               error_message="", last_status_change=time.time())
            return {"success": True}
        else:
            error_msg = result.stderr.decode("utf-8", errors="replace")[:300]
            return {"success": False, "error": error_msg}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "停止容器超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 健康检查与状态检测
# ═══════════════════════════════════════════════════════════

def check_environment_health(env_id: str) -> Dict[str, Any]:
    """检查环境健康状况，自动更新状态并触发告警。"""
    env = get_environment(env_id)
    if not env:
        return {"success": False, "error": f"环境 {env_id} 不存在"}

    # 1. 检查 Docker 容器状态
    docker_ok = False
    if env.get("container_name"):
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", env["container_name"]],
                capture_output=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip() == "true":
                docker_ok = True
        except Exception:
            pass
    elif env.get("docker_compose_path"):
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", env["docker_compose_path"], "ps", "-q"],
                capture_output=True, timeout=10,
            )
            docker_ok = result.returncode == 0 and result.stdout.strip() != ""
        except Exception:
            pass

    # 2. HTTP 健康检查
    http_ok = False
    http_detail = ""
    if env.get("health_check_url"):
        import urllib.request
        try:
            req = urllib.request.Request(
                env["health_check_url"], method="GET", timeout=5,
            )
            with urllib.request.urlopen(req) as resp:
                http_ok = resp.status == 200
                http_detail = f"HTTP {resp.status}"
        except Exception as e:
            http_detail = str(e)[:200]

    # 3. 判定状态
    now = time.time()
    if not docker_ok and not http_ok:
        update_environment(env_id, status=ENV_STATUS_OFFLINE,
                           last_checked_at=now,
                           error_message="容器未运行且健康检查失败")
        _create_alert(env_id, env["name"], ALERT_LEVEL_CRITICAL,
                      "环境健康检查失败", "容器未运行，健康检查失败")
        return {"success": False, "status": ENV_STATUS_OFFLINE,
                "docker": docker_ok, "http": http_ok}
    elif not docker_ok:
        update_environment(env_id, status=ENV_STATUS_ERROR,
                           last_checked_at=now,
                           error_message=f"Docker 容器未运行 (HTTP: {http_detail})")
        _create_alert(env_id, env["name"], ALERT_LEVEL_WARNING,
                      "容器状态异常", "容器未运行，但健康检查通过")
        return {"success": False, "status": ENV_STATUS_ERROR,
                "docker": docker_ok, "http": http_ok}
    elif not http_ok:
        update_environment(env_id, status=ENV_STATUS_ERROR,
                           last_checked_at=now,
                           error_message=f"健康检查失败 ({http_detail})")
        _create_alert(env_id, env["name"], ALERT_LEVEL_WARNING,
                      "环境健康检查异常", f"HTTP 健康检查失败: {http_detail}")
        return {"success": False, "status": ENV_STATUS_ERROR,
                "docker": docker_ok, "http": http_ok}

    # 全部正常
    update_environment(env_id, status=ENV_STATUS_ONLINE,
                       last_checked_at=now, error_message="")
    return {"success": True, "status": ENV_STATUS_ONLINE,
            "docker": docker_ok, "http": http_ok}


def check_all_environments() -> Dict[str, Any]:
    """批量检查所有环境健康状态。"""
    envs = list_environments()
    results = {"total": len(envs), "online": 0, "error": 0, "offline": 0, "detail": []}
    for env in envs:
        if env["status"] == ENV_STATUS_MAINTENANCE:
            results["detail"].append({
                "env_id": env["id"], "name": env["name"],
                "status": ENV_STATUS_MAINTENANCE, "success": True,
            })
            continue
        r = check_environment_health(env["id"])
        detail = {
            "env_id": env["id"],
            "name": env["name"],
            "status": r.get("status", env["status"]),
            "success": r.get("success", False),
            "error": r.get("error", ""),
        }
        results["detail"].append(detail)
        if detail["status"] == ENV_STATUS_ONLINE:
            results["online"] += 1
        elif detail["status"] == ENV_STATUS_ERROR:
            results["error"] += 1
        else:
            results["offline"] += 1
    return results


# ═══════════════════════════════════════════════════════════
# 告警管理
# ═══════════════════════════════════════════════════════════

def _create_alert(
    env_id: str,
    env_name: str,
    level: str,
    message: str,
    detail: str = "",
) -> Dict[str, Any]:
    """创建告警记录。"""
    alert_id = uuid.uuid4().hex[:12]
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO alerts
               (id, env_id, env_name, level, message, detail, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (alert_id, env_id, env_name, level, message, detail, "open", now),
        )
        conn.commit()
        logger.warning("环境告警 [env=%s, level=%s, msg=%s]", env_name, level, message)
        return {"id": alert_id, "env_id": env_id, "env_name": env_name,
                "level": level, "message": message, "detail": detail,
                "status": "open", "created_at": now}
    finally:
        pass  # shared cached conn


def list_alerts(
    status: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        query = "SELECT * FROM alerts WHERE 1=1"
        params: List = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if level and level in VALID_ALERT_LEVELS:
            query += " AND level = ?"
            params.append(level)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def resolve_alert(alert_id: str) -> bool:
    """标记告警为已解决。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE alerts SET status = 'resolved', resolved_at = ? WHERE id = ? AND status = 'open'",
            (time.time(), alert_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def get_stats() -> Dict[str, Any]:
    """获取环境与告警统计。"""
    conn = _get_conn()
    try:
        env_total = conn.execute("SELECT COUNT(*) FROM environments").fetchone()[0]
        # 一次 GROUP BY 查询代替逐状态 COUNT（消除 N+1）
        by_status = {s: 0 for s in VALID_STATUSES}
        for row in conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM environments GROUP BY status"
        ):
            if row["status"] in by_status:
                by_status[row["status"]] = row["cnt"]

        alert_open = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE status = 'open'"
        ).fetchone()[0]
        alert_total = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]

        return {
            "env_total": env_total,
            "env_by_status": by_status,
            "alert_open": alert_open,
            "alert_total": alert_total,
        }
    finally:
        pass  # shared cached conn
