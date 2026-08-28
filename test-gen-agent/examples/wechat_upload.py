"""
wechat_upload.py
模拟微信上传图片功能的 Python 模块。

包含图片格式/大小校验、尺寸解析、压缩、MD5 计算、上传（含重试）、批量上传。
外部依赖统一抽象，便于测试 Mock。
"""
import hashlib
import os
import time
from typing import Callable, Dict, List, Optional, Tuple

# ── 配置常量 ──────────────────────────────────────────────
MAX_IMAGE_SIZE = 10 * 1024 * 1024        # 10MB
MAX_DIMENSION = 5000                     # 最大边长
ALLOWED_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT = 30

# 常见图片魔数（文件头识别）
MAGIC_NUMBERS = {
    b"\x89PNG\r\n\x1a\n": ".png",
    b"\xff\xd8\xff": ".jpg",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"RIFF": ".webp",  # WEBP 以 RIFF....WEBP 开头
}

# 微信 API 错误码
WECHAT_ERROR_CODES = {
    -1: "系统繁忙",
    40001: "不合法的调用凭证",
    40009: "图片尺寸超限",
    40015: "不合法的素材类型",
    45001: "多媒体文件大小超过限制",
}


class ImageFormatError(Exception):
    """图片格式不支持或非法。"""
    pass


class ImageSizeError(Exception):
    """图片大小超过限制。"""
    pass


class DimensionError(Exception):
    """图片尺寸超出允许范围。"""
    pass


class UploadError(Exception):
    """上传失败。"""
    pass


class WeChatAPIError(Exception):
    """微信 API 返回错误。"""
    def __init__(self, code: int, message: str = ""):
        self.code = code
        self.message = message or WECHAT_ERROR_CODES.get(code, f"未知错误 {code}")
        super().__init__(f"微信API错误({code}): {self.message}")


def validate_image(file_path: str) -> Tuple[bool, str]:
    """
    校验图片格式、大小、魔数。

    Args:
        file_path: 图片文件路径

    Returns:
        (是否合法, 原因或格式名)

    Raises:
        FileNotFoundError: 文件不存在
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    file_size = os.path.getsize(file_path)
    if file_size > MAX_IMAGE_SIZE:
        raise ImageSizeError(f"图片超过 {MAX_IMAGE_SIZE//1024//1024}MB 限制")

    # 检查扩展名
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ALLOWED_FORMATS:
        raise ImageFormatError(f"不支持的图片格式: {ext}")

    # 检查魔数（文件头）
    with open(file_path, "rb") as f:
        header = f.read(12)

    detected_ext = None
    for magic, magic_ext in MAGIC_NUMBERS.items():
        if header.startswith(magic):
            detected_ext = magic_ext
            break

    if detected_ext is None:
        # 默认按扩展名接受（简化场景）
        return True, ext.lstrip(".")

    # 魔数与扩展名不匹配
    if detected_ext != ext:
        return False, f"文件内容与扩展名不匹配: 检测到{detected_ext}, 期望{ext}"

    return True, ext.lstrip(".")


def get_image_dimensions(file_path: str) -> Tuple[int, int]:
    """
    解析图片宽高。

    Args:
        file_path: 图片文件路径

    Returns:
        (width, height)

    Raises:
        FileNotFoundError: 文件不存在
        ImageFormatError: 不支持的图片格式
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise ImageFormatError(f"不支持的图片格式: {ext}")

    with open(file_path, "rb") as f:
        header = f.read(30)

    # 简化实现：根据头部字节推断尺寸
    if ext == ".png":
        if len(header) < 24:
            return (0, 0)
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        return width, height
    elif ext in (".jpg", ".jpeg"):
        # JPEG 尺寸解析（简化）
        i = 2
        while i < len(header) - 2:
            if header[i] != 0xFF:
                i += 1
                continue
            marker = header[i+1]
            if marker == 0xC0 or marker == 0xC2:
                height = int.from_bytes(header[i+5:i+7], "big")
                width = int.from_bytes(header[i+7:i+9], "big")
                return width, height
            length = int.from_bytes(header[i+2:i+4], "big")
            i += 2 + length
        return (0, 0)
    else:
        # GIF/WebP/BMP 简化：返回占位尺寸
        return (100, 100)


def validate_dimensions(width: int, height: int) -> bool:
    """
    校验图片尺寸是否在允许范围内。

    Args:
        width: 图片宽度
        height: 图片高度

    Returns:
        True 如果尺寸合法

    Raises:
        DimensionError: 尺寸超过允许范围
    """
    if width <= 0 or height <= 0:
        raise DimensionError(f"图片尺寸必须为正数: {width}x{height}")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise DimensionError(
            f"图片尺寸超过限制: {width}x{height} (最大 {MAX_DIMENSION}px)"
        )
    return True


