"""
学术邮件处理器
处理论文投稿和审稿任务
"""

from typing import Dict, List

from core.notion_client import NotionClient
from config.categories import SYNC_CATEGORIES


class AcademicProcessor:
    """学术邮件处理器"""

    def __init__(self, notion: NotionClient = None):
        self.notion = notion or NotionClient()

    def process(self, items: List[Dict]) -> Dict:
        """
        处理学术相关项目

        Args:
            items: Stage2分析结果中的items

        Returns:
            处理结果统计
        """
        papers_synced = 0
        reviews_synced = 0
        skipped = 0

        for item in items:
            item_type = item.get("type")
            category = item.get("category", "")

            # 只处理需要同步的分类
            if category not in SYNC_CATEGORIES:
                skipped += 1
                continue

            if item_type == "paper" and category in ["Paper/InProgress", "Paper/Journal", "Paper/Conference"]:
                if self.notion.sync_paper(item):
                    papers_synced += 1
                    venue = item.get('venue', '?')[:20]
                    title = (item.get('title') or '?')[:30]
                    print(f"   ✓ 论文: [{venue}] {title}...")

            elif item_type == "review" and category == "Review/Active":
                if self.notion.sync_review(item):
                    reviews_synced += 1
                    deadline = item.get('deadline') or '无'
                    venue = item.get('venue', '?')[:20]
                    print(f"   ✓ 审稿: [DDL:{deadline}] {venue}...")

        return {
            "papers_synced": papers_synced,
            "reviews_synced": reviews_synced,
            "skipped": skipped,
        }
