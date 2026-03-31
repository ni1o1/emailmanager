"""
学术邮件处理器
处理论文投稿和审稿任务
"""

from typing import Dict, List

from config.categories import SYNC_CATEGORIES
from core.logger import get_logger

logger = get_logger(__name__)


class AcademicProcessor:
    """学术邮件处理器"""

    def __init__(self):
        pass

    def process(self, items: List[Dict]) -> Dict:
        """
        处理学术相关项目

        Args:
            items: Stage2分析结果中的items

        Returns:
            处理结果统计
        """
        papers_found = 0
        reviews_found = 0
        skipped = 0

        for item in items:
            item_type = item.get("type")
            category = item.get("category", "")

            if category not in SYNC_CATEGORIES:
                skipped += 1
                continue

            if item_type == "paper" and category in ["Paper/InProgress", "Paper/Journal", "Paper/Conference"]:
                papers_found += 1
                venue = item.get('venue', '?')[:20]
                title = (item.get('title') or '?')[:30]
                logger.info(f"   ✓ 论文: [{venue}] {title}")

            elif item_type == "review" and category == "Review/Active":
                reviews_found += 1
                deadline = item.get('deadline') or '无'
                venue = item.get('venue', '?')[:20]
                logger.info(f"   ✓ 审稿: [DDL:{deadline}] {venue}")

        return {
            "papers_synced": papers_found,
            "reviews_synced": reviews_found,
            "skipped": skipped,
        }
