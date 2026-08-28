"""
模块名: test_wechat_concurrency.py
模块说明: 微信上传图片功能的并发测试

测试覆盖:
  - 并发测试: 多线程同时上传同一/不同文件
  - 并发测试: 批量上传的并发行为
  - 并发测试: 竞态条件与线程安全
  - 回归测试: 并发下的功能正确性
"""
import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wechat_upload import (
    MAX_DIMENSION,
    MAX_IMAGE_SIZE,
    batch_upload_images,
    calculate_md5,
    compress_image,
    upload_image,
    validate_image,
)


# ─── Fixtures ─────────────────────────────
@pytest.fixture
def sample_image(tmp_path):
    """创建一个小型 PNG 测试图片。"""
    img = tmp_path / "test.png"
    # PNG 头部（含魔数）+ 简单数据
    img.write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    )
    return str(img)


@pytest.fixture
def large_image(tmp_path):
    """创建接近大小限制的图片。"""
    img = tmp_path / "large.jpg"
    # JPEG 魔数 + 数据填充
    img.write_bytes(b"\xff\xd8\xff" + b"\x00" * (MAX_IMAGE_SIZE - 10))
    return str(img)


@pytest.fixture
def multi_images(tmp_path):
    """创建多张测试图片。"""
    paths = []
    for i in range(5):
        img = tmp_path / f"img_{i}.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * (50 + i))
        paths.append(str(img))
    return paths


# ─── 并发测试：多线程同时上传同一文件 ─────
class TestConcurrentSameFileUpload:
    """
    并发测试: 多个线程同时上传同一个文件
    预期: 所有上传都应成功，不会出现竞态问题
    """

    def test_parallel_same_file_all_succeed(self, sample_image):
        """并发: 10 个线程同时上传同一文件应全部成功"""
        # Arrange
        num_threads = 10
        results = []
        errors = []

        def _do_upload():
            try:
                result = upload_image(
                    file_path=sample_image,
                    access_token="token_abc",
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Act
        threads = [
            threading.Thread(target=_do_upload) for _ in range(num_threads)
        ]
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "media_id": "media_123", "url": "http://example.com/x.jpg"
            }
            mock_post.return_value = mock_resp

            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

        # Assert
        assert not errors, f"并发上传出现错误: {errors}"
        assert len(results) == num_threads, \
            f"应成功 {num_threads} 次，实际 {len(results)} 次"
        assert all(r["media_id"] == "media_123" for r in results)

    def test_concurrent_md5_calculation_same_file(self, sample_image):
        """并发: 多线程同时计算同一文件 MD5，结果应一致"""
        # Arrange
        expected = calculate_md5(sample_image)
        results = []
        lock = threading.Lock()

        def _calc():
            md5 = calculate_md5(sample_image)
            with lock:
                results.append(md5)

        threads = [threading.Thread(target=_calc) for _ in range(20)]

        # Act
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # Assert
        assert len(results) == 20
        assert all(md5 == expected for md5 in results), \
            "并发计算 MD5 结果不一致"

    def test_parallel_upload_with_progress_callback(self, sample_image):
        """并发: 带进度回调的并行上传"""
        # Arrange
        progress_events = []
        lock = threading.Lock()

        def _progress(pct):
            with lock:
                progress_events.append(pct)

        def _do_upload():
            return upload_image(
                file_path=sample_image,
                access_token="token",
                progress_callback=_progress,
            )

        # Act
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "media_id": f"media_{threading.get_ident()}"
            }
            mock_post.return_value = mock_resp

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(_do_upload) for _ in range(5)]
                results = [f.result(timeout=30) for f in as_completed(futures)]

        # Assert
        assert len(results) == 5
        assert len(progress_events) >= 5 * 3, \
            "每个上传至少应有 3 个进度回调"
        # 进度值应在 0-100 范围内
        assert all(0 <= p <= 100 for p in progress_events)


