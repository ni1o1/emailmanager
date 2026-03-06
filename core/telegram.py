"""
Telegram Bot 发送客户端
通过 Telegram Bot API 发送通知消息
"""

import requests
from typing import Optional
from dataclasses import dataclass


@dataclass
class MessageResult:
    """发送结果"""
    success: bool
    error: Optional[str] = None


class TelegramClient:
    """Telegram Bot 发送客户端"""

    def __init__(self, token: str = None, chat_id: str = None):
        from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED

        self.token = token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.enabled = TELEGRAM_ENABLED
        self.api_base = f"https://api.telegram.org/bot{self.token}"

        # 代理设置（从环境变量读取）
        import os
        proxy = os.getenv("TELEGRAM_PROXY", "")
        self.proxies = {"https": proxy, "http": proxy} if proxy else None

    def send(self, message: str) -> MessageResult:
        """发送 Telegram 消息"""
        if not self.enabled:
            return MessageResult(success=False, error="Telegram 通知未启用")

        if not self.token or not self.chat_id:
            return MessageResult(success=False, error="未配置 Telegram Bot Token 或 Chat ID")

        if not message:
            return MessageResult(success=False, error="消息内容为空")

        try:
            resp = requests.post(
                f"{self.api_base}/sendMessage",
                json={"chat_id": self.chat_id, "text": message},
                timeout=30,
                proxies=self.proxies,
            )
            data = resp.json()
            if data.get("ok"):
                return MessageResult(success=True)
            else:
                return MessageResult(success=False, error=data.get("description", "未知错误"))
        except requests.Timeout:
            return MessageResult(success=False, error="发送超时（30秒）")
        except Exception as e:
            return MessageResult(success=False, error=str(e))

    def send_silent(self, message: str) -> bool:
        """静默发送（不抛异常）"""
        try:
            result = self.send(message)
            return result.success
        except Exception:
            return False
