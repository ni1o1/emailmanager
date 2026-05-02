"""
统一通知管理器
"""

from datetime import date, datetime
from typing import Dict, List

from config.settings import (
    FEISHU_ENABLED,
    FEISHU_NOTIFY_LEVEL,
    FEISHU_QUIET_HOURS,
)
from core.logger import get_logger
from core.message_formatter import MessageFormatter
from core.feishu import FeishuClient

logger = get_logger(__name__)


class NotificationManager:
    """飞书通知入口"""

    def __init__(self, formatter: MessageFormatter = None):
        self.formatter = formatter or MessageFormatter()
        self.client = FeishuClient()
        self.enabled = FEISHU_ENABLED
        self.notify_level = FEISHU_NOTIFY_LEVEL
        self.quiet_hours = FEISHU_QUIET_HOURS

    def has_enabled_backends(self) -> bool:
        """是否启用了飞书通知"""
        return self.enabled

    @staticmethod
    def _is_quiet_hours(quiet_hours: str) -> bool:
        """检查是否在静默时段"""
        if not quiet_hours:
            return False

        try:
            start_str, end_str = quiet_hours.split("-")
            now = datetime.now().time()
            start = datetime.strptime(start_str, "%H:%M").time()
            end = datetime.strptime(end_str, "%H:%M").time()

            if start <= end:
                return start <= now <= end
            return now >= start or now <= end
        except Exception:
            return False

    def _send(self, message: str) -> bool:
        if not self.enabled or not message:
            return False

        result = self.client.send(message)
        if result.success:
            logger.info("📱 已发送飞书通知")
            return True

        logger.warning(f"📱 飞书发送失败: {result.error}")
        return False

    def send_text(self, message: str, respect_quiet_hours: bool = False) -> int:
        """发送纯文本到飞书"""
        if not self.enabled:
            return 0
        if respect_quiet_hours and self._is_quiet_hours(self.quiet_hours):
            return 0
        return 1 if self._send(message) else 0

    def send_startup_notification(self, check_interval_seconds: int, daily_report_time: str) -> int:
        """发送启动通知"""
        if not self.has_enabled_backends():
            return 0

        now = datetime.now()
        interval_minutes = max(check_interval_seconds // 60, 1)
        message = (
            f"📧 邮件监控已启动\n"
            f"{now.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"每 {interval_minutes} 分钟检查新邮件\n"
            f"每天 {daily_report_time} 发送统计简报"
        )
        return self.send_text(message, respect_quiet_hours=False)

    def send_daily_report(self, report_date: date, stats: Dict) -> int:
        """发送每日统计简报"""
        if not self.has_enabled_backends():
            return 0

        lines = [
            "📊 邮件日报",
            report_date.strftime("%Y-%m-%d"),
            "",
            f"今日处理: {stats.get('total', 0)} 封",
        ]

        by_stage1 = stats.get("by_stage1", {})
        if by_stage1:
            lines.append("")
            category_names = {
                "TRASH": "🗑️ 垃圾",
                "PAPER": "📄 论文",
                "REVIEW": "📝 审稿",
                "BILLING": "💳 账单",
                "NOTICE": "📢 通知",
                "EXAM": "📋 考试",
                "PERSONAL": "👤 个人",
            }
            for key, count in by_stage1.items():
                if count > 0:
                    lines.append(f"{category_names.get(key, key)}: {count}")

        return self.send_text("\n".join(lines), respect_quiet_hours=False)

    def send_processing_notification(
        self,
        stats: Dict,
        important_emails: List[Dict] = None,
        all_new_emails: List[Dict] = None,
    ):
        """按各后端自己的策略发送处理结果通知"""
        important_emails = important_emails or []
        all_new_emails = all_new_emails or []

        if stats.get("new", 0) == 0:
            return

        if not self.enabled or self._is_quiet_hours(self.quiet_hours):
            return
        if self.notify_level == "important" and not important_emails:
            return

        if all_new_emails:
            message = self.formatter.format_new_emails_digest(all_new_emails)
        elif self.notify_level == "important" and important_emails:
            message = self.formatter.format_important_alert(important_emails)
        else:
            message = self.formatter.format_email_summary(stats)

        self._send(message)

    def send_error_alert(self, error: str, context: str = ""):
        """发送错误提醒，受静默时段控制"""
        if not self.enabled or self._is_quiet_hours(self.quiet_hours):
            return

        message = self.formatter.format_error_alert(error, context)
        success = self.client.send_silent(message)
        if success:
            logger.info("📱 已发送飞书错误提醒")