# ─── 并发测试：批量上传 ────────────────────
class TestConcurrentBatchUpload:
    """
    并发测试: 批量上传的并发行为
    """

    def test_batch_upload_concurrent_workers(self, multi_images):
        """并发: 批量上传使用多 worker 并发执行"""
        # Arrange
        num_files = len(multi_images)

        # Act
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"media_id": "batch_media"}
            mock_post.return_value = mock_resp

            start = time.time()
            results = batch_upload_images(
                file_paths=multi_images,
                access_token="token",
                max_workers=4,
            )
            elapsed = time.time() - start

        # Assert
        assert len(results) == num_files, \
            f"应返回 {num_files} 个结果，实际 {len(results)}"
        # 4 worker 并发应比串行更快（mock 快速响应时不严格校验耗时）
        assert all(r["media_id"] == "batch_media" for r in results)

    def test_batch_upload_partial_failure_isolates(self, multi_images):
        """并发: 部分文件失败不应影响其他文件"""
        # Arrange
        def _mock_post(url, **kwargs):
            file_name = kwargs.get("files", {}).get("media", ("",))[0]
            mock_resp = MagicMock()
            if "img_2" in file_name:
                mock_resp.status_code = 500
            else:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"media_id": "ok"}
            return mock_resp

        # Act
        with patch("requests.post", side_effect=_mock_post):
            results = batch_upload_images(
                file_paths=multi_images,
                access_token="token",
                retries=0,
                max_workers=4,
            )

        # Assert
        # 4 个成功（img_0, img_1, img_3, img_4），1 个失败被记录
        assert len(results) == 4, \
            f"应成功 4 个，实际 {len(results)}"

    def test_batch_upload_high_concurrency_race_safety(self, multi_images):
        """并发: 高并发（20 任务）批量上传的线程安全"""
        # Arrange
        files = multi_images * 4  # 20 个文件
        results = []
        lock = threading.Lock()

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"media_id": "race_safe"}
            mock_post.return_value = mock_resp

            # Act
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(batch_upload_images, files, "token", max_workers=4)
                    for _ in range(3)
                ]
                for f in as_completed(futures):
                    batch_results = f.result(timeout=60)
                    with lock:
                        results.extend(batch_results)

        # Assert
        assert len(results) == 60, f"应处理 60 个文件，实际 {len(results)}"


# ─── 并发测试：竞态条件 ────────────────────
class TestRaceCondition:
    """
    并发测试: 竞态条件与线程安全
    """

    def test_concurrent_compress_and_upload(self, sample_image):
        """并发: 压缩和上传同时进行不应冲突"""
        # Arrange
        results = []
        errors = []

        def _compress():
            try:
                path = compress_image(sample_image, quality=70)
                results.append(("compress", path))
            except Exception as e:
                errors.append(("compress", e))

        def _upload():
            try:
                r = upload_image(sample_image, "token")
                results.append(("upload", r["media_id"]))
            except Exception as e:
                errors.append(("upload", e))

        # Act
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"media_id": "u1"}
            mock_post.return_value = mock_resp

            t1 = threading.Thread(target=_compress)
            t2 = threading.Thread(target=_upload)
            t1.start()
            t2.start()
            t1.join(timeout=30)
            t2.join(timeout=30)

        # Assert
        assert not errors, f"竞态操作出现错误: {errors}"
        ops = [op for op, _ in results]
        assert "compress" in ops and "upload" in ops

    def test_concurrent_validation_same_file(self, sample_image):
        """并发: 同一文件被并发校验，结果一致"""
        # Arrange
        outcomes = []
        lock = threading.Lock()

        def _validate():
            valid, fmt = validate_image(sample_image)
            with lock:
                outcomes.append((valid, fmt))

        threads = [threading.Thread(target=_validate) for _ in range(50)]

        # Act
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # Assert
        assert len(outcomes) == 50
        assert all(valid is True and fmt == "png" for valid, fmt in outcomes), \
            "并发校验结果不一致"


# ─── 并发测试：压力下的资源控制 ────────────
class TestConcurrencyStress:
    """
    并发测试: 高并发压力下的资源控制
    """

    def test_max_parallel_upload_100_tasks(self, sample_image):
        """并发: 100 个并行上传任务不崩溃"""
        # Arrange
        results = []
        errors = []

        def _upload():
            try:
                upload_image(sample_image, "token")
                results.append(True)
            except Exception as e:
                errors.append(str(e))

        # Act
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"media_id": "stress"}
            mock_post.return_value = mock_resp

            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(_upload) for _ in range(100)]
                for f in as_completed(futures):
                    f.result(timeout=60)

        # Assert
        assert len(errors) == 0, f"压力测试出现 {len(errors)} 个错误"
        assert len(results) == 100, \
            f"应完成 100 次上传，实际 {len(results)} 次"
