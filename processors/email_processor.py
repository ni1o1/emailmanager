"""
邮件处理核心逻辑
提供共享的邮件分类和处理功能
"""

from typing import Dict, List, Tuple


def group_emails_by_category(emails: List[Dict]) -> Dict[str, List[Dict]]:
    """
    按 Stage 1 分类结果对邮件进行分组

    Args:
        emails: 已经过 Stage 1 分类的邮件列表

    Returns:
        分类字典，键为分类名，值为邮件列表
    """
    groups = {
        "TRASH": [],
        "PAPER": [],
        "REVIEW": [],
        "BILLING": [],
        "NOTICE": [],
        "EXAM": [],
        "PERSONAL": [],
        "UNKNOWN": [],
    }

    for email in emails:
        category = email.get("_stage1_category", "UNKNOWN")
        if category in groups:
            groups[category].append(email)
        else:
            groups["UNKNOWN"].append(email)

    return groups


def print_classification_stats(groups: Dict[str, List[Dict]], prefix: str = "   "):
    """打印分类统计"""
    labels = {
        "TRASH": "垃圾邮件",
        "PAPER": "论文投稿",
        "REVIEW": "审稿任务",
        "BILLING": "账单邮件",
        "NOTICE": "通知公告",
        "EXAM": "考试相关",
        "PERSONAL": "个人邮件",
        "UNKNOWN": "待分析",
    }

    for key, label in labels.items():
        count = len(groups.get(key, []))
        print(f"{prefix}{label}: {count} 封")


def process_stage2_results(
    emails: List[Dict],
    analysis: Dict,
    items: List[Dict]
) -> Tuple[List[Dict], Dict[int, Dict]]:
    """
    处理 Stage 2 分析结果

    Args:
        emails: Stage 2 处理的邮件列表
        analysis: Stage 2 返回的分析结果
        items: 识别到的学术项目列表

    Returns:
        (处理后的邮件列表, 分类信息映射)
    """
    classifications = analysis.get("classifications", [])
    class_map = {c["id"]: c for c in classifications}

    for i, email in enumerate(emails, 1):
        cls_info = class_map.get(i, {})
        final_category = cls_info.get("category", email.get("_final_category", "Unknown"))
        email["_final_category"] = final_category

        # 查找对应的 item 获取更多信息
        for item in items:
            if i in item.get("source_emails", []):
                email["_item_category"] = item.get("category")
                if not email.get("_venue"):
                    email["_venue"] = item.get("venue", "")
                break

    return emails, class_map


def should_sync_to_emails_db(email: Dict) -> Tuple[bool, str]:
    """
    判断邮件是否应该同步到邮件整理数据库

    Args:
        email: 邮件字典

    Returns:
        (是否同步, 分类名称)
    """
    final_category = email.get("_final_category", "")
    item_category = email.get("_item_category", "")
    needs_action = email.get("_needs_action", False)

    is_trash = "Trash" in (final_category or "")
    is_paper = "Paper" in (final_category or "") or "Paper" in (item_category or "")
    is_review = "Review" in (final_category or "") or "Review" in (item_category or "")

    if is_trash:
        return False, ""

    if is_paper or is_review or needs_action:
        category = "审稿" if is_review else "学术"
        return True, category

    return False, ""


# 各类邮件的默认配置
EMAIL_CATEGORY_DEFAULTS = {
    "TRASH": {"importance": 1, "needs_action": False, "sync": False},
    "PAPER": {"importance": 4, "needs_action": True, "sync": True, "db_category": "学术"},
    "REVIEW": {"importance": 4, "needs_action": True, "sync": True, "db_category": "审稿"},
    "BILLING": {"importance": 2, "needs_action": False, "sync": True, "db_category": "账单"},
    "NOTICE": {"importance": 2, "needs_action": False, "sync": True, "db_category": "通知"},
    "EXAM": {"importance": 5, "needs_action": True, "sync": True, "db_category": "考试"},
    "PERSONAL": {"importance": 3, "needs_action": False, "sync": True, "db_category": "个人"},
}
