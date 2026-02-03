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

## 项目结构

```
emailmanager/
├── config/
│   ├── settings.py          # 配置（从.env读取）
│   ├── categories.py        # 分类规则定义
│   └── prompts/             # LLM Prompt 模板
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
QQ_EMAIL_ADDRESS=your_email@qq.com
QQ_EMAIL_PASSWORD=your_app_password  # QQ邮箱授权码

PKU_EMAIL_ADDRESS=your_email@pku.edu.cn
PKU_EMAIL_PASSWORD=your_password

# ============== Kimi API ==============
KIMI_API_KEY=your_kimi_api_key

# ============== Notion ==============
NOTION_TOKEN=your_notion_token
NOTION_PARENT_PAGE_ID=your_page_id

# ============== iMessage 通知 ==============
IMESSAGE_ENABLED=true
IMESSAGE_SENDER=your_account_id
IMESSAGE_RECIPIENT=+86xxxxxxxxxxx
IMESSAGE_NOTIFY_LEVEL=all  # all / important / summary
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

## License

MIT
