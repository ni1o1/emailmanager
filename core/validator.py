"""
配置验证器

在程序启动时验证必要的配置项，避免运行时错误
"""

import os
from typing import List, Tuple
from dataclasses import dataclass

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class ConfigValidator:
    """配置验证器"""

    # 必填配置项
    REQUIRED_FIELDS = [
        ("KIMI_API_KEY", "Kimi LLM API 密钥"),
        ("NOTION_TOKEN", "Notion API Token"),
        ("NOTION_PARENT_PAGE_ID", "Notion 父页面 ID"),
    ]

    # 至少需要一个邮箱账户
    EMAIL_ACCOUNT_PAIRS = [
        ("QQ_EMAIL_ADDRESS", "QQ_EMAIL_PASSWORD", "QQ邮箱"),
        ("PKU_EMAIL_ADDRESS", "PKU_EMAIL_PASSWORD", "PKU邮箱"),
    ]

    # 可选但建议配置的项
    OPTIONAL_FIELDS = [
        ("IMESSAGE_RECIPIENT", "iMessage 接收者（启用通知时需要）"),
    ]

    @classmethod
    def validate(cls) -> ValidationResult:
        """
        验证配置

        Returns:
            ValidationResult 包含验证结果、错误和警告信息
        """
        errors = []
        warnings = []

        # 验证必填项
        for env_name, description in cls.REQUIRED_FIELDS:
            value = os.getenv(env_name, "").strip()
            if not value:
                errors.append(f"缺少必填配置 {env_name}: {description}")

        # 验证至少有一个邮箱账户
        has_email_account = False
        for addr_key, pwd_key, name in cls.EMAIL_ACCOUNT_PAIRS:
            addr = os.getenv(addr_key, "").strip()
            pwd = os.getenv(pwd_key, "").strip()
            if addr and pwd:
                has_email_account = True
                logger.debug(f"已配置邮箱账户: {name}")
            elif addr and not pwd:
                errors.append(f"{name}已配置地址但缺少密码 ({pwd_key})")
            elif pwd and not addr:
                errors.append(f"{name}已配置密码但缺少地址 ({addr_key})")

        if not has_email_account:
            errors.append("至少需要配置一个邮箱账户（QQ邮箱或PKU邮箱）")

        # 检查 iMessage 配置
        imessage_enabled = os.getenv("IMESSAGE_ENABLED", "false").lower() == "true"
        imessage_recipient = os.getenv("IMESSAGE_RECIPIENT", "").strip()
        if imessage_enabled and not imessage_recipient:
            warnings.append("iMessage 已启用但未配置接收者 (IMESSAGE_RECIPIENT)")

        # 检查静默时段格式
        quiet_hours = os.getenv("IMESSAGE_QUIET_HOURS", "").strip()
        if quiet_hours:
            if not cls._validate_quiet_hours_format(quiet_hours):
                warnings.append(f"静默时段格式错误: {quiet_hours}，应为 HH:MM-HH:MM")

        # 检查 API Key 格式（基本检查）
        kimi_key = os.getenv("KIMI_API_KEY", "").strip()
        if kimi_key and len(kimi_key) < 20:
            warnings.append("KIMI_API_KEY 看起来太短，请确认是否正确")

        notion_token = os.getenv("NOTION_TOKEN", "").strip()
        if notion_token and not notion_token.startswith("secret_"):
            warnings.append("NOTION_TOKEN 通常以 'secret_' 开头，请确认是否正确")

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )

    @classmethod
    def _validate_quiet_hours_format(cls, value: str) -> bool:
        """验证静默时段格式"""
        try:
            parts = value.split("-")
            if len(parts) != 2:
                return False
            for part in parts:
                hours, minutes = part.split(":")
                h = int(hours)
                m = int(minutes)
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    return False
            return True
        except (ValueError, AttributeError):
            return False

    @classmethod
    def validate_and_report(cls) -> bool:
        """
        验证配置并输出报告

        Returns:
            True 如果配置有效，False 如果有错误
        """
        result = cls.validate()

        if result.errors:
            logger.error("=" * 50)
            logger.error("配置验证失败！")
            logger.error("=" * 50)
            for error in result.errors:
                logger.error(f"  [ERROR] {error}")

        if result.warnings:
            for warning in result.warnings:
                logger.warning(f"  [WARN] {warning}")

        if result.is_valid:
            logger.info("配置验证通过")

        return result.is_valid


def require_valid_config():
    """
    要求有效配置，否则退出程序

    在程序入口处调用此函数
    """
    import sys

    if not ConfigValidator.validate_and_report():
        logger.error("请检查 .env 文件中的配置项")
        logger.error("参考 .env.example 获取配置示例")
        sys.exit(1)
