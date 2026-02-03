"""
两阶段邮件分类器（LLM驱动）
Stage 1: LLM分析标题+发件人判断分类
Stage 2: 如果标题无法判断，LLM分析邮件内容
"""

import re
import json
import time
import requests
from typing import Dict, List, Optional, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import KIMI_API_URL, KIMI_API_KEY, KIMI_MODEL, KIMI_TIMEOUT
from config.prompts import get_stage1_prompt, get_stage2_prompt
from core.logger import get_logger
from core.exceptions import LLMError, ClassificationError

logger = get_logger(__name__)


def extract_json_from_text(text: str, expect_array: bool = False) -> Optional[Any]:
    """
    从文本中提取 JSON，更健壮的实现

    Args:
        text: 包含 JSON 的文本
        expect_array: 是否期望数组格式

    Returns:
        解析后的 JSON 对象，或 None
    """
    if not text:
        return None

    # 尝试直接解析（如果整个文本就是 JSON）
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 查找 markdown 代码块中的 JSON
    code_block_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    code_blocks = re.findall(code_block_pattern, text)
    for block in code_blocks:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue

    # 查找数组或对象
    if expect_array:
        # 查找最外层的数组
        array_match = re.search(r'\[[\s\S]*\]', text)
        if array_match:
            try:
                return json.loads(array_match.group())
            except json.JSONDecodeError:
                pass
    else:
        # 查找最外层的对象（处理嵌套情况）
        # 找到第一个 { 和最后一个 }
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace > first_brace:
            json_str = text[first_brace:last_brace + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

    return None


class EmailClassifier:
    """两阶段LLM邮件分类器"""

    # Stage 1 分类结果
    CATEGORY_TRASH = "TRASH"           # 垃圾邮件（不同步）
    CATEGORY_PAPER = "PAPER"           # 我的论文投稿
    CATEGORY_REVIEW = "REVIEW"         # 审稿任务
    CATEGORY_BILLING = "BILLING"       # 账单相关
    CATEGORY_NOTICE = "NOTICE"         # 通知公告
    CATEGORY_EXAM = "EXAM"             # 考试相关
    CATEGORY_PERSONAL = "PERSONAL"     # 个人邮件
    CATEGORY_UNKNOWN = "UNKNOWN"       # 需要进一步分析

    def __init__(self):
        self.session = requests.Session()
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)

    def _call_llm(self, system_prompt: str, user_prompt: str, timeout: int = None) -> str:
        """调用LLM"""
        headers = {
            "Authorization": f"Bearer {KIMI_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": KIMI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 1
        }

        start_time = time.time()
        try:
            response = self.session.post(
                KIMI_API_URL,
                headers=headers,
                json=data,
                timeout=timeout or KIMI_TIMEOUT
            )
            response.raise_for_status()

            result = response.json()
            duration = time.time() - start_time

            # 记录 token 使用情况
            usage = result.get("usage", {})
            logger.debug(f"LLM调用成功: {duration:.2f}s, tokens: {usage.get('total_tokens', 'N/A')}")

            return result["choices"][0]["message"]["content"]
        except requests.Timeout:
            duration = time.time() - start_time
            logger.error(f"LLM调用超时: {duration:.2f}s")
            raise LLMError("LLM调用超时", timeout=True)
        except requests.RequestException as e:
            duration = time.time() - start_time
            response_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            logger.error(f"LLM调用失败: {duration:.2f}s, 错误: {e}")
            raise LLMError(f"LLM请求失败: {e}", response_code=response_code)

    def stage1_classify_batch(self, emails: List[Dict], batch_size: int = 10) -> List[Dict]:
        """Stage 1: 批量分析邮件标题"""
        if not emails:
            return []

        total = len(emails)
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch = emails[batch_start:batch_end]
            logger.info(f"Stage 1: 处理 {batch_start+1}-{batch_end}/{total} 封邮件...")
            self._classify_batch_internal(batch)

        return emails

    def _classify_batch_internal(self, emails: List[Dict]) -> None:
        """内部方法：对一批邮件进行LLM分类"""
        if not emails:
            return

        # 构建邮件列表供 LLM 分析
        email_list = []
        email_idx_map = {}
        for i, mail in enumerate(emails, 1):
            email_list.append(f"{i}. 标题: {mail.get('subject', '')[:100]}\n   发件人: {mail.get('from', '')[:80]}")
            email_idx_map[i] = mail

        email_text = "\n".join(email_list)

        system_prompt = get_stage1_prompt()

        user_prompt = f"""分析以下邮件：

{email_text}

返回JSON数组："""

        try:
            content = self._call_llm(system_prompt, user_prompt, timeout=60)
            results = extract_json_from_text(content, expect_array=True)
            if results and isinstance(results, list):
                result_map = {r["id"]: r["category"].upper() for r in results if "id" in r and "category" in r}
                for i, email in email_idx_map.items():
                    email["_stage1_category"] = result_map.get(i, self.CATEGORY_UNKNOWN)
            else:
                logger.warning(f"Stage 1 JSON解析失败，返回内容: {content[:200]}...")
                for email in emails:
                    email["_stage1_category"] = self.CATEGORY_UNKNOWN
        except Exception as e:
            logger.error(f"Stage 1 批次分析失败: {e}", exc_info=True)
            for email in emails:
                email["_stage1_category"] = self.CATEGORY_UNKNOWN

    def stage2_analyze_content(self, emails: List[Dict]) -> Dict:
        """Stage 2: 逐封分析邮件内容，提取详细信息"""
        if not emails:
            return {"items": [], "classifications": []}

        all_items = []
        all_classifications = []

        total = len(emails)
        for i, email in enumerate(emails, 1):
            logger.info(f"Stage 2: 分析 {i}/{total}...")
            result = self._analyze_single_email(email, i)

            if result.get("item"):
                item = result["item"]
                item["source_emails"] = [i]
                all_items.append(item)

            if result.get("classification"):
                cls = result["classification"]
                cls["id"] = i
                all_classifications.append(cls)

        return {
            "items": all_items,
            "classifications": all_classifications
        }

    def _analyze_single_email(self, email: Dict, idx: int) -> Dict:
        """分析单封邮件内容"""
        body = (email.get("body") or "")[:1500]
        subject = email.get("subject", "")[:200]
        from_addr = email.get("from", "")[:100]

        system_prompt = get_stage2_prompt()

        user_prompt = f"""分析这封邮件：

标题: {subject}
发件人: {from_addr}
内容: {body}

返回JSON："""

        try:
            content = self._call_llm(system_prompt, user_prompt, timeout=60)
            result = extract_json_from_text(content, expect_array=False)
            if result and isinstance(result, dict):
                # 更新邮件属性
                cls = result.get("classification", {})
                email["_final_category"] = cls.get("category", "Unknown")
                email["_importance"] = cls.get("importance", 2)
                email["_needs_action"] = cls.get("needs_action", False)
                email["_summary"] = cls.get("summary", "")[:20]
                email["_venue"] = cls.get("venue", "")

                # 检查是否是已发表论文的垃圾邮件
                item = result.get("item")
                if item and item.get("is_published_spam"):
                    email["_final_category"] = "Trash/Published"
                    email["_importance"] = 1
                    email["_needs_action"] = False

                return result
            else:
                logger.warning("Stage 2 JSON解析失败")
        except Exception as e:
            logger.error(f"Stage 2 分析失败: {e}", exc_info=True)

        return {}

    def classify_single(self, email: Dict) -> str:
        """分类单封邮件"""
        self.stage1_classify_batch([email])
        category = email.get("_stage1_category", self.CATEGORY_UNKNOWN)

        if category == self.CATEGORY_UNKNOWN and email.get("body"):
            result = self.stage2_analyze_content([email])
            if result.get("classifications"):
                category = result["classifications"][0].get("category", self.CATEGORY_UNKNOWN)
                email["_final_category"] = category

        return category
