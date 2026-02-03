"""
iMessage 发送客户端
通过 AppleScript 在 macOS 上发送 iMessage
"""

import subprocess
import platform
from typing import Optional
from dataclasses import dataclass


@dataclass
class MessageResult:
    """发送结果"""
    success: bool
    error: Optional[str] = None


class iMessageClient:
    """iMessage 发送客户端"""

    def __init__(self, recipient: str = None, sender: str = None):
        """
        初始化 iMessage 客户端

        Args:
            recipient: 收件人（手机号或 Apple ID）
                      如不指定，使用配置文件中的默认值
            sender: 发送账号（Apple ID 邮箱）
                   如不指定，使用配置文件中的默认值
        """
        # 延迟导入配置，避免循环依赖
        from config.settings import IMESSAGE_ENABLED, IMESSAGE_RECIPIENT

        self.recipient = recipient or IMESSAGE_RECIPIENT
        self.enabled = IMESSAGE_ENABLED

        # 发送账号（需要在 Mac 的信息 App 中登录此账号）
        import os
        self.sender = sender or os.getenv("IMESSAGE_SENDER", "")

    def is_available(self) -> bool:
        """
        检查 iMessage 是否可用

        Returns:
            True if macOS and Messages.app is available
        """
        if platform.system() != "Darwin":
            return False

        # 检查 Messages.app 是否存在
        try:
            result = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to return exists application process "Messages"'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def send(self, message: str) -> MessageResult:
        """
        发送 iMessage

        Args:
            message: 消息内容

        Returns:
            MessageResult 包含成功状态和可能的错误信息
        """
        if not self.enabled:
            return MessageResult(success=False, error="iMessage 通知未启用")

        if not self.recipient:
            return MessageResult(success=False, error="未配置收件人")

        if not message:
            return MessageResult(success=False, error="消息内容为空")

        # 转义消息内容中的特殊字符
        escaped_message = self._escape_for_applescript(message)
        escaped_recipient = self._escape_for_applescript(self.recipient)

        # AppleScript 脚本
        # 如果指定了发送账号ID，使用该账号发送
        if self.sender:
            escaped_sender = self._escape_for_applescript(self.sender)
            applescript = f'''
tell application "Messages"
    set targetService to account id "{escaped_sender}"
    set targetBuddy to participant "{escaped_recipient}" of targetService
    send "{escaped_message}" to targetBuddy
end tell
'''
        else:
            applescript = f'''
tell application "Messages"
    set targetService to 1st account whose service type = iMessage
    set targetBuddy to participant "{escaped_recipient}" of targetService
    send "{escaped_message}" to targetBuddy
end tell
'''

        try:
            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return MessageResult(success=True)
            else:
                error_msg = result.stderr.strip() or "未知错误"
                return MessageResult(success=False, error=error_msg)

        except subprocess.TimeoutExpired:
            return MessageResult(success=False, error="发送超时")
        except Exception as e:
            return MessageResult(success=False, error=str(e))

    def send_silent(self, message: str) -> bool:
        """
        静默发送（不抛异常）

        Args:
            message: 消息内容

        Returns:
            是否发送成功
        """
        try:
            result = self.send(message)
            return result.success
        except Exception:
            return False

    @staticmethod
    def _escape_for_applescript(text: str) -> str:
        """
        转义 AppleScript 字符串中的特殊字符

        Args:
            text: 原始文本

        Returns:
            转义后的文本
        """
        # AppleScript 字符串需要转义反斜杠和双引号
        return text.replace("\\", "\\\\").replace('"', '\\"')
