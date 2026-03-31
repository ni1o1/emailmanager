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

from config.settings import KIMI_API_URL, KIMI_API_KEY, KIMI_MODEL, KIMI_TIMEOUT, LLM_THINKING_BUDGET
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

    def _call_llm(self, system_prompt: str, user_prompt: str, timeout: int = None, max_retries: int = 3) -> str:
        """
        调用LLM，支持 thinking budget 和应用层重试

        Args:
            system_prompt: 系统提示
            user_prompt: 用户提示
            timeout: 单次请求超时时间
            max_retries: 最大重试次数（默认3次）
        """
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

        # 添加 thinking budget
        if LLM_THINKING_BUDGET > 0:
            data["thinking"] = {
                "type": "enabled",
                "budget_tokens": LLM_THINKING_BUDGET
            }

        last_error = None
        for attempt in range(1, max_retries + 1):
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

                usage = result.get("usage", {})
                logger.debug(f"LLM调用成功: {duration:.2f}s, tokens: {usage.get('total_tokens', 'N/A')}")

                return result["choices"][0]["message"]["content"]
            except requests.Timeout:
                duration = time.time() - start_time
                last_error = LLMError("LLM调用超时", timeout=True)
                logger.warning(f"LLM调用超时 (尝试 {attempt}/{max_retries}): {duration:.2f}s")
            except requests.RequestException as e:
                duration = time.time() - start_time
                response_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
                last_error = LLMError(f"LLM请求失败: {e}", response_code=response_code)
                logger.warning(f"LLM调用失败 (尝试 {attempt}/{max_retries}): {duration:.2f}s, 错误: {e}")

            if attempt < max_retries:
                wait = 2 ** attempt  # 指数退避: 2s, 4s
                logger.info(f"等待 {wait}s 后重试...")
                time.sleep(wait)

        logger.error(f"LLM调用在 {max_retries} 次尝试后仍然失败")
        raise last_error

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

        # 带 JSON 解析重试的 Stage 1 调用
        max_parse_retries = 2
        for parse_attempt in range(max_parse_retries):
            try:
                content = self._call_llm(system_prompt, user_prompt, timeout=120)
                results = extract_json_from_text(content, expect_array=True)
                if results and isinstance(results, list):
                    result_map = {r["id"]: r["category"].upper() for r in results if "id" in r and "category" in r}
                    for i, email in email_idx_map.items():
                        email["_stage1_category"] = result_map.get(i, self.CATEGORY_UNKNOWN)
                    return  # 成功，退出
                else:
                    logger.warning(f"Stage 1 JSON解析失败 (尝试 {parse_attempt+1}/{max_parse_retries})，返回内容: {content[:200]}...")
                    if parse_attempt < max_parse_retries - 1:
                        continue  # 重试
            except Exception as e:
                logger.error(f"Stage 1 批次分析失败: {e}", exc_info=True)
                break  # LLM 调用本身已有重试，这里不再重复

        # 所有尝试都失败，标记为 UNKNOWN
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

        # 带 JSON 解析重试的 Stage 2 调用
        max_parse_retries = 2
        for parse_attempt in range(max_parse_retries):
            try:
                content = self._call_llm(system_prompt, user_prompt, timeout=120)
                result = extract_json_from_text(content, expect_array=False)
                if result and isinstance(result, dict):
                    cls = result.get("classification", {})
                    email["_final_category"] = cls.get("category", "Unknown")
                    email["_importance"] = cls.get("importance", 2)
                    email["_needs_action"] = cls.get("needs_action", False)
                    email["_summary"] = cls.get("summary", "")
                    email["_venue"] = cls.get("venue", "")

                    item = result.get("item")
                    if item and item.get("is_published_spam"):
                        email["_final_category"] = "Trash/Published"
                        email["_importance"] = 1
                        email["_needs_action"] = False

                    return result
                else:
                    logger.warning(f"Stage 2 JSON解析失败 (尝试 {parse_attempt+1}/{max_parse_retries})")
                    if parse_attempt < max_parse_retries - 1:
                        continue
            except Exception as e:
                logger.error(f"Stage 2 分析失败: {e}", exc_info=True)
                break

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
