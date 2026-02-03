"""
Pytest 配置和共享 fixtures
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_env_vars():
    """模拟环境变量"""
    env_vars = {
        "KIMI_API_KEY": "sk-test-key-12345678901234567890",
        "NOTION_TOKEN": "secret_test_token_12345",
        "NOTION_PARENT_PAGE_ID": "test-page-id-12345",
        "QQ_EMAIL_ADDRESS": "test@qq.com",
        "QQ_EMAIL_PASSWORD": "test_password",
        "IMESSAGE_ENABLED": "false",
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def sample_email():
    """示例邮件数据"""
    return {
        "message_id": "<test123@example.com>",
        "subject": "Your manuscript PAPER-2024-001 has been received",
        "from": "editor@journal.com",
        "date": "2024-01-15 10:30:00",
        "date_str": "2024-01-15 10:30:00",
        "account": "QQ邮箱",
        "email_id": 12345,
        "body": "Dear Author, Thank you for submitting your manuscript...",
    }


@pytest.fixture
def sample_trash_email():
    """示例垃圾邮件数据"""
    return {
        "message_id": "<spam123@example.com>",
        "subject": "阿里云ECS服务器到期提醒",
        "from": "aliyun@aliyun.com",
        "date": "2024-01-15 10:30:00",
        "account": "QQ邮箱",
        "email_id": 12346,
    }


@pytest.fixture
def sample_billing_email():
    """示例账单邮件"""
    return {
        "message_id": "<bill123@example.com>",
        "subject": "招商银行信用卡电子账单",
        "from": "creditcard@cmbchina.com",
        "date": "2024-01-15",
        "account": "QQ邮箱",
        "email_id": 12347,
        "body": "您的本期账单金额为 1234.56 元，还款日为 2024-02-05",
    }


@pytest.fixture
def sample_review_email():
    """示例审稿邮件"""
    return {
        "message_id": "<review123@example.com>",
        "subject": "Invitation to review for Journal of Urban Planning",
        "from": "editor@journal.com",
        "date": "2024-01-15",
        "account": "PKU邮箱",
        "email_id": 12348,
        "body": "Dear Dr. Yu, We would like to invite you to review a manuscript...",
    }


@pytest.fixture
def mock_llm_response():
    """模拟 LLM 响应"""
    def _mock_response(content):
        return MagicMock(
            json=lambda: {
                "choices": [{"message": {"content": content}}],
                "usage": {"total_tokens": 100}
            },
            status_code=200
        )
    return _mock_response


@pytest.fixture
def mock_notion_response():
    """模拟 Notion API 响应"""
    def _mock_response(data=None):
        if data is None:
            data = {"id": "test-page-id", "object": "page"}
        return MagicMock(
            json=lambda: data,
            status_code=200
        )
    return _mock_response
