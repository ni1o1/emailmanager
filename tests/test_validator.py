"""
测试配置验证器
"""

import pytest
import os
from unittest.mock import patch

from core.validator import ConfigValidator, ValidationResult


class TestConfigValidator:
    """测试配置验证器"""

    def test_validate_all_required_fields_present(self, mock_env_vars):
        """测试所有必填字段都存在"""
        result = ConfigValidator.validate()
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_missing_kimi_api_key(self):
        """测试缺少 KIMI_API_KEY"""
        env_vars = {
            "NOTION_TOKEN": "secret_test_token",
            "NOTION_PARENT_PAGE_ID": "test-page-id",
            "QQ_EMAIL_ADDRESS": "test@qq.com",
            "QQ_EMAIL_PASSWORD": "password",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            result = ConfigValidator.validate()
            assert result.is_valid is False
            assert any("KIMI_API_KEY" in e for e in result.errors)

    def test_validate_missing_notion_token(self):
        """测试缺少 NOTION_TOKEN"""
        env_vars = {
            "KIMI_API_KEY": "sk-test-key-12345678901234567890",
            "NOTION_PARENT_PAGE_ID": "test-page-id",
            "QQ_EMAIL_ADDRESS": "test@qq.com",
            "QQ_EMAIL_PASSWORD": "password",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            result = ConfigValidator.validate()
            assert result.is_valid is False
            assert any("NOTION_TOKEN" in e for e in result.errors)

    def test_validate_no_email_account(self):
        """测试没有配置任何邮箱账户"""
        env_vars = {
            "KIMI_API_KEY": "sk-test-key-12345678901234567890",
            "NOTION_TOKEN": "secret_test_token",
            "NOTION_PARENT_PAGE_ID": "test-page-id",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            result = ConfigValidator.validate()
            assert result.is_valid is False
            assert any("邮箱账户" in e for e in result.errors)

    def test_validate_email_address_without_password(self):
        """测试有邮箱地址但没有密码"""
        env_vars = {
            "KIMI_API_KEY": "sk-test-key-12345678901234567890",
            "NOTION_TOKEN": "secret_test_token",
            "NOTION_PARENT_PAGE_ID": "test-page-id",
            "QQ_EMAIL_ADDRESS": "test@qq.com",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            result = ConfigValidator.validate()
            assert result.is_valid is False
            assert any("缺少密码" in e for e in result.errors)

    def test_validate_imessage_enabled_without_recipient(self, mock_env_vars):
        """测试 iMessage 启用但没有接收者"""
        with patch.dict(os.environ, {"IMESSAGE_ENABLED": "true", "IMESSAGE_RECIPIENT": ""}):
            result = ConfigValidator.validate()
            # 应该是警告而不是错误
            assert result.is_valid is True
            assert any("IMESSAGE_RECIPIENT" in w for w in result.warnings)

    def test_validate_quiet_hours_format_valid(self):
        """测试有效的静默时段格式"""
        assert ConfigValidator._validate_quiet_hours_format("23:00-07:00") is True
        assert ConfigValidator._validate_quiet_hours_format("00:00-23:59") is True
        assert ConfigValidator._validate_quiet_hours_format("12:30-18:45") is True

    def test_validate_quiet_hours_format_invalid(self):
        """测试无效的静默时段格式"""
        assert ConfigValidator._validate_quiet_hours_format("invalid") is False
        assert ConfigValidator._validate_quiet_hours_format("25:00-07:00") is False
        assert ConfigValidator._validate_quiet_hours_format("23:60-07:00") is False
        assert ConfigValidator._validate_quiet_hours_format("23:00") is False
        assert ConfigValidator._validate_quiet_hours_format("") is False

    def test_validate_short_api_key_warning(self, mock_env_vars):
        """测试过短的 API Key 产生警告"""
        with patch.dict(os.environ, {"KIMI_API_KEY": "short"}):
            result = ConfigValidator.validate()
            # 应该有警告
            assert any("太短" in w for w in result.warnings)

    def test_validate_notion_token_format_warning(self, mock_env_vars):
        """测试 Notion Token 格式警告"""
        with patch.dict(os.environ, {"NOTION_TOKEN": "not_starting_with_secret"}):
            result = ConfigValidator.validate()
            assert any("secret_" in w for w in result.warnings)

    def test_validation_result_dataclass(self):
        """测试 ValidationResult 数据类"""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["Test warning"]
        )
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
