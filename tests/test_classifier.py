"""
测试邮件分类器
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from processors.classifier import EmailClassifier, extract_json_from_text


class TestExtractJsonFromText:
    """测试 JSON 提取函数"""

    def test_bare_json_object(self):
        """测试裸 JSON 对象"""
        text = '{"category": "PAPER", "id": 1}'
        result = extract_json_from_text(text)
        assert result is not None
        assert result["category"] == "PAPER"
        assert result["id"] == 1

    def test_bare_json_array(self):
        """测试裸 JSON 数组"""
        text = '[{"id": 1, "category": "PAPER"}, {"id": 2, "category": "TRASH"}]'
        result = extract_json_from_text(text, expect_array=True)
        assert result is not None
        assert len(result) == 2
        assert result[0]["category"] == "PAPER"

    def test_markdown_code_block(self):
        """测试 Markdown 代码块中的 JSON"""
        text = '''Here is the result:
```json
{"category": "BILLING", "importance": 3}
```
'''
        result = extract_json_from_text(text)
        assert result is not None
        assert result["category"] == "BILLING"

    def test_json_with_surrounding_text(self):
        """测试带有周围文本的 JSON"""
        text = 'Based on my analysis, the result is {"category": "NOTICE"} and that is my conclusion.'
        result = extract_json_from_text(text)
        assert result is not None
        assert result["category"] == "NOTICE"

    def test_nested_json(self):
        """测试嵌套 JSON"""
        text = '{"item": {"title": "Test", "status": "pending"}, "classification": {"category": "PAPER"}}'
        result = extract_json_from_text(text)
        assert result is not None
        assert result["item"]["title"] == "Test"
        assert result["classification"]["category"] == "PAPER"

    def test_invalid_json(self):
        """测试无效 JSON"""
        text = "This is not JSON at all"
        result = extract_json_from_text(text)
        assert result is None

    def test_empty_string(self):
        """测试空字符串"""
        result = extract_json_from_text("")
        assert result is None

    def test_none_input(self):
        """测试 None 输入"""
        result = extract_json_from_text(None)
        assert result is None


class TestEmailClassifier:
    """测试邮件分类器"""

    @pytest.fixture
    def classifier(self):
        """创建分类器实例"""
        return EmailClassifier()

    def test_classifier_categories(self, classifier):
        """测试分类器常量"""
        assert classifier.CATEGORY_TRASH == "TRASH"
        assert classifier.CATEGORY_PAPER == "PAPER"
        assert classifier.CATEGORY_REVIEW == "REVIEW"
        assert classifier.CATEGORY_BILLING == "BILLING"
        assert classifier.CATEGORY_NOTICE == "NOTICE"
        assert classifier.CATEGORY_EXAM == "EXAM"
        assert classifier.CATEGORY_PERSONAL == "PERSONAL"
        assert classifier.CATEGORY_UNKNOWN == "UNKNOWN"

    def test_stage1_classify_batch_empty(self, classifier):
        """测试空邮件列表"""
        result = classifier.stage1_classify_batch([])
        assert result == []

    @patch.object(EmailClassifier, '_call_llm')
    def test_stage1_classify_batch_success(self, mock_llm, classifier, sample_email):
        """测试批量分类成功"""
        mock_llm.return_value = json.dumps([
            {"id": 1, "category": "PAPER"}
        ])

        emails = [sample_email]
        result = classifier.stage1_classify_batch(emails)

        assert len(result) == 1
        assert result[0]["_stage1_category"] == "PAPER"

    @patch.object(EmailClassifier, '_call_llm')
    def test_stage1_classify_batch_llm_error(self, mock_llm, classifier, sample_email):
        """测试 LLM 调用失败时的处理"""
        mock_llm.side_effect = Exception("API Error")

        emails = [sample_email]
        result = classifier.stage1_classify_batch(emails)

        assert len(result) == 1
        assert result[0]["_stage1_category"] == "UNKNOWN"

    @patch.object(EmailClassifier, '_call_llm')
    def test_stage1_classify_batch_invalid_json(self, mock_llm, classifier, sample_email):
        """测试 JSON 解析失败时的处理"""
        mock_llm.return_value = "Invalid JSON response"

        emails = [sample_email]
        result = classifier.stage1_classify_batch(emails)

        assert len(result) == 1
        assert result[0]["_stage1_category"] == "UNKNOWN"

    def test_stage2_analyze_content_empty(self, classifier):
        """测试空邮件列表"""
        result = classifier.stage2_analyze_content([])
        assert result == {"items": [], "classifications": []}

    @patch.object(EmailClassifier, '_call_llm')
    def test_stage2_analyze_content_success(self, mock_llm, classifier, sample_email):
        """测试内容分析成功"""
        mock_llm.return_value = json.dumps({
            "item": {
                "category": "Paper",
                "title": "Test Paper",
                "manuscript_id": "PAPER-2024-001",
                "status": "received"
            },
            "classification": {
                "category": "Paper/Submission",
                "importance": 4,
                "needs_action": False,
                "summary": "稿件已收到"
            }
        })

        emails = [sample_email]
        result = classifier.stage2_analyze_content(emails)

        assert len(result["items"]) == 1
        assert len(result["classifications"]) == 1
        assert result["items"][0]["title"] == "Test Paper"
        assert emails[0]["_importance"] == 4


class TestClassifierIntegration:
    """集成测试（需要 mock 外部依赖）"""

    @patch.object(EmailClassifier, '_call_llm')
    def test_full_classification_flow(self, mock_llm, sample_email, sample_trash_email):
        """测试完整分类流程"""
        classifier = EmailClassifier()

        # Stage 1 响应
        mock_llm.return_value = json.dumps([
            {"id": 1, "category": "PAPER"},
            {"id": 2, "category": "TRASH"}
        ])

        emails = [sample_email, sample_trash_email]
        classifier.stage1_classify_batch(emails)

        assert emails[0]["_stage1_category"] == "PAPER"
        assert emails[1]["_stage1_category"] == "TRASH"
