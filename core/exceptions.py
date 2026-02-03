"""
统一异常定义

所有自定义异常都继承自 EmailManagerError
便于统一捕获和处理
"""

from typing import Optional


class EmailManagerError(Exception):
    """
    Email Manager 基础异常类

    所有自定义异常都应继承此类
    """

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self):
        if self.details:
            return f"{self.message} | 详情: {self.details}"
        return self.message


class LLMError(EmailManagerError):
    """
    LLM 调用异常

    用于 Kimi API 调用失败时
    """

    def __init__(
        self,
        message: str,
        retry_count: int = 0,
        timeout: bool = False,
        response_code: Optional[int] = None,
    ):
        details = {
            "retry_count": retry_count,
            "timeout": timeout,
        }
        if response_code:
            details["response_code"] = response_code
        super().__init__(message, details)
        self.retry_count = retry_count
        self.timeout = timeout
        self.response_code = response_code


class NotionError(EmailManagerError):
    """
    Notion API 异常

    用于 Notion 同步失败时
    """

    def __init__(
        self,
        message: str,
        page_id: Optional[str] = None,
        database_id: Optional[str] = None,
        api_code: Optional[str] = None,
    ):
        details = {}
        if page_id:
            details["page_id"] = page_id
        if database_id:
            details["database_id"] = database_id
        if api_code:
            details["api_code"] = api_code
        super().__init__(message, details)
        self.page_id = page_id
        self.database_id = database_id
        self.api_code = api_code


class EmailFetchError(EmailManagerError):
    """
    邮件获取异常

    用于 IMAP 连接或邮件获取失败时
    """

    def __init__(
        self,
        message: str,
        account: Optional[str] = None,
        imap_error: Optional[str] = None,
    ):
        details = {}
        if account:
            details["account"] = account
        if imap_error:
            details["imap_error"] = imap_error
        super().__init__(message, details)
        self.account = account
        self.imap_error = imap_error


class ConfigurationError(EmailManagerError):
    """
    配置错误异常

    用于配置验证失败时
    """

    def __init__(self, message: str, missing_fields: Optional[list] = None):
        details = {}
        if missing_fields:
            details["missing_fields"] = missing_fields
        super().__init__(message, details)
        self.missing_fields = missing_fields or []


class ClassificationError(EmailManagerError):
    """
    分类异常

    用于邮件分类失败时
    """

    def __init__(
        self,
        message: str,
        stage: int = 1,
        email_count: int = 0,
    ):
        details = {
            "stage": stage,
            "email_count": email_count,
        }
        super().__init__(message, details)
        self.stage = stage
        self.email_count = email_count


class NotificationError(EmailManagerError):
    """
    通知发送异常

    用于 iMessage 发送失败时
    """

    def __init__(
        self,
        message: str,
        recipient: Optional[str] = None,
    ):
        details = {}
        if recipient:
            # 脱敏处理
            details["recipient"] = recipient[:3] + "***"
        super().__init__(message, details)
        self.recipient = recipient


def handle_exception(func):
    """
    异常处理装饰器

    统一捕获和记录异常

    用法:
        @handle_exception
        def some_function():
            ...
    """
    import functools
    from core.logger import get_logger

    logger = get_logger(func.__module__)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except EmailManagerError as e:
            logger.error(f"{func.__name__} 失败: {e}")
            raise
        except Exception as e:
            logger.exception(f"{func.__name__} 发生未预期错误: {e}")
            raise EmailManagerError(f"未预期错误: {e}") from e

    return wrapper
