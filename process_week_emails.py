#!/usr/bin/env python3
"""
处理最近一周的所有邮件并同步到 Notion
这是一个一次性脚本，用于初始化/重建 Notion 数据库
"""

import sys
sys.path.insert(0, '/Users/yuqing/emailmanager')

from datetime import datetime
from typing import List, Dict

from core.email_client import EmailClient
from core.notion_client import NotionClient
from core.state import StateManager
from core.billing_db import BillingDB
from processors.classifier import EmailClassifier
from processors.academic import AcademicProcessor
from processors.billing import BillingProcessor


def process_week_emails():
    """处理最近一周的所有邮件"""
    print("=" * 60)
    print("📬 处理最近一周邮件并同步到 Notion")
    print(f"   开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 初始化组件
    email_client = EmailClient()
    notion = NotionClient()
    state = StateManager()
    billing_db = BillingDB()
    classifier = EmailClassifier()
    academic_processor = AcademicProcessor(notion)
    billing_processor = BillingProcessor(billing_db, notion)

    # 1. 获取最近一周的所有邮件
    print("\n📥 获取最近一周邮件...")
    all_emails = email_client.fetch_recent_emails(days=7, limit=200)
    print(f"   共找到 {len(all_emails)} 封邮件")

    if not all_emails:
        print("   ⚠️ 没有找到邮件")
        return

    # 2. Stage 1: LLM分析标题分类
    print(f"\n🤖 Stage 1: 分析邮件标题...")
    classifier.stage1_classify_batch(all_emails)

    # 按分类分组
    trash_emails = []
    paper_emails = []
    review_emails = []
    billing_emails = []
    notice_emails = []
    exam_emails = []
    personal_emails = []
    unknown_emails = []

    for email in all_emails:
        category = email.get("_stage1_category", "UNKNOWN")
        if category == "TRASH":
            trash_emails.append(email)
        elif category == "PAPER":
            paper_emails.append(email)
        elif category == "REVIEW":
            review_emails.append(email)
        elif category == "BILLING":
            billing_emails.append(email)
        elif category == "NOTICE":
            notice_emails.append(email)
        elif category == "EXAM":
            exam_emails.append(email)
        elif category == "PERSONAL":
            personal_emails.append(email)
        else:
            unknown_emails.append(email)

    print(f"\n📊 Stage 1 分类结果:")
    print(f"   垃圾邮件: {len(trash_emails)} 封")
    print(f"   论文投稿: {len(paper_emails)} 封")
    print(f"   审稿任务: {len(review_emails)} 封")
    print(f"   账单邮件: {len(billing_emails)} 封")
    print(f"   通知公告: {len(notice_emails)} 封")
    print(f"   考试相关: {len(exam_emails)} 封")
    print(f"   个人邮件: {len(personal_emails)} 封")
    print(f"   待分析: {len(unknown_emails)} 封")

    synced_to_emails_db = 0

    # 记录垃圾邮件（不同步到Notion）
    for email in trash_emails:
        state.mark_processed(
            message_id=email.get("message_id"),
            account=email.get("account"),
            subject=email.get("subject"),
            stage1_result="TRASH",
            marked_read=False  # 不标记已读，保留原状态
        )

    # 3. 处理需要Stage 2分析的邮件（论文 + 审稿 + unknown）
    need_stage2 = paper_emails + review_emails + unknown_emails
    if need_stage2:
        print(f"\n📖 加载 {len(need_stage2)} 封邮件内容...")
        for email in need_stage2:
            email_client.load_email_body(email)

        print(f"🤖 Stage 2: 分析邮件内容...")
        analysis = classifier.stage2_analyze_content(need_stage2)

        items = analysis.get("items", [])
        classifications = analysis.get("classifications", [])

        print(f"   识别到 {len(items)} 个学术项目")

        class_map = {c["id"]: c for c in classifications}
        trash_count = sum(1 for c in classifications if "Trash" in c.get("category", ""))
        if trash_count:
            print(f"   LLM判定垃圾: {trash_count} 封")

        if items:
            print(f"\n📝 同步学术项目到 Notion...")
            result = academic_processor.process(items)
            print(f"   论文: {result['papers_synced']} 条")
            print(f"   审稿: {result['reviews_synced']} 条")

        # 记录处理状态
        for i, email in enumerate(need_stage2, 1):
            cls_info = class_map.get(i, {})
            final_category = cls_info.get("category", email.get("_final_category", "Unknown"))
            importance = email.get("_importance", 2)
            needs_action = email.get("_needs_action", False)
            summary = email.get("_summary", "")[:20]
            venue = email.get("_venue", "")

            item_category = None
            for item in items:
                if i in item.get("source_emails", []):
                    item_category = item.get("category")
                    if not venue:
                        venue = item.get("venue", "")
                    break

            is_trash = "Trash" in (final_category or "")
            is_paper = "Paper" in (final_category or "") or "Paper" in (item_category or "")
            is_review = "Review" in (final_category or "") or "Review" in (item_category or "")

            if not is_trash and (is_paper or is_review or needs_action):
                email_category = "审稿" if is_review else "学术"
                if notion.sync_email(email, email_category, importance, needs_action, summary, venue):
                    synced_to_emails_db += 1

            state.mark_processed(
                message_id=email.get("message_id"),
                account=email.get("account"),
                subject=email.get("subject"),
                stage1_result=email.get("_stage1_category", "UNKNOWN"),
                stage2_category=item_category or final_category,
                synced=not is_trash,
                marked_read=False
            )

    # 4. 处理账单邮件
    if billing_emails:
        print(f"\n💳 处理 {len(billing_emails)} 封账单邮件...")
        for email in billing_emails:
            email_client.load_email_body(email)

        billing_items = billing_processor.parse_billing_emails(billing_emails)

        if billing_items:
            print(f"   识别到 {len(billing_items)} 个账单项目")
            result = billing_processor.process(billing_items)
            print(f"   新条目: {result['new_items']}")
            print(f"   同步Notion: {result['synced_to_notion']}")

        for email in billing_emails:
            if notion.sync_email(email, "账单", importance=2, needs_action=False):
                synced_to_emails_db += 1

            state.mark_processed(
                message_id=email.get("message_id"),
                account=email.get("account"),
                subject=email.get("subject"),
                stage1_result="BILLING",
                synced=True,
                marked_read=False
            )

    # 5. 处理通知公告邮件
    if notice_emails:
        print(f"\n📢 处理 {len(notice_emails)} 封通知邮件...")
        for email in notice_emails:
            email_client.load_email_body(email)

        classifier.stage2_analyze_content(notice_emails)

        for email in notice_emails:
            importance = email.get("_importance", 2)
            needs_action = email.get("_needs_action", False)
            summary = email.get("_summary", "")[:20]

            if notion.sync_email(email, "通知", importance, needs_action, summary):
                synced_to_emails_db += 1

            state.mark_processed(
                message_id=email.get("message_id"),
                account=email.get("account"),
                subject=email.get("subject"),
                stage1_result="NOTICE",
                synced=True,
                marked_read=False
            )

    # 6. 处理考试相关邮件
    if exam_emails:
        print(f"\n📝 处理 {len(exam_emails)} 封考试邮件...")
        for email in exam_emails:
            email_client.load_email_body(email)

        classifier.stage2_analyze_content(exam_emails)

        for email in exam_emails:
            importance = email.get("_importance", 5)
            needs_action = email.get("_needs_action", True)
            summary = email.get("_summary", "")[:20]

            if notion.sync_email(email, "考试", importance, needs_action, summary):
                synced_to_emails_db += 1

            state.mark_processed(
                message_id=email.get("message_id"),
                account=email.get("account"),
                subject=email.get("subject"),
                stage1_result="EXAM",
                synced=True,
                marked_read=False
            )

    # 7. 处理个人邮件
    if personal_emails:
        print(f"\n👤 处理 {len(personal_emails)} 封个人邮件...")
        for email in personal_emails:
            email_client.load_email_body(email)

        classifier.stage2_analyze_content(personal_emails)

        for email in personal_emails:
            importance = email.get("_importance", 3)
            needs_action = email.get("_needs_action", False)
            summary = email.get("_summary", "")[:20]

            if notion.sync_email(email, "个人", importance, needs_action, summary):
                synced_to_emails_db += 1

            state.mark_processed(
                message_id=email.get("message_id"),
                account=email.get("account"),
                subject=email.get("subject"),
                stage1_result="PERSONAL",
                synced=True,
                marked_read=False
            )

    # 统计结果
    print("\n" + "=" * 60)
    print("📊 处理完成统计")
    print("=" * 60)
    print(f"   总邮件数: {len(all_emails)}")
    print(f"   垃圾邮件: {len(trash_emails)} (未同步)")
    print(f"   同步到邮件整理: {synced_to_emails_db} 封")
    print(f"\n   完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    process_week_emails()