def compress_image(
    file_path: str,
    quality: int = 80,
    target_width: Optional[int] = None,
) -> str:
    """
    压缩图片。

    Args:
        file_path: 源图片路径
        quality: 压缩质量 0-100
        target_width: 目标宽度（可选）

    Returns:
        压缩后图片路径

    Raises:
        FileNotFoundError: 文件不存在
        ImageFormatError: 格式不支持
        ValueError: 压缩质量无效
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if not 0 <= quality <= 100:
        raise ValueError(f"压缩质量必须在 0-100 之间: {quality}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise ImageFormatError(f"不支持的图片格式: {ext}")

    # 简化实现：生成压缩后文件
    dir_path = os.path.dirname(file_path) or "."
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    compressed_path = os.path.join(dir_path, f"{base_name}_compressed{ext}")

    # 模拟压缩过程
    with open(file_path, "rb") as src:
        data = src.read()

    with open(compressed_path, "wb") as dst:
        dst.write(data)

    return compressed_path


def calculate_md5(file_path: str) -> str:
    """
    计算文件的 MD5 值。

    Args:
        file_path: 文件路径

    Returns:
        MD5 哈希字符串

    Raises:
        FileNotFoundError: 文件不存在
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def upload_image(
    file_path: str,
    access_token: str,
    url: str = "https://api.weixin.qq.com/cgi-bin/material/add_material",
    retries: int = DEFAULT_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
    progress_callback: Optional[Callable[[int], None]] = None,
    compress: bool = False,
    compress_quality: int = 80,
) -> Dict[str, str]:
    """
    上传图片到微信素材库。

    Args:
        file_path: 图片文件路径
        access_token: 微信 access_token
        url: 上传接口 URL
        retries: 重试次数
        timeout: 超时时间（秒）
        progress_callback: 进度回调，参数为 0-100 整数
        compress: 是否压缩后再上传
        compress_quality: 压缩质量

    Returns:
        {"media_id": ..., "url": ..., "file_name": ...}

    Raises:
        FileNotFoundError: 文件不存在
        ImageFormatError: 格式不支持
        UploadError: 上传失败
        WeChatAPIError: 微信 API 错误
    """
    import requests

    # 校验图片
    valid, format_name = validate_image(file_path)
    if not valid:
        raise ImageFormatError(f"图片无效: {format_name}")

    if not access_token:
        raise ValueError("access_token 不能为空")
    if not url:
        raise ValueError("URL 不能为空")
    if retries < 0:
        raise ValueError("重试次数不能为负数")
    if timeout <= 0:
        raise ValueError("超时时间必须为正数")

    # 可选压缩
    actual_path = file_path
    if compress:
        actual_path = compress_image(file_path, quality=compress_quality)

    if progress_callback:
        progress_callback(30)

    # 计算文件 MD5
    md5 = calculate_md5(actual_path)
    file_name = os.path.basename(actual_path)
    file_size = os.path.getsize(actual_path)

    # 上传（带重试）
    attempt = 0
    while attempt <= retries:
        try:
            if progress_callback:
                progress_callback(50 + attempt * 10)

            with open(actual_path, "rb") as f:
                files = {"media": (file_name, f)}
                params = {"access_token": access_token, "type": "image"}
                resp = requests.post(
                    url, params=params, files=files, timeout=timeout
                )

            if progress_callback:
                progress_callback(90)

            if resp.status_code == 200:
                data = resp.json()
                # 微信返回格式: {"media_id": "...", "url": "..."}
                if "media_id" not in data:
                    if "errcode" in data:
                        code = data["errcode"]
                        if code in WECHAT_ERROR_CODES:
                            raise WeChatAPIError(code)
                    raise UploadError(f"响应缺少 media_id: {data}")

                if progress_callback:
                    progress_callback(100)

                return {
                    "media_id": data["media_id"],
                    "url": data.get("url", ""),
                    "file_name": file_name,
                }
            elif resp.status_code == 401:
                raise UploadError("认证失败 (401)")
            elif resp.status_code == 500:
                if attempt >= retries:
                    raise UploadError("服务器错误 (500)，重试已耗尽")
                time.sleep(2 ** attempt)  # 指数退避
            else:
                raise UploadError(f"HTTP 错误: {resp.status_code}")

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            if attempt >= retries:
                raise UploadError(f"网络错误，重试已耗尽: {e}")
            time.sleep(2 ** attempt)  # 指数退避

        attempt += 1

    raise UploadError("上传失败（未知原因）")


def batch_upload_images(
    file_paths: List[str],
    access_token: str,
    url: str = "https://api.weixin.qq.com/cgi-bin/material/add_material",
    retries: int = DEFAULT_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
    max_workers: int = 4,
) -> List[Dict[str, str]]:
    """
    批量上传多张图片。

    Args:
        file_paths: 图片文件路径列表
        access_token: 微信 access_token
        url: 上传接口 URL
        retries: 重试次数
        timeout: 超时时间
        max_workers: 并发 worker 数

    Returns:
        上传结果列表 [{"media_id": ...}, ...]

    Raises:
        ValueError: 文件列表为空
    """
    import concurrent.futures

    if not file_paths:
        raise ValueError("文件列表不能为空")

    results: List[Dict[str, str]] = []
    errors: List[Exception] = []

    def _upload_one(path: str) -> Dict[str, str]:
        return upload_image(
            file_path=path,
            access_token=access_token,
            url=url,
            retries=retries,
            timeout=timeout,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(_upload_one, path): path
            for path in file_paths
        }
        for future in concurrent.futures.as_completed(future_to_path):
            path = future_to_path[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                errors.append(e)

    return results
