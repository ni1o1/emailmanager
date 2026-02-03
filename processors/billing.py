"""
账单处理器
处理信用卡账单、会员订阅等
"""

import re
import json
import requests
from typing import Dict, List, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import KIMI_API_URL, KIMI_API_KEY, KIMI_MODEL, KIMI_TIMEOUT, NOTION_PARENT_PAGE_ID
from core.billing_db import BillingDB
from core.notion_client import NotionClient


# 账单类型
BILLING_TYPES = {
    "credit_card": "信用卡",
    "membership": "会员订阅",
    "utility": "水电燃气",
    "insurance": "保险",
    "loan": "贷款",
    "other": "其他",
}

# 已知的账单发件人关键词
BILLING_SENDERS = {
    # 信用卡
    "招商银行": "credit_card",
    "工商银行": "credit_card",
    "建设银行": "credit_card",
    "交通银行": "credit_card",
    "中国银行": "credit_card",
    "农业银行": "credit_card",
    "浦发银行": "credit_card",
    "中信银行": "credit_card",
    "民生银行": "credit_card",
    "光大银行": "credit_card",
    "平安银行": "credit_card",
    "广发银行": "credit_card",
    "citibank": "credit_card",
    "hsbc": "credit_card",
    # 会员
    "netflix": "membership",
    "spotify": "membership",
    "youtube": "membership",
    "apple": "membership",
    "microsoft": "membership",
    "adobe": "membership",
    "dropbox": "membership",
    "notion": "membership",
    "openai": "membership",
    # 航空里程
    "东方航空": "membership",
    "南方航空": "membership",
    "国航": "membership",
    "海航": "membership",
}


