"""桌面通知模块。"""

from common.logging_utils import get_logger

logger = get_logger(__name__)

try:
    from plyer import notification
    NOTIFICATION_AVAILABLE = True
except ImportError:  # pragma: no cover
    NOTIFICATION_AVAILABLE = False


class Notifier:
    """桌面通知器，依赖 plyer（可选）。"""

    def __init__(self, app_name: str = "A股盯盘助手"):
        self.app_name = app_name
        self._notify_error_logged = False

    @property
    def available(self) -> bool:
        return NOTIFICATION_AVAILABLE

    def notify(self, title: str, message: str):
        """发送桌面通知，失败静默处理避免刷屏。"""
        if not NOTIFICATION_AVAILABLE:
            return
        try:
            notification.notify(
                title=title,
                message=message,
                app_name=self.app_name,
                timeout=10,
            )
        except FileNotFoundError:
            # gdbus 或 notify-send 未安装，静默跳过
            pass
        except Exception:  # noqa: BLE001
            if not self._notify_error_logged:
                logger.warning("发送桌面通知失败（后续静默）")
                print("发送通知失败")
                self._notify_error_logged = True
