"""
邮件监控器
定时检查新邮件并处理
使用LLM两阶段分类
"""

import time
from datetime import datetime, date
from typing import List, Dict

from config.settings import (
    CHECK_INTERVAL,
    MAX_EMAILS_PER_BATCH,
    DAILY_REPORT_TIME,
    MARK_TRASH_AS_READ,
    MAX_EMAIL_AGE_DAYS,
)
from core.email_client import EmailClient
from core.state import StateManager
from core.message_formatter import MessageFormatter
from core.notification_manager import NotificationManager
from core.logger import get_logger, LogContext
from core.metrics import metrics
from processors.classifier import EmailClassifier
from processors.academic import AcademicProcessor
from processors.email_processor import (
    group_emails_by_category,
    print_classification_stats,
)

logger = get_logger(__name__)

# 解析每日简报时间
def _parse_daily_report_time():
    try:
        parts = DAILY_REPORT_TIME.split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 14, 0  # 默认 14:00

DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE = _parse_daily_report_time()


class EmailWatcher:
    """邮件监控器"""

    def __init__(self):
        self.email_client = EmailClient()
        self.state = StateManager()
        self.classifier = EmailClassifier()
        self.academic_processor = AcademicProcessor()

        self.formatter = MessageFormatter()
        self.notifier = NotificationManager(self.formatter)

        # 记录上次发送每日简报的日期
        self._last_daily_report_date = None

    @staticmethod
    def _is_zero_amount_bill(summary: str, subject: str) -> bool:
        """检测是否为0元账单"""
        import re
        text = summary + " " + subject
        # 匹配 ¥0、¥0.00、0元、0.00元、$0、$0.00 等
        zero_patterns = [
            r'[¥￥]\s*0(\.0+)?(?!\d)',
            r'\$\s*0(\.0+)?(?!\d)',
            r'0(\.0+)?\s*元',
            r'金额[为是：:]\s*0',
        ]
        for pattern in zero_patterns:
            if re.search(pattern, text):
                return True
        return False

    def _send_startup_notification(self, check_interval_seconds: int):
        """发送启动通知"""
        sent_count = self.notifier.send_startup_notification(
            check_interval_seconds=check_interval_seconds,
            daily_report_time=DAILY_REPORT_TIME,
        )
        if sent_count == 0 and not self.notifier.has_enabled_backends():
            logger.info("未启用任何通知后端，跳过启动通知")

    def _should_send_daily_report(self) -> bool:
        """检查是否应该发送每日简报"""
        now = datetime.now()
        today = date.today()

        # 检查是否已经发送过今天的简报
        if self._last_daily_report_date == today:
            return False

        # 检查是否到达发送时间（14:00）
        if now.hour == DAILY_REPORT_HOUR and now.minute < DAILY_REPORT_MINUTE + 10:
            # 在14:00-14:10之间发送
            return True

        return False

    def _send_daily_report(self):
        """发送每日统计简报"""
        today = date.today()
        stats = self.state.get_stats(days=1)
        sent_count = self.notifier.send_daily_report(today, stats)
        if sent_count > 0:
            self._last_daily_report_date = today
        elif self.notifier.has_enabled_backends():
            logger.warning("已启用通知后端，但每日简报发送失败")
        else:
            logger.warning("未启用任何通知后端，每日简报未发送")

    def _send_notification(self, stats: Dict, important_emails: List[Dict] = None, all_new_emails: List[Dict] = None):
        """发送处理完成通知"""
        self.notifier.send_processing_notification(
            stats,
            important_emails=important_emails,
            all_new_emails=all_new_emails,
        )

    def check_and_process(self) -> Dict:
        """
        检查并处理新邮件

        Returns:
            处理结果统计
        """
        logger.info(f"{'='*50}")
        logger.info(f"检查新邮件 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info('='*50)

        # 1. 获取未读邮件（限制最大回溯天数，防止数据库丢失后重复处理大量邮件）
        logger.info(f"获取未读邮件（最近 {MAX_EMAIL_AGE_DAYS} 天）...")
        all_unread = self.email_client.fetch_unread_emails(
            limit=MAX_EMAILS_PER_BATCH,
            max_age_days=MAX_EMAIL_AGE_DAYS
        )
        logger.info(f"找到 {len(all_unread)} 封未读邮件")

        if not all_unread:
            logger.info("没有新邮件")
            return {"total": 0, "new": 0}

        # 2. 过滤已处理的
        processed_ids = self.state.get_processed_ids()
        new_emails = [e for e in all_unread if e.get("message_id") not in processed_ids]
        logger.info(f"其中 {len(new_emails)} 封是新邮件")

        if not new_emails:
            logger.info("没有需要处理的新邮件")
            return {"total": len(all_unread), "new": 0}

        # 3. Stage 1: LLM分析标题分类
        logger.info("Stage 1: LLM分析邮件标题...")
        self.classifier.stage1_classify_batch(new_emails)

        # 按分类分组
        groups = group_emails_by_category(new_emails)
        trash_emails = groups["TRASH"]
        paper_emails = groups["PAPER"]
        review_emails = groups["REVIEW"]
        billing_emails = groups["BILLING"]
        notice_emails = groups["NOTICE"]
        exam_emails = groups["EXAM"]
        personal_emails = groups["PERSONAL"]
        unknown_emails = groups["UNKNOWN"]

        print_classification_stats(groups)

        # 记录垃圾邮件
        for email in trash_emails:
            metrics.record_email("TRASH")
            should_mark_read = MARK_TRASH_AS_READ
            self.state.mark_processed(
                message_id=email.get("message_id"),
                account=email.get("account"),
                subject=email.get("subject"),
                stage1_result="TRASH",
                marked_read=should_mark_read
            )
            if should_mark_read:
                self.email_client.mark_as_read(email["account"], email["email_id"])

        # 4. 处理需要Stage 2分析的邮件（论文 + 审稿 + unknown）
        need_stage2 = paper_emails + review_emails + unknown_emails
        if need_stage2:
            logger.info("加载邮件内容...")
            for email in need_stage2:
                self.email_client.load_email_body(email)

            logger.info("Stage 2: LLM分析邮件内容...")
            analysis = self.classifier.stage2_analyze_content(need_stage2)

            items = analysis.get("items", [])
            classifications = analysis.get("classifications", [])

            logger.info(f"识别到 {len(items)} 个学术项目")

            class_map = {c["id"]: c for c in classifications}
            trash_count = sum(1 for c in classifications if "Trash" in c.get("category", ""))
            if trash_count:
                logger.info(f"LLM判定垃圾: {trash_count} 封")

            if items:
                result = self.academic_processor.process(items)
                logger.info(f"论文: {result['papers_synced']} 条, 审稿: {result['reviews_synced']} 条")

            for i, email in enumerate(need_stage2, 1):
                cls_info = class_map.get(i, {})
                final_category = cls_info.get("category", email.get("_final_category", "Unknown"))
                item_category = None
                for item in items:
                    if i in item.get("source_emails", []):
                        item_category = item.get("category")
                        if not email.get("_venue"):
                            email["_venue"] = item.get("venue", "")
                        break

                self.state.mark_processed(
                    message_id=email.get("message_id"),
                    account=email.get("account"),
                    subject=email.get("subject"),
                    stage1_result=email.get("_stage1_category", "UNKNOWN"),
                    stage2_category=item_category or final_category,
                    synced=False,
                    marked_read=False
                )

        # 5. 处理账单邮件（Stage 2 分析获取摘要和金额）
        if billing_emails:
            logger.info("分析账单邮件...")
            for email in billing_emails:
                self.email_client.load_email_body(email)

            self.classifier.stage2_analyze_content(billing_emails)

            for email in billing_emails:
                # 0 元账单不推送
                summary = email.get("_summary", "")
                if self._is_zero_amount_bill(summary, email.get("subject", "")):
                    email["_suppress_notification"] = True
                    logger.info(f"跳过0元账单: {email.get('subject', '')[:50]}")

                self.state.mark_processed(
                    message_id=email.get("message_id"),
                    account=email.get("account"),
                    subject=email.get("subject"),
                    stage1_result="BILLING",
                    synced=False,
                    marked_read=False
                )

        # 6. 处理通知公告邮件（Stage 2 分析重要程度，只推送重要的）
        if notice_emails:
            logger.info("分析通知邮件...")
            for email in notice_emails:
                self.email_client.load_email_body(email)

            self.classifier.stage2_analyze_content(notice_emails)

            for email in notice_emails:
                self.state.mark_processed(
                    message_id=email.get("message_id"),
                    account=email.get("account"),
                    subject=email.get("subject"),
                    stage1_result="NOTICE",
                    synced=False,
                    marked_read=False
                )

        # 7. 处理考试相关邮件（用Stage 2分析）
        if exam_emails:
            logger.info("处理考试邮件...")
            for email in exam_emails:
                self.email_client.load_email_body(email)

            self.classifier.stage2_analyze_content(exam_emails)

            for email in exam_emails:
                if not email.get("_importance"):
                    email["_importance"] = 5
                if email.get("_needs_action") is None:
                    email["_needs_action"] = True

                self.state.mark_processed(
                    message_id=email.get("message_id"),
                    account=email.get("account"),
                    subject=email.get("subject"),
                    stage1_result="EXAM",
                    synced=False,
                    marked_read=False
                )

        # 8. 处理个人邮件（用Stage 2分析）
        if personal_emails:
            logger.info("处理个人邮件...")
            for email in personal_emails:
                self.email_client.load_email_body(email)

            self.classifier.stage2_analyze_content(personal_emails)

            for email in personal_emails:
                self.state.mark_processed(
                    message_id=email.get("message_id"),
                    account=email.get("account"),
                    subject=email.get("subject"),
                    stage1_result="PERSONAL",
                    synced=False,
                    marked_read=False
                )

        # NOTICE 类邮件：只有 importance >= 4 才推送，其余从通知列表中排除
        for email in notice_emails:
            importance = email.get("_importance", 2)
            if importance < 4:
                email["_suppress_notification"] = True

        # 收集重要邮件（用于通知）
        important_emails = []
        for email in new_emails:
            importance = email.get("_importance", 2)
            needs_action = email.get("_needs_action", False)
            if importance >= 4 or needs_action:
                important_emails.append(email)

        # 构建统计结果
        stats = {
            "total": len(all_unread),
            "new": len(new_emails),
            "trash": len(trash_emails),
            "paper": len(paper_emails),
            "review": len(review_emails),
            "billing": len(billing_emails),
            "notice": len(notice_emails),
            "exam": len(exam_emails),
            "personal": len(personal_emails),
            "unknown": len(unknown_emails),
        }

        # 发送飞书通知（传入所有新邮件以显示摘要）
        self._send_notification(stats, important_emails, new_emails)

        logger.info(f"处理完成: 新邮件 {len(new_emails)} 封, 垃圾 {len(trash_emails)} 封")

        return stats

    def run_forever(self, interval: int = None):
        """
        持续运行，定时检查邮件

        Args:
            interval: 检查间隔（秒），默认使用配置
        """
        interval = interval or CHECK_INTERVAL
        logger.info("邮件监控已启动")
        logger.info(f"检查间隔: {interval}秒 ({interval//60}分钟)")
        logger.info(f"每日简报: {DAILY_REPORT_HOUR}:{DAILY_REPORT_MINUTE:02d}")
        logger.info("按 Ctrl+C 停止")

        # 发送启动通知
        self._send_startup_notification(interval)

        try:
            while True:
                try:
                    # 检查是否需要发送每日简报
                    if self._should_send_daily_report():
                        logger.info("发送每日简报...")
                        self._send_daily_report()

                    self.check_and_process()
                except Exception as e:
                    logger.error(f"处理出错: {e}", exc_info=True)
                    self.notifier.send_error_alert(str(e), "邮件处理")

                logger.debug(f"下次检查: {interval}秒后...")
                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("监控已停止")
            # 输出性能指标摘要
            metrics.log_summary()

    def run_once(self):
        """运行一次检查"""
        result = self.check_and_process()
        # 输出性能指标摘要
        logger.debug(metrics.summary())
        return result
