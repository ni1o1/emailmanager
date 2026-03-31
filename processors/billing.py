"""
账单处理器
处理信用卡账单、会员订阅等
"""

from typing import Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


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
    """账单处理器（简化版，仅分类不存储）"""

    def __init__(self):
        pass

    def is_billing_email(self, email: Dict) -> bool:
        """判断是否为账单邮件"""
        subject = (email.get("subject") or "").lower()
        from_addr = (email.get("from_lower") or email.get("from", "")).lower()

        for keyword in BILLING_SENDERS.keys():
            if keyword.lower() in from_addr:
                return True

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

        subject = (email.get("subject") or "").lower()
        if any(kw in subject for kw in ["信用卡", "credit card", "账单"]):
            return "credit_card"
        if any(kw in subject for kw in ["会员", "订阅", "membership", "subscription"]):
            return "membership"

        return "other"
