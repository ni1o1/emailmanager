# 邮件管理系统架构设计

## 当前问题分析

### 性能瓶颈
1. **一次性处理所有邮件**：每次运行都扫描30天的邮件（~100封），即使已经处理过
2. **LLM调用过重**：所有邮件内容都发送给Kimi，token消耗大，容易超时
3. **无增量处理**：没有记录已处理邮件，每次重复工作

### 代码问题
1. 多个重复的脚本（academic_manager.py, academic_manager_v2.py）
2. 配置分散在各文件中
3. 缺少统一入口

## 新架构设计

```
emailmanager/
├── config/
│   ├── __init__.py
│   ├── settings.py          # 统一配置（邮箱、API密钥、Notion）
│   └── categories.py        # 分类规则定义
├── core/
│   ├── __init__.py
│   ├── email_client.py      # 邮件读取（IMAP）
│   ├── email_sender.py      # 邮件发送（SMTP）
│   ├── notion_client.py     # Notion API封装
│   └── state.py             # 状态管理（已处理邮件记录）
├── processors/
│   ├── __init__.py
│   ├── classifier.py        # 两阶段分类器（快筛+精分）
│   ├── academic.py          # 学术邮件处理（论文/审稿）
│   └── general.py           # 通用邮件处理
├── scheduler/
│   ├── __init__.py
│   └── watcher.py           # 定时检查器
├── main.py                   # 统一入口
├── requirements.txt
└── .env
```

## 核心优化：两阶段LLM分类

### Stage 1: 快速标题筛选（低成本）
- 只用邮件标题+发件人
- 使用规则匹配 + 轻量LLM (haiku级别)
- 目标：快速过滤80%的垃圾邮件

```
输入: 标题 + 发件人
输出: TRASH / MAYBE_ACADEMIC / MAYBE_IMPORTANT / UNKNOWN
```

### Stage 2: 深度内容分析（高成本）
- 只对Stage 1筛出的邮件调用完整分析
- 使用Kimi K2.5进行详细分类和信息提取

```
输入: 完整邮件内容
输出: 详细分类 + 结构化信息提取
```

## 增量处理设计

### 状态记录
使用SQLite记录已处理邮件：
```sql
CREATE TABLE processed_emails (
    message_id TEXT PRIMARY KEY,
    account TEXT,
    subject TEXT,
    processed_at DATETIME,
    category TEXT,
    synced_to_notion BOOLEAN
);
```

### 处理流程
```
1. 获取未读邮件
2. 过滤已处理的邮件（查state.db）
3. Stage 1快筛
4. Stage 2精分（仅对有价值邮件）
5. 同步到Notion
6. 记录处理状态
7. 标记邮件为已读
```

## 定时任务设计

### 每10分钟轮询
```python
while True:
    new_emails = check_new_unread_emails()
    if new_emails:
        process_emails(new_emails)
    sleep(600)  # 10分钟
```

### 分类处理流程
```
新邮件 → Stage1快筛
    ├→ TRASH → 直接标记已读，不同步
    ├→ ACADEMIC → academic_processor
    │   ├→ 论文投稿 → 更新论文数据库
    │   └→ 审稿邀请 → 更新审稿数据库
    ├→ IMPORTANT → notion同步 + 标记待处理
    └→ OTHER → notion同步（低优先级）
```

## 预期性能提升

| 指标 | 当前 | 优化后 |
|------|------|--------|
| 每次处理邮件数 | ~100封 | ~5-10封（新邮件） |
| LLM调用次数 | 1次（大payload） | 2次（小payload） |
| LLM Token消耗 | ~50K tokens | ~5K tokens |
| 响应时间 | 2-5分钟 | 10-30秒 |
| 超时风险 | 高 | 低 |

## 使用方法

```bash
# 运行一次检查
python main.py

# 持续监控模式（每10分钟检查）
python main.py --watch

# 自定义检查间隔（5分钟）
python main.py --watch --interval 300

# 查看统计信息
python main.py --stats

# 清理30天前的记录
python main.py --cleanup 30
```

## 目录结构（已实现）

```
emailmanager/
├── config/
│   ├── __init__.py
│   ├── settings.py          # 统一配置
│   └── categories.py        # 分类规则
├── core/
│   ├── __init__.py
│   ├── email_client.py      # 邮件读取/发送
│   ├── notion_client.py     # Notion API
│   └── state.py             # 状态管理(SQLite)
├── processors/
│   ├── __init__.py
│   ├── classifier.py        # 两阶段分类器
│   └── academic.py          # 学术邮件处理
├── scheduler/
│   ├── __init__.py
│   └── watcher.py           # 定时检查器
├── legacy/                   # 旧代码备份
├── main.py                   # 统一入口
├── state.db                  # 处理状态数据库
├── requirements.txt
└── ARCHITECTURE.md
```

## 实施状态：✅ 已完成

- ✅ Phase 1: 统一配置和核心模块
- ✅ Phase 2: 两阶段分类器
- ✅ Phase 3: 增量处理（state.db）
- ✅ Phase 4: 定时任务
- ✅ Phase 5: 代码清理
