"""
两阶段邮件分类器（LLM驱动）
Stage 1: LLM分析标题+发件人判断分类
Stage 2: 如果标题无法判断，LLM分析邮件内容
"""

import re
import json
import requests
from typing import Dict, List, Tuple
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import KIMI_API_URL, KIMI_API_KEY, KIMI_MODEL, KIMI_TIMEOUT


class EmailClassifier:
    """两阶段LLM邮件分类器"""

    # 分类结果
    CATEGORY_TRASH = "TRASH"           # 垃圾邮件
    CATEGORY_ACADEMIC = "ACADEMIC"     # 学术相关（论文/审稿）
    CATEGORY_BILLING = "BILLING"       # 账单相关
    CATEGORY_IMPORTANT = "IMPORTANT"   # 重要邮件（学校通知等）
    CATEGORY_UNKNOWN = "UNKNOWN"       # 需要进一步分析内容

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
            "temperature": 1  # kimi-k2.5 只支持 temperature=1
        }

        response = self.session.post(
            KIMI_API_URL,
            headers=headers,
            json=data,
            timeout=timeout or KIMI_TIMEOUT
        )
        response.raise_for_status()

        result = response.json()
        return result["choices"][0]["message"]["content"]

    def stage1_classify_batch(self, emails: List[Dict], batch_size: int = 20) -> List[Dict]:
        """
        Stage 1: 批量分析邮件标题，判断分类

        用LLM分析邮件的标题和发件人，快速判断分类。
        为避免超时，分批处理。

        Args:
            emails: 邮件列表（只需subject和from）
            batch_size: 每批处理的邮件数量

        Returns:
            带分类结果的邮件列表
        """
        if not emails:
            return []

        # 分批处理
        total = len(emails)
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch = emails[batch_start:batch_end]
            print(f"   📧 Stage 1: 处理 {batch_start+1}-{batch_end}/{total} 封邮件...")

            self._classify_batch_internal(batch, batch_start)

        return emails

    def _classify_batch_internal(self, emails: List[Dict], offset: int = 0) -> None:
        """内部方法：对一批邮件进行LLM分类"""
        if not emails:
            return

        # 准备邮件摘要（只有标题和发件人）
        email_list = []
        for i, mail in enumerate(emails, 1):
            email_list.append(f"{i}. 标题: {mail.get('subject', '')[:100]}\n   发件人: {mail.get('from', '')[:80]}")

        email_text = "\n".join(email_list)

        system_prompt = """你是一个邮件分类专家。根据邮件标题和发件人快速判断邮件类型。

【分类选项】
1. TRASH - 垃圾邮件：
   - 会议征稿、期刊投稿邀请、编辑邀请
   - 营销推广、折扣优惠、产品宣传
   - 引用提醒、重印本邀请、隐私政策更新
   - 系统通知（隔离区、密码重置等）

2. ACADEMIC - 学术相关：
   - 论文投稿状态（提交、审稿中、修改、接收、拒稿）
   - 审稿邀请、审稿提醒
   - 稿件校对、proof

3. BILLING - 账单相关：
   - 信用卡账单、还款提醒
   - 会员订阅、续费通知
   - 发票、payment

4. IMPORTANT - 重要邮件：
   - 学校/单位通知（关于...的通知）
   - 准考证、成绩、注册
   - 工作相关的重要沟通

5. UNKNOWN - 无法从标题判断，需要看内容

【输出格式】
返回JSON数组，每个元素包含邮件编号和分类：
[{"id": 1, "category": "TRASH"}, {"id": 2, "category": "ACADEMIC"}, ...]"""

        user_prompt = f"""请分析以下邮件，根据标题和发件人判断分类：

{email_text}

返回JSON数组："""

        try:
            content = self._call_llm(system_prompt, user_prompt, timeout=60)

            # 提取JSON
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                results = json.loads(json_match.group())

                # 更新邮件分类
                result_map = {r["id"]: r["category"] for r in results}
                for i, email in enumerate(emails, 1):
                    category = result_map.get(i, self.CATEGORY_UNKNOWN)
                    email["_stage1_category"] = category

        except Exception as e:
            print(f"   ⚠️ Stage 1 批次分析失败: {e}")
            # 失败时标记为UNKNOWN
            for email in emails:
                email["_stage1_category"] = self.CATEGORY_UNKNOWN

    def stage2_analyze_content(self, emails: List[Dict], batch_size: int = 10) -> Dict:
        """
        Stage 2: 分析邮件内容

        对Stage 1无法判断的邮件，或需要详细分析的学术邮件，
        分析邮件正文提取详细信息。
        为避免超时，分批处理。

        Args:
            emails: 需要分析的邮件列表（已加载body）
            batch_size: 每批处理的邮件数量

        Returns:
            分析结果（合并所有批次）
        """
        if not emails:
            return {"items": [], "classifications": []}

        all_items = []
        all_classifications = []

        # 分批处理
        total = len(emails)
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch = emails[batch_start:batch_end]
            print(f"   📄 Stage 2: 分析 {batch_start+1}-{batch_end}/{total} 封邮件内容...")

            result = self._analyze_content_batch(batch, batch_start)

            # 合并结果，调整ID偏移
            for item in result.get("items", []):
                # 调整source_emails的ID
                if "source_emails" in item:
                    item["source_emails"] = [sid + batch_start for sid in item["source_emails"]]
                all_items.append(item)

            for cls in result.get("classifications", []):
                cls["id"] = cls["id"] + batch_start
                all_classifications.append(cls)

        return {
            "items": all_items,
            "classifications": all_classifications,
            "summary": f"共分析 {total} 封邮件"
        }

    def _analyze_content_batch(self, emails: List[Dict], offset: int = 0) -> Dict:
        """内部方法：分析一批邮件的内容"""
        if not emails:
            return {"items": [], "classifications": []}

        # 准备邮件摘要（包含正文）
        email_summaries = []
        for i, mail in enumerate(emails, 1):
            body = (mail.get("body") or "")[:800]
            summary = f"{i}. 标题: {mail['subject'][:150]}\n   发件人: {mail['from'][:80]}\n   内容: {body}"
            email_summaries.append(summary)

        email_text = "\n\n".join(email_summaries)

        system_prompt = """你是一个学术邮件分析专家。分析邮件内容，提取结构化信息。

【任务】
1. 确定每封邮件的最终分类
2. 对学术邮件，提取论文/审稿详情
3. 识别真正重要的邮件

【分类选项】
- Paper/InProgress: 论文投稿流程中（提交、审稿中、修改、接收）
- Review/Active: 需要完成的审稿任务
- Action/Important: 需要回复的重要邮件
- Billing: 账单相关
- Academic/Trash: 学术垃圾（引用提醒、重印本、已发表论文的后续）
- Spam: 垃圾邮件"""

        user_prompt = f"""请分析以下邮件内容：

{email_text}

【输出JSON格式】
{{
    "items": [
        {{
            "type": "paper" 或 "review",
            "category": "Paper/InProgress" 或 "Review/Active",
            "manuscript_id": "稿件编号",
            "title": "论文标题",
            "journal": "期刊",
            "status": "状态",
            "deadline": "截止日期（审稿）YYYY-MM-DD",
            "last_update": "YYYY-MM-DD",
            "source_emails": [对应邮件编号],
            "notes": "备注"
        }}
    ],
    "classifications": [
        {{"id": 1, "category": "分类", "reason": "简要原因"}}
    ],
    "summary": "一句话总结"
}}"""

        try:
            content = self._call_llm(system_prompt, user_prompt, timeout=90)

            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())

                # 更新邮件的最终分类
                if "classifications" in result:
                    class_map = {c["id"]: c["category"] for c in result["classifications"]}
                    for i, email in enumerate(emails, 1):
                        if i in class_map:
                            email["_final_category"] = class_map[i]

                return result

        except Exception as e:
            print(f"   ⚠️ Stage 2 批次分析失败: {e}")

        return {"items": [], "classifications": []}

    def classify_single(self, email: Dict) -> str:
        """
        分类单封邮件（用于实时处理）

        Args:
            email: 邮件字典

        Returns:
            分类结果
        """
        # 先用标题判断
        emails = self.stage1_classify_batch([email])
        category = email.get("_stage1_category", self.CATEGORY_UNKNOWN)

        # 如果无法判断，需要分析内容
        if category == self.CATEGORY_UNKNOWN and email.get("body"):
            result = self.stage2_analyze_content([email])
            if result.get("classifications"):
                category = result["classifications"][0].get("category", self.CATEGORY_UNKNOWN)
                email["_final_category"] = category

        return category


# 为了向后兼容，保留旧的常量名
EmailClassifier.STAGE1_TRASH = EmailClassifier.CATEGORY_TRASH
EmailClassifier.STAGE1_ACADEMIC = EmailClassifier.CATEGORY_ACADEMIC
EmailClassifier.STAGE1_BILLING = EmailClassifier.CATEGORY_BILLING
EmailClassifier.STAGE1_UNKNOWN = EmailClassifier.CATEGORY_UNKNOWN
