"""
统一配置文件（示例）
复制此文件为 settings.py 并填入实际配置
"""

# ============== 邮箱配置 ==============

EMAIL_ACCOUNTS = [
    {
        "name": "QQ邮箱",
        "address": "your_email@qq.com",
        "password": "your_app_password",  # QQ邮箱授权码
        "imap_host": "imap.qq.com",
        "imap_port": 993,
        "smtp_host": "smtp.qq.com",
        "smtp_port": 465,
    },
    {
        "name": "PKU邮箱",
        "address": "your_email@pku.edu.cn",
        "password": "your_password",
        "imap_host": "mail.pku.edu.cn",
        "imap_port": 993,
        "smtp_host": "mail.pku.edu.cn",
        "smtp_port": 465,
    },
]

# 默认发送邮箱
DEFAULT_SEND_ACCOUNT = "QQ邮箱"

# 邮件签名
EMAIL_SIGNATURE = """
--
Your Name
Your Title
Your Organization
"""

# ============== Kimi API 配置 ==============

KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"
KIMI_API_KEY = "your_kimi_api_key"
KIMI_MODEL = "kimi-k2.5"
KIMI_TIMEOUT = 120  # 秒

# ============== Notion 配置 ==============

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_TOKEN = "your_notion_token"
NOTION_VERSION = "2022-06-28"

# 数据库名称
NOTION_DB_PAPERS = "📄 论文投稿管理"
NOTION_DB_REVIEWS = "📝 审稿任务管理"
NOTION_DB_EMAILS = "📬 邮件整理"
NOTION_DB_BILLING = "💳 账单管理"

# 父页面（所有数据库都放在这个页面下）
NOTION_PARENT_PAGE_ID = "your_notion_page_id"

# ============== 定时任务配置 ==============

CHECK_INTERVAL = 600  # 10分钟检查一次
MAX_EMAILS_PER_BATCH = 20  # 每批最多处理邮件数

# ============== 状态数据库 ==============

STATE_DB_PATH = "state.db"
