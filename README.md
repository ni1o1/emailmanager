# Email Manager

基于 LLM 的智能邮件管理系统，自动分类邮件并同步到 Notion，支持 iMessage 实时通知。

## 功能特性

- **两阶段 LLM 分类**
  - Stage 1: 分析邮件标题和发件人快速分类（批量处理，低成本）
  - Stage 2: 对需要深度分析的邮件读取正文内容（逐封处理，高精度）

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

## 快速开始

### 1. 克隆仓库

```bash
git clone git@github.com:ni1o1/emailmanager.git
cd emailmanager
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或 Windows: venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的配置（详见下方[配置说明](#配置说明)）。

### 5. 运行

```bash
# 运行一次邮件检查
python main.py

# 持续监控模式（每10分钟检查一次）
python main.py --watch

# 自定义检查间隔（秒）
python main.py --watch --interval 300
```

## 配置说明

### 环境变量 (.env)

所有敏感配置都通过 `.env` 文件管理，该文件不会被提交到 Git。

```env
# ============== 邮箱配置 ==============

# QQ邮箱（需要开启IMAP并获取授权码）
QQ_EMAIL_ADDRESS=your_email@qq.com
QQ_EMAIL_PASSWORD=your_app_password  # QQ邮箱授权码，非登录密码

# PKU邮箱
PKU_EMAIL_ADDRESS=your_email@pku.edu.cn
PKU_EMAIL_PASSWORD=your_password

# ============== Kimi API ==============

KIMI_API_KEY=your_kimi_api_key
# API 地址（可选，默认 Moonshot）
# KIMI_API_URL=https://api.moonshot.cn/v1/chat/completions
# 模型名称（可选，默认 kimi-k2.5）
# KIMI_MODEL=kimi-k2.5
# 超时时间秒（可选，默认 120）
# KIMI_TIMEOUT=120

# ============== Notion ==============

NOTION_TOKEN=your_notion_token
NOTION_PARENT_PAGE_ID=your_page_id

# ============== iMessage 通知 ==============

# 是否启用 iMessage 通知（true/false）
IMESSAGE_ENABLED=true

# iMessage 收件人（手机号或 Apple ID）
# 格式：+86xxxxxxxxxxx 或 your_email@icloud.com
IMESSAGE_RECIPIENT=+86xxxxxxxxxxx

# 通知级别：all（每次处理都通知）/ important（仅重要邮件）/ summary（摘要）
IMESSAGE_NOTIFY_LEVEL=all

# 静默时段（不发送通知）- 格式：HH:MM-HH:MM
IMESSAGE_QUIET_HOURS=23:00-07:00

# ============== 邮件签名 ==============

# 自动回复邮件的签名
# 多行签名使用 \n 分隔
# 例如：Best regards,\n\nYour Name\nYour Title\nYour Organization
EMAIL_SIGNATURE=Best regards,\n\nYour Name
```

### 获取 API 密钥

#### QQ邮箱授权码

1. 登录 [QQ邮箱](https://mail.qq.com)
2. 进入 设置 → 账户
3. 开启 IMAP/SMTP 服务
4. 生成授权码（用于 `QQ_EMAIL_PASSWORD`）

#### Kimi API Key

1. 访问 [Moonshot AI 开放平台](https://platform.moonshot.cn)
2. 注册/登录账号
3. 创建 API Key

#### Notion Token

1. 访问 [Notion Integrations](https://www.notion.so/my-integrations)
2. 创建新的 Integration
3. 复制 Internal Integration Token
4. 在 Notion 中将 Integration 添加到目标页面

### Prompt 模板配置

LLM 分类行为由 `config/prompts/` 目录下的 Prompt 模板控制。你可以根据自己的需求修改这些模板。

#### Stage 1 分类器 (`config/prompts/stage1_classifier.md`)

用于快速分类邮件标题，决定哪些邮件需要深度分析。

**分类类别：**
- `EXAM` - 考试相关（雅思、托福、GRE等）
- `BILLING` - 账单（信用卡、会员续费）
- `PAPER` - 论文投稿流程中的状态变更
- `REVIEW` - 审稿任务
- `NOTICE` - 学校/单位官方通知
- `PERSONAL` - 个人邮件（真人发送）
- `TRASH` - 垃圾邮件（广告、推销、虚荣指标）
- `UNKNOWN` - 无法判断

**自定义方法：**

编辑 `config/prompts/stage1_classifier.md`，可以：
- 修改分类的判断标准
- 添加新的垃圾邮件特征
- 调整分类优先级

#### Stage 2 分析器 (`config/prompts/stage2_analyzer.md`)

用于深度分析邮件内容，提取结构化信息。

**功能：**
- 重要性评分（1-5分）
- 行动判定（是否需要回复/提交/支付等）
- 学术垃圾识别（抽印本推销、引用提醒等）
- 信息提取（期刊名、稿件号、截止日期等）

**自定义方法：**

编辑 `config/prompts/stage2_analyzer.md`，可以：
- 调整重要性评分标准
- 修改 "需要行动" 的判定逻辑
- 添加特定领域的信息提取规则

## 项目结构

```
emailmanager/
├── config/
│   ├── settings.py          # 配置（从.env读取）
│   ├── categories.py        # 分类规则定义
│   └── prompts/             # LLM Prompt 模板
│       ├── stage1_classifier.md  # 标题分类 Prompt
│       └── stage2_analyzer.md    # 内容分析 Prompt
├── core/
│   ├── email_client.py      # IMAP/SMTP 邮件客户端
│   ├── notion_client.py     # Notion API 客户端
│   ├── state.py             # 状态管理（SQLite）
│   ├── billing_db.py        # 账单数据库
│   ├── imessage.py          # iMessage 发送客户端
│   ├── message_formatter.py # 消息格式化
│   ├── logger.py            # 统一日志系统
│   ├── validator.py         # 配置验证器
│   ├── exceptions.py        # 统一异常定义
│   └── metrics.py           # 性能指标收集
├── processors/
│   ├── classifier.py        # LLM 两阶段分类器
│   ├── academic.py          # 学术邮件处理
│   ├── billing.py           # 账单邮件处理
│   └── email_processor.py   # 邮件处理共享逻辑
├── scheduler/
│   └── watcher.py           # 邮件监控调度器
├── tests/                   # 单元测试
├── logs/                    # 日志目录
├── main.py                  # 程序入口
├── process_week_emails.py   # 批量处理历史邮件
└── state.db                 # 处理状态数据库
```

## 使用方法

### 基本命令

```bash
# 运行一次邮件检查
python main.py

