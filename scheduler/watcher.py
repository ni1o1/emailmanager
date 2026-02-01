"""
邮件监控器
定时检查新邮件并处理
使用LLM两阶段分类
"""

import time
from datetime import datetime
from typing import List, Dict

from config.settings import CHECK_INTERVAL, MAX_EMAILS_PER_BATCH
from core.email_client import EmailClient
from core.notion_client import NotionClient
from core.state import StateManager
from core.billing_db import BillingDB
from processors.classifier import EmailClassifier
from processors.academic import AcademicProcessor
from processors.billing import BillingProcessor


class EmailWatcher:
    """邮件监控器"""

    def __init__(self):
        self.email_client = EmailClient()
        self.notion = NotionClient()
        self.state = StateManager()
        self.billing_db = BillingDB()
        self.classifier = EmailClassifier()
        self.academic_processor = AcademicProcessor(self.notion)
        self.billing_processor = BillingProcessor(self.billing_db, self.notion)

    def check_and_process(self) -> Dict:
        """
        检查并处理新邮件

        Returns:
            处理结果统计
        """
        print(f"\n{'='*50}")
        print(f"📬 检查新邮件 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print('='*50)

        # 1. 获取未读邮件
        print("\n📥 获取未读邮件...")
        all_unread = self.email_client.fetch_unread_emails(limit=MAX_EMAILS_PER_BATCH)
        print(f"   找到 {len(all_unread)} 封未读邮件")

        if not all_unread:
            print("   ✓ 没有新邮件")
            return {"total": 0, "new": 0}

        # 2. 过滤已处理的
        processed_ids = self.state.get_processed_ids()
        new_emails = [e for e in all_unread if e.get("message_id") not in processed_ids]
        print(f"   其中 {len(new_emails)} 封是新邮件")

        if not new_emails:
            print("   ✓ 没有需要处理的新邮件")
            return {"total": len(all_unread), "new": 0}

        # 3. Stage 1: LLM分析标题分类
        print(f"\n🤖 Stage 1: LLM分析邮件标题...")
        self.classifier.stage1_classify_batch(new_emails)

        # 按分类分组
        trash_emails = []
        academic_emails = []
        billing_emails = []
        notice_emails = []
        personal_emails = []
        unknown_emails = []

        for email in new_emails:
            category = email.get("_stage1_category", "UNKNOWN")
            if category == "TRASH":
                trash_emails.append(email)
            elif category == "ACADEMIC":
                academic_emails.append(email)
            elif category == "BILLING":
                billing_emails.append(email)
            elif category in ["NOTICE", "IMPORTANT"]:
                notice_emails.append(email)
            elif category == "PERSONAL":
                personal_emails.append(email)
            else:
                unknown_emails.append(email)

        print(f"   垃圾邮件: {len(trash_emails)} 封")
        print(f"   学术邮件: {len(academic_emails)} 封")
        print(f"   账单邮件: {len(billing_emails)} 封")
        print(f"   通知公告: {len(notice_emails)} 封")
        print(f"   个人邮件: {len(personal_emails)} 封")
        print(f"   待分析: {len(unknown_emails)} 封")

        # 记录垃圾邮件（不同步到Notion）
        for email in trash_emails:
            self.state.mark_processed(
                message_id=email.get("message_id"),
                account=email.get("account"),
                subject=email.get("subject"),
                stage1_result="TRASH",
                marked_read=True
            )
            self.email_client.mark_as_read(email["account"], email["email_id"])

        synced_to_emails_db = 0

        # 4. 处理需要Stage 2分析的邮件（学术 + unknown）
        need_stage2 = academic_emails + unknown_emails
        if need_stage2:
            # 加载邮件正文
            print(f"\n📖 加载邮件内容...")
            for email in need_stage2:
                self.email_client.load_email_body(email)

            print(f"\n🤖 Stage 2: LLM分析邮件内容...")
            analysis = self.classifier.stage2_analyze_content(need_stage2)

            items = analysis.get("items", [])
            classifications = analysis.get("classifications", [])

            print(f"   识别到 {len(items)} 个学术项目")

            # 统计分类结果
            class_map = {c["id"]: c["category"] for c in classifications}
            trash_count = sum(1 for c in classifications if "Trash" in c.get("category", ""))
            if trash_count:
                print(f"   LLM判定垃圾: {trash_count} 封")

            if items:
                print(f"\n📝 同步学术项目到 Notion...")
                result = self.academic_processor.process(items)
                print(f"   论文: {result['papers_synced']} 条")
                print(f"   审稿: {result['reviews_synced']} 条")

            # 记录处理状态
            for i, email in enumerate(need_stage2, 1):
                final_category = class_map.get(i, email.get("_stage1_category", "UNKNOWN"))
                email["_final_category"] = final_category

                # 找到对应的item
                item_category = None
                for item in items:
                    if i in item.get("source_emails", []):
                        item_category = item.get("category")
                        break

                # 同步重要邮件到邮件整理
                is_important = final_category in ["Paper/InProgress", "Review/Active", "Action/Important", "Notice/School", "Notice/Exam"]
                if is_important or item_category in ["Paper/InProgress", "Review/Active"]:
                    if self.notion.sync_email(email, "学术"):
                        synced_to_emails_db += 1

                self.state.mark_processed(
                    message_id=email.get("message_id"),
                    account=email.get("account"),
                    subject=email.get("subject"),
                    stage1_result=email.get("_stage1_category", "UNKNOWN"),
                    stage2_category=item_category or final_category,
                    synced=is_important,
                    marked_read=True
                )
                self.email_client.mark_as_read(email["account"], email["email_id"])

        # 5. 处理账单邮件
        if billing_emails:
            print(f"\n💳 分析账单邮件...")
            # 加载正文
            for email in billing_emails:
                self.email_client.load_email_body(email)

            billing_items = self.billing_processor.parse_billing_emails(billing_emails)

            if billing_items:
                print(f"   识别到 {len(billing_items)} 个账单项目")
                result = self.billing_processor.process(billing_items)
                print(f"   新条目: {result['new_items']}")
                print(f"   更新记录: {result['updated_records']}")
                print(f"   同步Notion: {result['synced_to_notion']}")

            # 同步账单邮件到邮件整理
            for email in billing_emails:
                if self.notion.sync_email(email, "账单"):
                    synced_to_emails_db += 1

                self.state.mark_processed(
                    message_id=email.get("message_id"),
                    account=email.get("account"),
                    subject=email.get("subject"),
                    stage1_result="BILLING",
                    synced=True,
                    marked_read=True
                )
                self.email_client.mark_as_read(email["account"], email["email_id"])

        # 6. 处理通知公告邮件
        for email in notice_emails:
            self.email_client.load_email_body(email)
            if self.notion.sync_email(email, "通知"):
                synced_to_emails_db += 1

            self.state.mark_processed(
                message_id=email.get("message_id"),
                account=email.get("account"),
                subject=email.get("subject"),
                stage1_result="NOTICE",
                synced=True,
                marked_read=True
            )
            self.email_client.mark_as_read(email["account"], email["email_id"])

        # 7. 处理个人邮件
        for email in personal_emails:
            self.email_client.load_email_body(email)
            if self.notion.sync_email(email, "个人"):
                synced_to_emails_db += 1

            self.state.mark_processed(
                message_id=email.get("message_id"),
                account=email.get("account"),
                subject=email.get("subject"),
                stage1_result="PERSONAL",
                synced=True,
                marked_read=True
            )
            self.email_client.mark_as_read(email["account"], email["email_id"])

        if synced_to_emails_db > 0:
            print(f"\n📋 同步到邮件整理: {synced_to_emails_db} 封")

        print(f"\n{'='*50}")
        print(f"✅ 处理完成")
        print('='*50)

        return {
            "total": len(all_unread),
            "new": len(new_emails),
            "trash": len(trash_emails),
            "academic": len(academic_emails),
            "billing": len(billing_emails),
            "notice": len(notice_emails),
            "personal": len(personal_emails),
            "unknown": len(unknown_emails),
        }

    def run_forever(self, interval: int = None):
        """
        持续运行，定时检查邮件

        Args:
            interval: 检查间隔（秒），默认使用配置
        """
        interval = interval or CHECK_INTERVAL
        print(f"\n🚀 邮件监控已启动")
        print(f"   检查间隔: {interval}秒 ({interval//60}分钟)")
        print(f"   按 Ctrl+C 停止\n")

        try:
            while True:
                try:
                    self.check_and_process()
                except Exception as e:
                    print(f"\n⚠️ 处理出错: {e}")

                print(f"\n⏰ 下次检查: {interval}秒后...")
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n👋 监控已停止")

    def run_once(self):
        """运行一次检查"""
        return self.check_and_process()