class BillingProcessor:
    """账单处理器"""

    def __init__(self, billing_db: BillingDB = None, notion: NotionClient = None):
        self.db = billing_db or BillingDB()
        self.notion = notion or NotionClient()
        self._notion_db_id = None

        self.session = requests.Session()
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)

    def is_billing_email(self, email: Dict) -> bool:
        """判断是否为账单邮件"""
        subject = (email.get("subject") or "").lower()
        from_addr = (email.get("from_lower") or email.get("from", "")).lower()

        # 检查发件人
        for keyword in BILLING_SENDERS.keys():
            if keyword.lower() in from_addr:
                return True

        # 检查标题关键词
        billing_keywords = [
            "账单", "对账单", "还款", "信用卡", "消费提醒",
            "会员", "订阅", "续费", "invoice", "billing", "statement",
            "payment", "subscription", "membership",
        ]
        return any(kw in subject for kw in billing_keywords)

    def detect_billing_type(self, email: Dict) -> Optional[str]:
        """检测账单类型"""
        from_addr = (email.get("from_lower") or "").lower()

        for keyword, bill_type in BILLING_SENDERS.items():
            if keyword.lower() in from_addr:
                return bill_type

        # 根据标题推断
        subject = (email.get("subject") or "").lower()
        if any(kw in subject for kw in ["信用卡", "credit card", "账单"]):
            return "credit_card"
        if any(kw in subject for kw in ["会员", "订阅", "membership", "subscription"]):
            return "membership"

        return "other"

    def parse_billing_emails(self, emails: List[Dict]) -> List[Dict]:
        """解析账单邮件，提取结构化信息"""
        if not emails:
            return []

        # 准备邮件摘要
        email_summaries = []
        for i, mail in enumerate(emails[:10], 1):
            body = (mail.get("body") or "")[:800]
            summary = f"{i}. 标题: {mail['subject'][:150]}\n   发件人: {mail['from'][:80]}\n   时间: {mail.get('date_str', '未知')}\n   内容: {body}"
            email_summaries.append(summary)

        email_text = "\n\n".join(email_summaries)

        prompt = f"""请分析以下账单相关邮件，提取结构化信息。

【任务】
1. 识别账单条目（信用卡、会员订阅等）
2. 提取账单金额、账期、还款日期
3. 同一账户的多封邮件应该合并

【输出JSON格式】
{{
    "items": [
        {{
            "name": "账户名称（如：招商银行信用卡、Netflix会员）",
            "type": "credit_card/membership/utility/other",
            "period": "账期（如 2026-01）",
            "amount": 金额（数字）,
            "currency": "CNY/USD",
            "due_date": "还款日期 YYYY-MM-DD",
            "status": "pending/paid",
            "source_emails": [对应邮件编号],
            "notes": "备注"
        }}
    ],
    "summary": "一句话总结"
}}

邮件列表：
{email_text}"""

        headers = {
            "Authorization": f"Bearer {KIMI_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": KIMI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 1
        }

        try:
            response = self.session.post(
                KIMI_API_URL,
                headers=headers,
                json=data,
                timeout=KIMI_TIMEOUT
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                parsed = json.loads(json_match.group())
                return parsed.get("items", [])

        except Exception as e:
            print(f"   ⚠️ 解析账单失败: {e}")

        return []

    def process(self, billing_items: List[Dict]) -> Dict:
        """
        处理账单项目：更新本地数据库，同步到Notion

        Args:
            billing_items: 解析出的账单项目列表

        Returns:
            处理结果统计
        """
        new_items = 0
        updated_records = 0
        synced_to_notion = 0

        for item in billing_items:
            name = item.get("name", "").strip()
            if not name:
                continue

            bill_type = item.get("type", "other")
            period = item.get("period", "")
            amount = item.get("amount")
            due_date = item.get("due_date")
            status = item.get("status", "pending")

            # 1. 获取或创建条目
            item_id = self.db.get_or_create_item(
                name=name,
                item_type=bill_type,
                amount=amount,
                currency=item.get("currency", "CNY"),
            )

            # 检查是否新创建
            db_item = self.db.get_item_by_name(name)
            if db_item and not db_item.get("notion_page_id"):
                new_items += 1

            # 2. 添加/更新账单记录
            if period:
                record_id, is_new, has_changes = self.db.add_or_update_record(
                    item_id=item_id,
                    period=period,
                    amount=amount,
                    due_date=due_date,
                    status=status,
                    notes=item.get("notes"),
                )

                if is_new or has_changes:
                    updated_records += 1

            # 3. 每个账单项目都尝试同步到Notion（无论是否有period）
            try:
                # 重新获取db_item确保有最新数据
                db_item = self.db.get_item_by_name(name)
                if self._sync_to_notion(db_item, item, period or ""):
                    synced_to_notion += 1
            except Exception as e:
                print(f"      ⚠️ 同步账单到Notion失败 ({name}): {e}")

        return {
            "new_items": new_items,
            "updated_records": updated_records,
            "synced_to_notion": synced_to_notion,
        }

    def _get_notion_db(self) -> Optional[str]:
        """获取或创建Notion账单数据库"""
        if self._notion_db_id:
            return self._notion_db_id

        db_id = self.notion.find_database("账单管理")
        if db_id:
            self._notion_db_id = db_id
            return db_id

        # 创建数据库（使用统一的父页面）
        parent_id = NOTION_PARENT_PAGE_ID
        db_data = {
            "parent": {"type": "page_id", "page_id": parent_id},
            "title": [{"type": "text", "text": {"content": "💳 账单管理"}}],
            "properties": {
                "名称": {"title": {}},
                "类型": {
                    "select": {
                        "options": [
                            {"name": "信用卡", "color": "blue"},
                            {"name": "会员订阅", "color": "purple"},
                            {"name": "水电燃气", "color": "yellow"},
                            {"name": "保险", "color": "green"},
                            {"name": "其他", "color": "gray"},
                        ]
                    }
                },
                "当期金额": {"number": {"format": "number"}},
                "账期": {"rich_text": {}},
                "还款日": {"date": {}},
                "状态": {
                    "select": {
                        "options": [
                            {"name": "待还款", "color": "red"},
                            {"name": "已还款", "color": "green"},
                        ]
                    }
                },
                "备注": {"rich_text": {}},
            }
        }

        result = self.notion._request("POST", "/databases", db_data)
        if "id" in result:
            self._notion_db_id = result["id"]
            print(f"   ✓ 创建账单数据库: {result['id']}")
            return result["id"]
        return None

    def _sync_to_notion(self, db_item: Dict, billing_item: Dict, period: str) -> bool:
        """同步账单到Notion"""
        db_id = self._get_notion_db()
        if not db_id:
            return False

        name = billing_item.get("name", "未知")
        bill_type = billing_item.get("type", "other")
        type_name = BILLING_TYPES.get(bill_type, "其他")

        # 构建页面数据
        page_data = {
            "parent": {"database_id": db_id},
            "properties": {
                "名称": {"title": [{"text": {"content": name}}]},
                "类型": {"select": {"name": type_name}},
                "账期": {"rich_text": [{"text": {"content": period}}]},
                "状态": {"select": {"name": "待还款" if billing_item.get("status") == "pending" else "已还款"}},
            }
        }

        if billing_item.get("amount"):
            page_data["properties"]["当期金额"] = {"number": billing_item["amount"]}

        if billing_item.get("due_date"):
            page_data["properties"]["还款日"] = {"date": {"start": billing_item["due_date"]}}

        if billing_item.get("notes"):
            page_data["properties"]["备注"] = {"rich_text": [{"text": {"content": billing_item["notes"][:500]}}]}

        # 查找是否已存在（按名称+账期）
        existing = self._find_existing_record(db_id, name, period)

        if existing:
            # 更新
            result = self.notion._request("PATCH", f"/pages/{existing}", page_data)
        else:
            # 创建
            result = self.notion._request("POST", "/pages", page_data)

        if "id" in result:
            # 更新本地数据库的Notion ID
            if db_item and db_item.get("id"):
                self.db.update_item_notion_id(db_item["id"], result["id"])
            return True

        return False

    def _find_existing_record(self, db_id: str, name: str, period: str) -> Optional[str]:
        """查找现有记录（使用精确匹配）"""
        result = self.notion._request("POST", f"/databases/{db_id}/query", {
            "filter": {
                "and": [
                    {"property": "名称", "title": {"equals": name}},
                    {"property": "账期", "rich_text": {"equals": period}},
                ]
            }
        })

        if result.get("results"):
            return result["results"][0]["id"]
        return None
