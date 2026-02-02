"""
分类规则定义
两阶段分类策略
"""

# ============== 发件人优先级系统 ==============

# 高优先级发件人（白名单）- 这些发件人的邮件应该被优先处理
HIGH_PRIORITY_SENDERS = {
    # 考试机构 - 最高优先级
    "ielts": {"category": "EXAM", "importance": 5},
    "britishcouncil": {"category": "EXAM", "importance": 5},
    "ets.org": {"category": "EXAM", "importance": 5},
    "toefl": {"category": "EXAM", "importance": 5},
    "gre": {"category": "EXAM", "importance": 5},
    "candidates.cambridgeenglish": {"category": "EXAM", "importance": 5},

    # 银行账单 - 重要（中文名称 + 域名）
    "招商银行": {"category": "BILLING", "importance": 4},
    "cmbchina": {"category": "BILLING", "importance": 4},  # 招商银行域名
    "95555": {"category": "BILLING", "importance": 4},  # 招商银行号码
    "工商银行": {"category": "BILLING", "importance": 4},
    "icbc": {"category": "BILLING", "importance": 4},  # 工商银行域名
    "建设银行": {"category": "BILLING", "importance": 4},
    "ccb.com": {"category": "BILLING", "importance": 4},  # 建设银行域名
    "交通银行": {"category": "BILLING", "importance": 4},
    "bankcomm": {"category": "BILLING", "importance": 4},  # 交通银行域名
    "中国银行": {"category": "BILLING", "importance": 4},
    "boc.cn": {"category": "BILLING", "importance": 4},  # 中国银行域名
    "citibank": {"category": "BILLING", "importance": 4},
    "citi.com": {"category": "BILLING", "importance": 4},
}

# 垃圾发件人（黑名单）- 直接标记为TRASH
TRASH_SENDERS = [
    # 算力/云服务平台
    "autodl", "autoDL", "阿里云", "aliyun", "腾讯云", "tencent cloud",
    "huawei cloud", "华为云", "aws", "azure",

    # 论文出版后的广告
    "reprints@", "copyright.com", "webshop",

    # 营销平台
    "noreply", "no-reply", "newsletter", "marketing", "promotion",
    "advertising", "mailer-daemon", "postmaster",

    # 会议/期刊垃圾
    "mdpi", "hindawi", "frontiers", "scirp",
]

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
SYNC_CATEGORIES = [
    "Paper/InProgress", "Paper/Journal", "Paper/Conference",  # 论文
    "Review/Active",  # 审稿
    "Action/Important", "Info/Newsletter"
]

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
