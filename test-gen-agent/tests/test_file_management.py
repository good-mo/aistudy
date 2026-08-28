"""文件管理模块单元测试。"""

import os
import shutil
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    c = TestClient(app)
    # 登录获取认证令牌
    r = c.post("/login", json={"username": "admin", "password": "admin123"})
    if r.status_code == 200:
        session = r.json()["data"]
        c.headers.update({
            "X-AUTH-TOKEN": session["sessionId"],
            "CSRF-TOKEN": session["csrfToken"],
        })
    return c


@pytest.fixture
def uploads_dir():
    """清理上传目录。"""
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
    if os.path.exists(upload_dir):
        for f in os.listdir(upload_dir):
            os.remove(os.path.join(upload_dir, f))
    yield upload_dir


class TestFileManagement:
    """文件管理测试。"""

    def test_file_page_empty(self, client, uploads_dir):
        """空文件列表。"""
        r = client.post("/project/file/page", json={})
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["total"] == 0

    def test_file_upload(self, client, uploads_dir):
        """上传文件。"""
        r = client.post("/project/file/upload", files={
            "file": ("test.txt", b"Hello World", "text/plain"),
        })
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "test.txt"
        assert data["data"]["size"] == 11

    def test_file_page_after_upload(self, client, uploads_dir):
        """上传后文件列表。"""
        client.post("/project/file/upload", files={
            "file": ("test.txt", b"Hello World", "text/plain"),
        })
        r = client.post("/project/file/page", json={})
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["total"] == 1
        assert data["data"]["list"][0]["name"] == "test.txt"

    def test_file_download(self, client, uploads_dir):
        """下载文件。"""
        r = client.post("/project/file/upload", files={
            "file": ("test.txt", b"Hello World", "text/plain"),
        })
        file_id = r.json()["data"]["id"]
        r = client.get(f"/project/file/download/{file_id}")
        assert r.status_code == 200
        assert r.content == b"Hello World"

    def test_file_get_detail(self, client, uploads_dir):
        """获取文件详情。"""
        r = client.post("/project/file/upload", files={
            "file": ("test.txt", b"Hello World", "text/plain"),
        })
        file_id = r.json()["data"]["id"]
        r = client.get(f"/project/file/get/{file_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "test.txt"

    def test_file_delete(self, client, uploads_dir):
        """删除文件。"""
        r = client.post("/project/file/upload", files={
            "file": ("test.txt", b"Hello World", "text/plain"),
        })
        file_id = r.json()["data"]["id"]
        r = client.post("/project/file/delete", json={"id": file_id})
        assert r.status_code == 200
        assert r.json()["code"] == 200
        # 验证已删除
        r = client.post("/project/file/page", json={})
        assert r.json()["data"]["total"] == 0

    def test_file_types(self, client):
        """获取文件类型。"""
        r = client.post("/project/file/type")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert len(data["data"]) > 0

    def test_file_module_tree(self, client):
        """获取模块树。"""
        r = client.get("/project/file-module/tree")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert len(data["data"]) >= 1


class TestAttachment:
    """附件管理测试。"""

    def test_attachment_page(self, client, uploads_dir):
        """附件分页。"""
        r = client.post("/attachment/page", json={})
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200

    def test_attachment_upload(self, client, uploads_dir):
        """上传附件。"""
        r = client.post("/attachment/upload", files={
            "file": ("attach.txt", b"Attachment Content", "text/plain"),
        })
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "attach.txt"

    def test_bug_attachment_upload(self, client, uploads_dir):
        """上传缺陷附件。"""
        r = client.post("/bug/attachment/upload", files={
            "file": ("bug.txt", b"Bug Report", "text/plain"),
        })
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "bug.txt"

    def test_bug_attachment_md_upload(self, client, uploads_dir):
        """富文本编辑器上传。"""
        r = client.post("/bug/attachment/upload/md/file", files={
            "file": ("image.png", b"fake-image", "image/png"),
        })
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert "url" in data["data"]
