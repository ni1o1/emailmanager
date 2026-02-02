# Email Manager

基于 LLM 的智能邮件管理系统，自动分类邮件并同步到 Notion，支持 iMessage 实时通知。

## 功能特性

- **两阶段 LLM 分类**
  - Stage 1: 分析邮件标题和发件人快速分类
  - Stage 2: 对需要深度分析的邮件读取正文内容

- **智能分类**
  - 垃圾邮件（会议征稿、营销推广等）
  - 学术邮件（论文投稿、审稿任务）
  - 账单邮件（信用卡、会员订阅）
  - 通知邮件（学校通知等）
  - 考试邮件（考试报名、成绩通知等）
  - 个人邮件

- **Notion 同步**
  - 论文投稿管理数据库
  - 审稿任务管理数据库
  - 账单管理数据库
  - 邮件整理数据库

- **iMessage 通知**（macOS）
  - 新邮件实时推送摘要
  - 每日 14:00 统计简报
  - 服务启动通知
  - 支持自定义发送账号

- **多账户支持**
  - 支持多个邮箱账户（QQ邮箱、PKU邮箱等）
  - 统一管理和分类

## 项目结构

```
emailmanager/
├── config/
│   ├── settings.py         # 配置（从.env读取）
│   └── categories.py       # 分类规则定义
├── core/
│   ├── email_client.py     # IMAP/SMTP 邮件客户端
│   ├── notion_client.py    # Notion API 客户端
│   ├── state.py            # 状态管理（SQLite）
│   ├── billing_db.py       # 账单数据库
│   ├── imessage.py         # iMessage 发送客户端
│   └── message_formatter.py # 消息格式化
├── processors/
│   ├── classifier.py       # LLM 两阶段分类器
│   ├── academic.py         # 学术邮件处理
│   └── billing.py          # 账单邮件处理
├── scheduler/
│   └── watcher.py          # 邮件监控调度器
├── legacy/                  # 旧版脚本（备份）
├── main.py                  # 程序入口
├── process_week_emails.py   # 批量处理历史邮件
├── .env                     # 环境变量（敏感配置）
└── .env.example             # 环境变量模板
```

## 安装

```bash
# 克隆仓库
git clone git@github.com:ni1o1/emailmanager.git
cd emailmanager

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际配置
```

## 配置

编辑 `.env` 文件：

```env
# ============== 邮箱配置 ==============

# QQ邮箱
QQ_EMAIL_ADDRESS=your_email@qq.com
QQ_EMAIL_PASSWORD=your_app_password  # QQ邮箱授权码

# PKU邮箱
PKU_EMAIL_ADDRESS=your_email@pku.edu.cn
PKU_EMAIL_PASSWORD=your_password

# ============== Kimi API ==============

KIMI_API_KEY=your_kimi_api_key

# ============== Notion ==============

NOTION_TOKEN=your_notion_token
NOTION_PARENT_PAGE_ID=your_page_id

# ============== iMessage 通知 ==============

# 是否启用 iMessage 通知（true/false）
IMESSAGE_ENABLED=true

# 发送账号ID（在终端运行以下命令查看）:
# osascript -e 'tell application "Messages" to get id of every account'
IMESSAGE_SENDER=your_account_id

# iMessage 收件人（手机号或 Apple ID）
IMESSAGE_RECIPIENT=+86xxxxxxxxxxx

# 通知级别：all / important / summary
IMESSAGE_NOTIFY_LEVEL=all

# 静默时段（不发送通知）- 格式：HH:MM-HH:MM
IMESSAGE_QUIET_HOURS=23:00-07:00
```

## 使用

```bash
# 运行一次邮件检查
python main.py

# 持续监控模式（每10分钟检查一次）
python main.py --watch

# 后台运行监控服务
nohup python main.py --watch > logs/watcher.log 2>&1 &

# 自定义检查间隔（秒）
python main.py --watch --interval 300

# 查看统计信息
python main.py --stats

# 清理30天前的记录
python main.py --cleanup 30

# 批量处理历史邮件（最近一周）
python process_week_emails.py
```

## 工作流程

```
1. 获取未读邮件
      ↓
2. Stage 1: LLM分析标题
   ├── TRASH → 标记已读，跳过
   ├── PAPER → 进入Stage 2（论文投稿）
   ├── REVIEW → 进入Stage 2（审稿任务）
   ├── BILLING → 解析账单信息
   ├── NOTICE → 同步到Notion
   ├── EXAM → 同步到Notion
   ├── PERSONAL → 同步到Notion
   └── UNKNOWN → 进入Stage 2
      ↓
3. Stage 2: LLM分析内容
   ├── 提取论文/审稿信息
   └── 确定最终分类
      ↓
4. 同步到Notion
   ├── 论文 → 论文投稿管理
   ├── 审稿 → 审稿任务管理
   ├── 账单 → 账单管理
   └── 其他 → 邮件整理
      ↓
5. 发送 iMessage 通知（如已启用）
   ├── 新邮件摘要
   └── 每日14:00统计简报
```

## iMessage 通知功能

### 功能说明

- **新邮件通知**：每次检测到新邮件时，发送摘要到指定手机号
- **每日简报**：每天 14:00 发送当日邮件统计
- **启动通知**：服务启动时发送确认消息

### 配置发送账号

为避免自己发给自己没有提示，建议在 Mac 的「信息」App 中登录另一个 Apple ID 作为发送账号：

1. 打开「信息」App
2. 前往「设置」→「iMessage」
3. 添加另一个 Apple ID 账号
4. 在终端运行以下命令获取账号 ID：
   ```bash
   osascript -e 'tell application "Messages" to get id of every account'
   ```
5. 将获取的 ID 填入 `.env` 的 `IMESSAGE_SENDER`

## 依赖

- Python 3.10+
- requests
- python-dotenv

## API

- **Kimi API** (kimi-k2.5): 用于邮件内容分析和分类
- **Notion API**: 用于数据库同步
- **IMAP/SMTP**: 用于邮件读取和发送
- **AppleScript**: 用于 iMessage 发送（macOS）

## License

MIT
