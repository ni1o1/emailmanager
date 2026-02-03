"""
分类规则定义
状态映射和标准化函数
"""

# ============== 需要同步到Notion的分类 ==============

SYNC_CATEGORIES = [
    "Paper/InProgress", "Paper/Journal", "Paper/Conference",  # 论文
    "Review/Active",  # 审稿
    "Action/Important", "Info/Newsletter"
]

# ============== 状态映射 ==============

PAPER_STATUS_MAP = {
    "submitted": "已投稿",
    "under review": "审稿中",
    "with editor": "审稿中",
    "minor revision": "小修",
    "major revision": "大修",
    "accepted": "已接收",
    "rejected": "被拒稿",
    "已投稿": "已投稿",
    "审稿中": "审稿中",
    "小修": "小修",
    "大修": "大修",
    "已接收": "已接收",
    "被拒稿": "被拒稿",
}

REVIEW_STATUS_MAP = {
    "pending": "待接受",
    "invited": "待接受",
    "accepted": "已接受",
    "in progress": "审稿中",
    "reviewing": "审稿中",
    "submitted": "已提交",
    "completed": "已提交",
    "待接受": "待接受",
    "已接受": "已接受",
    "审稿中": "审稿中",
    "已提交": "已提交",
}


def normalize_paper_status(status: str) -> str:
    """标准化论文状态"""
    if not status:
        return "审稿中"
    status_lower = status.lower().strip()
    for key, value in PAPER_STATUS_MAP.items():
        if key.lower() in status_lower:
            return value
    return "审稿中"


def normalize_review_status(status: str) -> str:
    """标准化审稿状态"""
    if not status:
        return "待接受"
    status_lower = status.lower().strip()
    for key, value in REVIEW_STATUS_MAP.items():
        if key.lower() in status_lower:
            return value
    return "待接受"
