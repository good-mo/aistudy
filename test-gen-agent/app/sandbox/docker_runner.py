# app/sandbox/docker_runner.py
"""
Docker 容器化测试沙箱
=====================
将被测代码与测试代码在隔离的 Docker 容器中运行，
避免在宿主机上直接执行（安全隔离），并支持资源限制。

特性：
  - 容器化运行 pytest / coverage，隔离文件系统与网络
  - CPU / 内存 / 网络 限制（安全底线）
  - 自动清理临时容器
  - Docker 不可用时自动降级为宿主机子进程（容错）
"""
import os
import tempfile
import subprocess
import shutil
from typing import List, Optional
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# 沙箱基础镜像（需包含 python + pytest + coverage）
SANDBOX_IMAGE = "python:3.12-slim"
# 工作目录内的源码文件名
SRC_FILENAME = "target_module.py"
TEST_FILENAME = "test_target_module.py"


def _docker_available() -> bool:
    """检测当前环境是否有可用的 docker CLI/SDK。"""
    try:
        import docker  # noqa: F401
        return True
    except ImportError:
        return False


def _docker_client():
    from docker import from_env
    return from_env()


def run_in_sandbox(
    source_code: str,
    test_code: str,
    module_name: str = "target_module",
    command: Optional[List[str]] = None,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
    env_extra: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    """
    在 Docker 容器中执行命令，返回 subprocess.CompletedProcess 兼容对象。

    Args:
        source_code: 被测源码
        test_code:   测试代码
        module_name: 模块名（用于构建可导入的文件名）
        command:     容器内要执行的命令，默认 `pytest <test>`
        cwd:         忽略（沙箱固定工作目录）
        timeout:     执行超时（秒）
        env_extra:   注入容器的额外环境变量

    Returns:
        CompletedProcess(stdout, stderr, returncode)
    """
    timeout = timeout or settings.test_timeout
    use_docker = settings.sandbox_enabled and _docker_available()

    if not use_docker:
        # ── 降级：宿主机子进程执行 ──────────────────
        logger.warning("沙箱不可用，降级为宿主机执行（sandbox_enabled=%s）",
                       settings.sandbox_enabled)
        return _run_host_subprocess(
            source_code, test_code, module_name, command, timeout, env_extra
        )

    # ── Docker 沙箱执行 ─────────────────────────────
    logger.info("在 Docker 沙箱中执行测试 [module=%s]", module_name)
    client = _docker_client()
    workdir = tempfile.mkdtemp(prefix="sandbox_")

    try:
        src_path = os.path.join(workdir, f"{module_name}.py")
        test_path = os.path.join(workdir, f"test_{module_name}.py")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(source_code)
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(test_code)

        container = client.containers.run(
            SANDBOX_IMAGE,
            command=command or ["pytest", f"test_{module_name}.py", "-v", "--tb=short"],
            detach=True,
            volumes={workdir: {"bind": "/sandbox", "mode": "rw"}},
            working_dir="/sandbox",
            network_mode=settings.sandbox_network_mode,
            mem_limit=settings.sandbox_mem_limit,
            nano_cpus=settings.sandbox_nano_cpus,
            environment=env_extra or {},
            remove=True,
        )
        try:
            result = container.wait(timeout=timeout)
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            container.remove(force=True)
            return _CompletedProcess(
                args=command or [], returncode=result.get("StatusCode", 1),
                stdout=logs, stderr="",
            )
        except Exception as e:
            logger.error("沙箱执行超时/异常 [err=%s]", e)
            try:
                container.remove(force=True)
            except Exception:
                pass
            return _CompletedProcess(
                args=command or [], returncode=1,
                stdout="", stderr=f"Sandbox timeout or error: {e}",
            )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


class _CompletedProcess(subprocess.CompletedProcess):
    """轻量的 CompletedProcess 兼容类，便于统一接口。"""
    def __init__(self, args, returncode, stdout, stderr):
        # 直接赋值，跳过父类 __init__（父类要求 stdout 为 bytes 或 None）
        self.args = args
        self.returncode = returncode
        self.stdout = stdout if isinstance(stdout, str) else stdout.decode(errors="replace")
        self.stderr = stderr if isinstance(stderr, str) else stderr.decode(errors="replace")


def _run_host_subprocess(
    source_code, test_code, module_name, command, timeout, env_extra
) -> subprocess.CompletedProcess:
    """宿主机子进程执行（降级路径）。"""
    import subprocess
    workdir = tempfile.mkdtemp(prefix="host_test_")
    try:
        with open(os.path.join(workdir, f"{module_name}.py"), "w", encoding="utf-8") as f:
            f.write(source_code)
        with open(os.path.join(workdir, f"test_{module_name}.py"), "w", encoding="utf-8") as f:
            f.write(test_code)

        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)
        cmd = command or ["pytest", f"test_{module_name}.py", "-v", "--tb=short"]
        return subprocess.run(
            cmd, cwd=workdir, capture_output=True, text=True,
            timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return _CompletedProcess(args=command or [], returncode=1, stdout="", stderr="Timeout")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
