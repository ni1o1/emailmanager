"""
飞书自建应用客户端
通过 App ID + App Secret 获取 tenant_access_token，向指定 chat_id 发送消息
"""

import json
import time
import threading
import requests
from typing import Optional
from dataclasses import dataclass

from core.logger import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 2  # 退避基数（秒）：2, 4, 8

TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
SEND_URL = "https://open.feishu.cn/open-apis/im/v1/messages"


@dataclass
class MessageResult:
    """发送结果"""
    success: bool
    error: Optional[str] = None


class FeishuClient:
    """飞书自建应用消息客户端"""

    def __init__(self, app_id: str = None, app_secret: str = None, chat_id: str = None):
        from config.settings import (
            FEISHU_APP_ID,
            FEISHU_APP_SECRET,
            FEISHU_CHAT_ID,
            FEISHU_ENABLED,
        )

        self.app_id = app_id or FEISHU_APP_ID
        self.app_secret = app_secret or FEISHU_APP_SECRET
        self.chat_id = chat_id or FEISHU_CHAT_ID
        self.enabled = FEISHU_ENABLED

        self._token: Optional[str] = None
        self._token_expire_at: float = 0
        self._token_lock = threading.Lock()

    def _get_token(self) -> Optional[str]:
        """获取 tenant_access_token，自动缓存到过期前 60 秒"""
        with self._token_lock:
            now = time.time()
            if self._token and now < self._token_expire_at - 60:
                return self._token

            try:
                resp = requests.post(
                    TOKEN_URL,
                    json={"app_id": self.app_id, "app_secret": self.app_secret},
                    timeout=15,
                )
                data = resp.json()
                if data.get("code") == 0:
                    self._token = data["tenant_access_token"]
                    self._token_expire_at = now + int(data.get("expire", 7200))
                    return self._token
                logger.warning(f"飞书获取 token 失败: {data}")
                return None
            except Exception as e:
                logger.warning(f"飞书获取 token 异常: {e}")
                return None

    def send(self, message: str) -> MessageResult:
        """发送飞书文本消息（带重试）"""
        if not self.enabled:
            return MessageResult(success=False, error="飞书通知未启用")

        if not self.app_id or not self.app_secret or not self.chat_id:
            return MessageResult(success=False, error="未配置飞书 APP_ID / APP_SECRET / CHAT_ID")

        if not message:
            return MessageResult(success=False, error="消息内容为空")

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            token = self._get_token()
            if not token:
                last_error = "获取 tenant_access_token 失败"
                if attempt < MAX_RETRIES:
                    time.sleep(BACKOFF_BASE ** attempt)
                continue

            try:
                resp = requests.post(
                    f"{SEND_URL}?receive_id_type=chat_id",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "receive_id": self.chat_id,
                        "msg_type": "text",
                        "content": json.dumps({"text": message}, ensure_ascii=False),
                    },
                    timeout=30,
                )
                data = resp.json()
                if data.get("code") == 0:
                    return MessageResult(success=True)

                code = data.get("code")
                msg = data.get("msg", "未知错误")
                # token 过期/失效时清空缓存重试
                if code in (99991663, 99991664, 99991665, 99991668):
                    self._token = None
                    last_error = f"token 失效({code}): {msg}"
                    if attempt < MAX_RETRIES:
                        continue
                # 其他业务错误（如 chat_id 无权限）不重试
                return MessageResult(success=False, error=f"{msg} (code={code})")
            except (requests.Timeout, requests.ConnectionError, requests.exceptions.SSLError) as e:
                last_error = str(e)
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE ** attempt
                    logger.warning(f"飞书发送失败（第{attempt}次），{wait}秒后重试: {last_error}")
                    time.sleep(wait)
            except Exception as e:
                return MessageResult(success=False, error=str(e))

        return MessageResult(success=False, error=f"重试{MAX_RETRIES}次后仍失败: {last_error}")

    def send_silent(self, message: str) -> bool:
        """静默发送（不抛异常）"""
        try:
            return self.send(message).success
        except Exception:
            return False
