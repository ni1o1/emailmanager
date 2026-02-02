"""
消息格式化器
将邮件处理结果格式化为适合 iMessage 的摘要
"""

from typing import Dict, List
from datetime import datetime


class MessageFormatter:
    """消息格式化器"""

    @staticmethod
    def format_email_summary(stats: Dict) -> str:
        """
        格式化邮件处理摘要

        Args:
            stats: 处理统计信息，来自 watcher.check_and_process() 返回值

        Returns:
            格式化的消息文本
        """
        if stats.get("new", 0) == 0:
            return ""  # 没有新邮件，不发送通知

        lines = []
        lines.append("📬 邮件处理完成")
        lines.append(f"时间: {datetime.now().strftime('%H:%M')}")
        lines.append("")

        # 统计概要
        new_count = stats.get("new", 0)
        lines.append(f"📥 新邮件: {new_count} 封")

        # 分类明细（只显示有数据的类别）
        categories = [
            ("paper", "📄 论文"),
            ("review", "📝 审稿"),
            ("billing", "💳 账单"),
            ("notice", "📢 通知"),
            ("exam", "📋 考试"),
            ("personal", "👤 个人"),
            ("trash", "🗑️ 垃圾"),
        ]

        details = []
        for key, label in categories:
            count = stats.get(key, 0)
            if count > 0:
                details.append(f"{label}: {count}")

        if details:
            lines.append(" | ".join(details))

        return "\n".join(lines)

    @staticmethod
    def format_important_alert(emails: List[Dict]) -> str:
        """
        格式化重要邮件提醒

        Args:
            emails: 重要邮件列表（importance >= 4 或 needs_action=True）

        Returns:
            格式化的消息文本
        """
        if not emails:
            return ""

        lines = []
        lines.append("⚠️ 重要邮件提醒")
        lines.append("")

        for email in emails[:5]:  # 最多显示5封
            subject = (email.get("subject", "无标题"))[:30]
            summary = email.get("_summary", "")[:15]

            if summary:
                lines.append(f"• {subject}")
                lines.append(f"  {summary}")
            else:
                lines.append(f"• {subject}")

        if len(emails) > 5:
            lines.append(f"...还有 {len(emails) - 5} 封")

        return "\n".join(lines)

    @staticmethod
    def format_new_emails_digest(emails: List[Dict]) -> str:
        """
        格式化新邮件摘要通知
        每封非垃圾邮件都显示其提炼的摘要

        Args:
            emails: 新处理的邮件列表（已包含 _summary, _stage1_category 等字段）

        Returns:
            格式化的消息文本
        """
        if not emails:
            return ""

        # 过滤掉垃圾邮件
        valid_emails = [e for e in emails if e.get("_stage1_category") != "TRASH"]

        if not valid_emails:
            return ""

        lines = []
        lines.append(f"📬 新邮件 ({len(valid_emails)}封)")
        lines.append(f"{datetime.now().strftime('%H:%M')}")
        lines.append("")

        # 分类图标映射
        category_icons = {
            "PAPER": "📄",
            "REVIEW": "📝",
            "BILLING": "💳",
            "NOTICE": "📢",
            "EXAM": "📋",
            "PERSONAL": "👤",
            "UNKNOWN": "📧",
        }

        for email in valid_emails[:10]:  # 最多显示10封
            category = email.get("_stage1_category", "UNKNOWN")
            icon = category_icons.get(category, "📧")

            # 获取摘要，如果没有则用标题的前20字
            summary = email.get("_summary", "")
            if not summary:
                summary = (email.get("subject", "无标题"))[:20]

            # 重要程度标记
            importance = email.get("_importance", 2)
            needs_action = email.get("_needs_action", False)

            urgent = ""
            if importance >= 4 or needs_action:
                urgent = "⚡"

            lines.append(f"{icon}{urgent} {summary}")

        if len(valid_emails) > 10:
            lines.append(f"...还有 {len(valid_emails) - 10} 封")

        return "\n".join(lines)

    @staticmethod
    def format_error_alert(error: str, context: str = "") -> str:
        """
        格式化错误提醒

        Args:
            error: 错误信息
            context: 上下文说明

        Returns:
            格式化的消息文本
        """
        lines = []
        lines.append("❌ 邮件处理出错")

        if context:
            lines.append(f"环节: {context}")

        # 截断过长的错误信息
        error_short = error[:100] + "..." if len(error) > 100 else error
        lines.append(f"错误: {error_short}")

        return "\n".join(lines)
