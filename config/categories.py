"""
分类规则定义
两阶段分类策略
"""

# ============== Stage 1: 快速标题筛选规则 ==============

# 垃圾邮件关键词（标题/发件人匹配任一即为垃圾）
TRASH_KEYWORDS_TITLE = [
    # 会议/征稿
    "call for papers", "cfp", "conference invitation", "special issue",
    "submit your paper", "invitation to submit", "征稿", "会议邀请",
    "organizing committee", "join the committee",
    "international conference", "virtual conference", "legal conference",
    # 期刊/投稿邀请
    "join our editorial", "become a reviewer", "editor invitation",
    "invited to contribute", "welcome to submit", "submit your original",
    "contribute articles", "indexed by scopus", "indexed by wos",
    "scopus and wos", "esci success", "elite publishing",
    "加急审稿", "ssci", "ei版面", "版面费",
    # 事务性噪音
    "citation alert", "new citation", "reprints", "offprints",
    "order your copies", "confirm co-authorship", "verify authorship",
    "verify your contribution", "copyright transfer", "terms of service",
    "privacy policy", "password reset", "verify your email", "account security",
    "reprint offer", "隐私政策",
    # 系统通知
    "quarantine", "隔离区", "隔离通知",
    # 营销/促销
    "discount", "promotion", "sale", "limited offer", "subscribe",
    "save $", "% off", "off!", "limited time", "last chance",
    "welcome back", "don't be a stranger", "stranger",
    "new issue of", "publish and share",
    # 日文营销
    "ポイント", "ギフト",
    # 产品推广
    "新品直播", "尽在", "app下载", "限时",
]

TRASH_KEYWORDS_SENDER = [
    "noreply", "no-reply", "newsletter", "marketing", "promotion",
    "advertising", "mailer-daemon", "postmaster",
    "copyright.com",  # 版权/重印本
    "technium", "playcanvas", "extrabux", "insta360",  # 具体营销发件人
]

# 学术相关关键词（可能需要进一步分析）
ACADEMIC_KEYWORDS_TITLE = [
    # 投稿流程
    "manuscript", "submission", "revision", "decision", "accepted",
    "rejected", "under review", "proof", "稿件", "投稿",
    # 审稿
    "review invitation", "referee", "reviewer", "审稿邀请",
]

ACADEMIC_KEYWORDS_SENDER = [
    "editorialmanager", "elsevier", "springer", "wiley", "mdpi",
    "ieee", "taylor", "sage", "nature", "science", "ems.press",
    "manuscript", "editorial", "editor",
]

# ============== Stage 2: 深度分类选项 ==============

CATEGORIES = {
    # 高价值：需要同步和关注
    "Paper/InProgress": "我的论文正在投稿流程中（提交、审稿中、修改要求、接收）",
    "Review/Active": "我需要完成的审稿任务",
    "Action/Important": "需要回复或处理的重要邮件",
    "Info/Newsletter": "有价值的Newsletter/订阅内容",

    # 学术垃圾桶（陷阱选项）
    "Academic/Admin_Noise": "学术事务性垃圾：引用提醒、重印本邀请、共同作者确认、版权转让、APC发票",

    # 垃圾
    "Spam/Conference": "会议邀请、征稿通知、特刊征稿",
    "Spam/Journal": "期刊投稿邀请、编辑邀请、掠夺性期刊",
    "Spam/Other": "其他垃圾邮件",
}

# 需要同步到Notion的分类
SYNC_CATEGORIES = ["Paper/InProgress", "Review/Active", "Action/Important", "Info/Newsletter"]

# 直接丢弃的分类
TRASH_CATEGORIES = ["Academic/Admin_Noise", "Spam/Conference", "Spam/Journal", "Spam/Other"]

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
