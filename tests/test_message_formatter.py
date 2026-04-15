"""
测试消息格式化器
"""

import re

from core.message_formatter import MessageFormatter


TIMESTAMP_PATTERN = r"^时间: \d{4}-\d{2}-\d{2} \d{2}:\d{2}$"


class TestMessageFormatter:
    """测试消息格式化器"""

    def test_format_email_summary_includes_full_date(self):
        """测试邮件摘要包含完整日期时间"""
        message = MessageFormatter.format_email_summary({
            "new": 2,
            "paper": 1,
            "notice": 1,
        })

        lines = message.splitlines()
        assert lines[0] == "📬 邮件处理完成"
        assert re.match(TIMESTAMP_PATTERN, lines[1])

    def test_format_important_alert_includes_full_date(self):
        """测试重要提醒包含完整日期时间"""
        message = MessageFormatter.format_important_alert([
            {"_summary": "请今天内提交修回稿"},
        ])

        lines = message.splitlines()
        assert lines[0] == "⚠️ 重要邮件提醒"
        assert re.match(TIMESTAMP_PATTERN, lines[1])

    def test_format_new_emails_digest_includes_full_date(self):
        """测试新邮件摘要包含完整日期时间"""
        message = MessageFormatter.format_new_emails_digest([
            {
                "_stage1_category": "NOTICE",
                "_summary": "学院通知明天上午开会",
                "_suppress_notification": False,
            }
        ])

        lines = message.splitlines()
        assert lines[0] == "📬 新邮件 (1封)"
        assert re.match(TIMESTAMP_PATTERN, lines[1])

    def test_format_error_alert_includes_full_date(self):
        """测试错误提醒包含完整日期时间"""
        message = MessageFormatter.format_error_alert("timeout", "Telegram 发送")

        lines = message.splitlines()
        assert lines[0] == "❌ 邮件处理出错"
        assert re.match(TIMESTAMP_PATTERN, lines[1])
