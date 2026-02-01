# Email Manager

基于 LLM 的智能邮件管理系统，自动分类邮件并同步到 Notion。

## 功能特性

- **两阶段 LLM 分类**
  - Stage 1: 分析邮件标题和发件人快速分类
  - Stage 2: 对需要深度分析的邮件读取正文内容

- **智能分类**
  - 垃圾邮件（会议征稿、营销推广等）
  - 学术邮件（论文投稿、审稿任务）
  - 账单邮件（信用卡、会员订阅）
  - 重要邮件（学校通知等）

- **Notion 同步**
  - 论文投稿管理数据库
  - 审稿任务管理数据库
  - 账单管理数据库
  - 邮件整理数据库

- **多账户支持**
  - 支持多个邮箱账户（QQ邮箱、PKU邮箱等）
  - 统一管理和分类

## 项目结构

```
emailmanager/
├── config/
│   ├── settings.py      # 配置（从.env读取）
│   └── categories.py    # 分类规则定义
├── core/
│   ├── email_client.py  # IMAP/SMTP 邮件客户端
│   ├── notion_client.py # Notion API 客户端
│   ├── state.py         # 状态管理（SQLite）
│   └── billing_db.py    # 账单数据库
├── processors/
│   ├── classifier.py    # LLM 两阶段分类器
│   ├── academic.py      # 学术邮件处理
│   └── billing.py       # 账单邮件处理
├── scheduler/
│   └── watcher.py       # 邮件监控调度器
├── main.py              # 程序入口
├── .env                 # 环境变量（敏感配置）
└── .env.example         # 环境变量模板
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
# 邮箱配置
QQ_EMAIL_ADDRESS=your_email@qq.com
QQ_EMAIL_PASSWORD=your_app_password  # QQ邮箱授权码

PKU_EMAIL_ADDRESS=your_email@pku.edu.cn
PKU_EMAIL_PASSWORD=your_password

# Kimi API（用于LLM分类）
KIMI_API_KEY=your_kimi_api_key

# Notion（用于数据同步）
NOTION_TOKEN=your_notion_token
NOTION_PARENT_PAGE_ID=your_page_id
```

## 使用

```bash
# 运行一次邮件检查
python main.py

# 持续监控模式（每10分钟检查一次）
python main.py --watch

# 自定义检查间隔（秒）
python main.py --watch --interval 300

# 查看统计信息
python main.py --stats

# 清理30天前的记录
python main.py --cleanup 30
```

## 工作流程

```
1. 获取未读邮件
      ↓
2. Stage 1: LLM分析标题
   ├── TRASH → 标记已读，跳过
   ├── ACADEMIC → 进入Stage 2
   ├── BILLING → 解析账单信息
   ├── IMPORTANT → 同步到Notion
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
   └── 重要邮件 → 邮件整理
```

## 依赖

- Python 3.10+
- requests
- python-dotenv

## API

- **Kimi API** (kimi-k2.5): 用于邮件内容分析和分类
- **Notion API**: 用于数据库同步
- **IMAP/SMTP**: 用于邮件读取和发送

## License

MIT
