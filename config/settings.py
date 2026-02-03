"""
统一配置文件
从 .env 文件读取敏感信息
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# ============== 邮箱配置 ==============

EMAIL_ACCOUNTS = [
    {
        "name": "QQ邮箱",
        "address": os.getenv("QQ_EMAIL_ADDRESS", ""),
        "password": os.getenv("QQ_EMAIL_PASSWORD", ""),
        "imap_host": "imap.qq.com",
        "imap_port": 993,
        "smtp_host": "smtp.qq.com",
        "smtp_port": 465,
    },
    {
        "name": "PKU邮箱",
        "address": os.getenv("PKU_EMAIL_ADDRESS", ""),
        "password": os.getenv("PKU_EMAIL_PASSWORD", ""),
        "imap_host": "mail.pku.edu.cn",
        "imap_port": 993,
        "smtp_host": "mail.pku.edu.cn",
        "smtp_port": 465,
    },
]

# 默认发送邮箱
DEFAULT_SEND_ACCOUNT = "QQ邮箱"

# 邮件签名（从 .env 读取，避免敏感信息泄露到代码仓库）
# 在 .env 中设置 EMAIL_SIGNATURE，使用 \n 分隔多行
EMAIL_SIGNATURE = os.getenv("EMAIL_SIGNATURE", "").replace("\\n", "\n")

# ============== Kimi API 配置 ==============

KIMI_API_URL = os.getenv("KIMI_API_URL", "https://api.moonshot.cn/v1/chat/completions")
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_MODEL = os.getenv("KIMI_MODEL", "kimi-k2.5")
KIMI_TIMEOUT = int(os.getenv("KIMI_TIMEOUT", "120"))  # 秒

# ============== Notion 配置 ==============

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_VERSION = "2022-06-28"

# 数据库名称
NOTION_DB_PAPERS = "📄 论文投稿管理"
NOTION_DB_REVIEWS = "📝 审稿任务管理"
NOTION_DB_EMAILS = "📬 邮件整理"
NOTION_DB_BILLING = "💳 账单管理"

# 父页面（所有数据库都放在这个页面下）
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID", "")

# ============== 定时任务配置 ==============

CHECK_INTERVAL = 600  # 10分钟检查一次
MAX_EMAILS_PER_BATCH = 100  # 每批最多处理邮件数

# ============== 状态数据库 ==============

STATE_DB_PATH = "state.db"

# ============== iMessage 通知配置 ==============

# 是否启用 iMessage 通知
IMESSAGE_ENABLED = os.getenv("IMESSAGE_ENABLED", "false").lower() == "true"

# iMessage 收件人（手机号或 Apple ID）
# 格式：+86xxxxxxxxxxx 或 email@icloud.com
IMESSAGE_RECIPIENT = os.getenv("IMESSAGE_RECIPIENT", "")

# 通知级别：all（所有处理完成都通知）/ important（仅重要邮件）/ summary（仅摘要）
IMESSAGE_NOTIFY_LEVEL = os.getenv("IMESSAGE_NOTIFY_LEVEL", "summary")

# 静默时段（不发送通知）- 格式：HH:MM-HH:MM
IMESSAGE_QUIET_HOURS = os.getenv("IMESSAGE_QUIET_HOURS", "23:00-07:00")
