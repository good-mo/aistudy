# app/adapters/domains/__init__.py
"""业务域拆分路由（Phase 3 重构）。

将 app/adapters/ 下的大文件按业务域拆分，
每个领域文件对应一个 FastAPI APIRouter。
"""
from app.adapters.domains.functional_cases import router as functional_cases_router
from app.adapters.domains.defects import router as defects_adapter_router
from app.adapters.domains.api_testing import router as api_testing_adapter_router
from app.adapters.domains.case_reviews import router as case_reviews_router
from app.adapters.domains.project import router as project_adapter_router
from app.adapters.domains.system import router as system_adapter_router
from app.adapters.domains.reports import router as reports_adapter_router
from app.adapters.domains.debug import router as debug_adapter_router
from app.adapters.domains.ai_config import router as ai_config_router
from app.adapters.domains.attachment import router as attachment_router
from app.adapters.domains.integrations import router as integrations_router
from app.adapters.domains.notifications import router as notifications_router
from app.adapters.domains.plugins import router as plugins_router
from app.adapters.domains.test_resources import router as test_resources_router
from app.adapters.domains.websocket import router as websocket_adapter_router
from app.adapters.domains.auth import router as auth_adapter_router
from app.adapters.domains.platform import router as platform_router
from app.adapters.domains.test import router as test_router
from app.adapters.domains.other import router as other_router

__all__ = [
    "functional_cases_router",
    "defects_adapter_router",
    "api_testing_adapter_router",
    "case_reviews_router",
    "project_adapter_router",
    "system_adapter_router",
    "reports_adapter_router",
    "debug_adapter_router",
    "ai_config_router",
    "attachment_router",
    "integrations_router",
    "notifications_router",
    "plugins_router",
    "test_resources_router",
    "websocket_adapter_router",
    "auth_adapter_router",
    "platform_router",
    "test_router",
    "other_router",
]