# 持续监控模式（默认每10分钟检查一次）
python main.py --watch

# 自定义检查间隔（秒）
python main.py --watch --interval 300

# 查看统计信息
python main.py --stats

# 清理30天前的记录
python main.py --cleanup 30

# 批量处理历史邮件（最近一周）
python process_week_emails.py
```

### 后台运行

```bash
# 使用 nohup 后台运行
nohup python main.py --watch > logs/watcher.log 2>&1 &

# 查看运行状态
ps aux | grep "main.py"

# 查看实时日志
tail -f logs/emailmanager.log
```

### 使用 launchd（macOS 推荐）

创建 `~/Library/LaunchAgents/com.emailmanager.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.emailmanager</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/venv/bin/python</string>
        <string>/path/to/emailmanager/main.py</string>
        <string>--watch</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/emailmanager</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/path/to/emailmanager/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/emailmanager/logs/launchd.err</string>
</dict>
</plist>
```

```bash
# 加载服务
launchctl load ~/Library/LaunchAgents/com.emailmanager.plist

# 查看状态
launchctl list | grep emailmanager

# 停止服务
launchctl unload ~/Library/LaunchAgents/com.emailmanager.plist
```

## 工作流程

```
1. 获取未读邮件
      ↓
2. Stage 1: LLM分析标题（批量）
   ├── TRASH → 标记已读，跳过
   ├── PAPER → 进入Stage 2
   ├── REVIEW → 进入Stage 2
   ├── BILLING → 解析账单信息
   ├── NOTICE/EXAM/PERSONAL → 进入Stage 2
   └── UNKNOWN → 进入Stage 2
      ↓
3. Stage 2: LLM分析内容（逐封）
   ├── 提取论文/审稿信息
   └── 确定最终分类和重要程度
      ↓
4. 同步到Notion
   ├── 论文 → 论文投稿管理
   ├── 审稿 → 审稿任务管理
   ├── 账单 → 账单管理
   └── 其他 → 邮件整理
      ↓
5. 发送 iMessage 通知
```

## 开发

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 查看覆盖率
pytest tests/ --cov=core --cov=processors
```

### 日志

日志文件位于 `logs/` 目录：
- `emailmanager.log`: 主日志（轮转，最大10MB）
- `errors.log`: 错误日志
- `watcher.log`: 监控服务输出

可通过环境变量 `LOG_LEVEL` 设置日志级别（DEBUG/INFO/WARNING/ERROR）。

### 配置验证

程序启动时会自动验证配置，检查：
- 必需的环境变量是否存在
- 至少配置了一个有效的邮箱账户
- iMessage 配置的一致性

## 依赖

- Python 3.10+
- requests
- python-dotenv
- pytest (开发)

## API

- **Kimi API** (kimi-k2.5): 邮件内容分析和分类
- **Notion API**: 数据库同步
- **IMAP/SMTP**: 邮件读取和发送
- **AppleScript**: iMessage 发送（macOS）

## 常见问题

### QQ邮箱连接失败

1. 确认已开启 IMAP 服务
2. 使用授权码而非登录密码
3. 检查网络是否能访问 imap.qq.com:993

### Notion 同步失败

1. 确认 Integration 已添加到目标页面
2. 检查 NOTION_PARENT_PAGE_ID 是否正确
3. 查看 logs/errors.log 获取详细错误信息

### iMessage 通知不工作

1. 仅支持 macOS
2. 确认 IMESSAGE_RECIPIENT 格式正确
3. 检查是否在静默时段内

## License

MIT
