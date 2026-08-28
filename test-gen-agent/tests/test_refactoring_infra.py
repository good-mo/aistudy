"""重构基础设施测试：验证 Phase 0-6 的核心组件。"""

import os
import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("LLM_PROVIDER", "local")


# ════════════════════════════════════════════════════════════
# Phase 1: 统一数据库层
# ════════════════════════════════════════════════════════════

class TestDatabaseCore:
    """统一数据库连接管理测试。"""

    def test_get_conn(self):
        from app.core.database import Database, get_conn
        conn = Database.get_conn("testcases.db")
        assert conn is not None
        # 连接复用
        conn2 = Database.get_conn("testcases.db")
        assert conn is conn2

    def test_query_one(self):
        from app.core.database import query_one
        row = query_one("testcases.db", "SELECT COUNT(*) as cnt FROM test_cases")
        assert row is not None
        assert "cnt" in row

    def test_query_all(self):
        from app.core.database import query_all
        rows = query_all("testcases.db", "SELECT * FROM test_cases LIMIT 5")
        assert isinstance(rows, list)

    def test_transaction(self):
        from app.core.database import Database
        with Database.transaction("testcases.db") as conn:
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1


# ════════════════════════════════════════════════════════════
# Phase 2: 统一路由契约层
# ════════════════════════════════════════════════════════════

class TestRouterCore:
    """统一路由注册测试。"""

    def test_api_route(self):
        from app.core.router import api_route, build_api_router, route_count

        @api_route("/test/refactoring/api", methods=["GET"])
        async def _test_route():
            return {"ok": True}

        assert route_count() > 0

    def test_route_conflict_detection(self):
        from app.core.router import check_duplicate_paths
        conflicts = check_duplicate_paths([
            {"path": "/api/cases", "methods": ["GET"]},
            {"path": "/api/defects", "methods": ["POST"]},
        ])
        assert isinstance(conflicts, list)


# ════════════════════════════════════════════════════════════
# Phase 3: 分层架构
# ════════════════════════════════════════════════════════════

class TestLayeredArchitecture:
    """分层架构测试。"""

    def test_models_exist(self):
        from app.models.case import CaseCreate, CaseUpdate
        from app.models.defect import DefectCreate, DefectUpdate
        assert CaseCreate is not None
        assert CaseUpdate is not None
        assert DefectCreate is not None
        assert DefectUpdate is not None

    def test_repositories_exist(self):
        from app.repositories.base import BaseRepo
        from app.repositories.case_repo import CaseRepo
        from app.repositories.defect_repo import DefectRepo
        assert BaseRepo is not None
        assert CaseRepo is not None
        assert DefectRepo is not None

    def test_services_exist(self):
        from app.services.case_service import CaseService, case_service
        from app.services.defect_service import DefectService, defect_service
        assert CaseService is not None
        assert DefectService is not None
        assert case_service is not None
        assert defect_service is not None

    def test_routers_exist(self):
        from app.routers.cases import router as cases_router
        from app.routers.defects import router as defects_router
        from app.routers.apitest import router as apitest_router
        from app.routers.projects import router as projects_router
        from app.routers.environments import router as environments_router
        assert cases_router is not None
        assert defects_router is not None
        assert apitest_router is not None
        assert projects_router is not None
        assert environments_router is not None


# ════════════════════════════════════════════════════════════
# Phase 4: 统一异常与响应
# ════════════════════════════════════════════════════════════

class TestExceptionHandling:
    """统一异常处理测试。"""

    def test_exceptions_exist(self):
        from app.core.exceptions import (
            AppError, NotFoundError, AuthError, ValidationError,
            ConflictError, register_exception_handlers,
        )
        assert AppError is not None
        assert NotFoundError is not None
        assert AuthError is not None
        assert ValidationError is not None
        assert ConflictError is not None
        assert register_exception_handlers is not None

    def test_response_helpers(self):
        from app.core.response import ok, fail
        resp = ok({"test": True})
        assert resp.status_code == 200
        data = resp.body.decode()
        assert "code" in data
        assert "200" in data or "code" in data

        resp = fail("error", code=400)
        assert resp.status_code == 400
        data = resp.body.decode()
        assert "error" in data
        assert "400" in data or "code" in data


# ════════════════════════════════════════════════════════════
# Phase 0: 路由冲突检测
# ════════════════════════════════════════════════════════════

class TestRouteConflict:
    """路由冲突检测测试。"""

    def test_script_exists(self):
        import os
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts", "route_conflict_check.py",
        )
        assert os.path.exists(script_path)


# ════════════════════════════════════════════════════════════
# Phase 5: 前端 API 契约
# ════════════════════════════════════════════════════════════

class TestFrontendContract:
    """前端 API 契约测试。"""

    def test_contracts_file_exists(self):
        import os
        contract_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "frontend", "src", "api", "contracts.ts",
        )
        assert os.path.exists(contract_path)

    def test_contracts_content(self):
        import os
        contract_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "frontend", "src", "api", "contracts.ts",
        )
        with open(contract_path) as f:
            content = f.read()
        assert "case" in content
        assert "bug" in content
        assert "apiDefinition" in content
        assert "scenario" in content


# ════════════════════════════════════════════════════════════
# Phase 6: 数据库合并
# ════════════════════════════════════════════════════════════

class TestDatabaseMerge:
    """数据库合并测试。"""

    def test_merge_script_exists(self):
        import os
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts", "merge_databases.py",
        )
        assert os.path.exists(script_path)

    def test_db_path_helper(self):
        from app.db import db_path
        path = db_path("testcases.db")
        assert path.endswith("testcases.db")
        assert os.path.isabs(path)
