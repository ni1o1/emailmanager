"""
两阶段邮件分类器（LLM驱动）
Stage 1: LLM分析标题+发件人判断分类
Stage 2: 如果标题无法判断，LLM分析邮件内容
"""

import re
import json
import requests
from typing import Dict, List, Tuple, Optional, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import KIMI_API_URL, KIMI_API_KEY, KIMI_MODEL, KIMI_TIMEOUT
from config.categories import HIGH_PRIORITY_SENDERS, TRASH_SENDERS


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

        response = self.session.post(
            KIMI_API_URL,
            headers=headers,
            json=data,
            timeout=timeout or KIMI_TIMEOUT
        )
        response.raise_for_status()

        result = response.json()
        return result["choices"][0]["message"]["content"]

    def stage1_classify_batch(self, emails: List[Dict], batch_size: int = 10) -> List[Dict]:
        """Stage 1: 批量分析邮件标题"""
        if not emails:
            return []

        total = len(emails)
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch = emails[batch_start:batch_end]
            print(f"   📧 Stage 1: 处理 {batch_start+1}-{batch_end}/{total} 封邮件...")
            self._classify_batch_internal(batch)

        return emails

    def _check_sender_priority(self, email: Dict) -> tuple:
        """检查发件人优先级，返回 (category, importance) 或 (None, None)"""
        from_addr = (email.get("from", "") or "").lower()
        subject = (email.get("subject", "") or "").lower()

        # 1. 检查高优先级发件人（白名单）
        for sender, info in HIGH_PRIORITY_SENDERS.items():
            if sender.lower() in from_addr:
                return info["category"], info["importance"]

        # 2. 检查垃圾发件人（黑名单）
        for sender in TRASH_SENDERS:
            if sender.lower() in from_addr:
                return self.CATEGORY_TRASH, 1

        # 3. 特殊标题规则
        # 考试相关关键词优先于其他分类
        exam_keywords = ["ielts", "雅思", "托福", "toefl", "gre", "准考证", "成绩", "score"]
        if any(kw in subject or kw in from_addr for kw in exam_keywords):
            return self.CATEGORY_EXAM, 5

        # 已发表论文的广告
        if any(kw in subject for kw in ["reprint", "order copies", "citation alert", "nearing publication"]):
            return self.CATEGORY_TRASH, 1

        return None, None

    def _classify_batch_internal(self, emails: List[Dict]) -> None:
        """内部方法：对一批邮件进行LLM分类"""
        if not emails:
            return

        # 先用规则引擎预分类
        needs_llm = []
        for email in emails:
            category, importance = self._check_sender_priority(email)
            if category:
                email["_stage1_category"] = category
                email["_importance"] = importance
            else:
                needs_llm.append(email)

        # 如果所有邮件都已经被规则分类，直接返回
        if not needs_llm:
            return

        email_list = []
        email_idx_map = {}  # 记录 LLM 列表序号到原始邮件的映射
        for i, mail in enumerate(needs_llm, 1):
            email_list.append(f"{i}. 标题: {mail.get('subject', '')[:100]}\n   发件人: {mail.get('from', '')[:80]}")
            email_idx_map[i] = mail

        email_text = "\n".join(email_list)

        system_prompt = """# Role: 我的学术事务执行官 (Chief of Staff)

## 你的身份设定
你是我（一名忙碌的研究人员）的“第二大脑”。你深知我的时间和注意力是最宝贵的资源。
你是我（一名忙碌的学术研究人员/博士生）的“第二大脑”。
你的核心任务是：**保护我的注意力，极度冷酷地过滤噪音，只把真正需要我行动的事项呈递给我。**

## 你的决策价值观（Persona Profile）
1.  **极简主义**：我每天收到大量邮件，如果一封邮件不需要我回复、不需要我付费、不需要我立刻操作，它通常就是垃圾。
2.  **结果导向**：我只关心论文的“结果”（录用/拒稿/修改），不关心“过程的周边”（谁引用了我、哪家云服务打折）。
3.  **风险厌恶**：涉及“钱（账单）”和“前途（考试/截稿）”的邮件，优先级最高，绝对不能漏。

## 你的任务
根据邮件标题和发件人，判断邮件的性质，并**严格**归入以下 8 个分类之一。

---

## 决策优先级与分类定义 (必须严格使用以下 Category 名称)

请按以下**优先级顺序**进行判断，一旦匹配即停止：

### 1. 【红线级】绝对不能漏 (Life & Money)
* **EXAM**
    * **定义**：涉及我个人前途的考试相关。
    * **特征**：雅思(IELTS)、托福(TOEFL)、GRE、准考证(Admission Ticket)、成绩单(Score Report)、报名确认。
    * **价值观**：这是“身家性命”，优先级最高。
* **BILLING**
    * **定义**：需要我付钱的账单。
    * **特征**：信用卡账单、必须支付的会员续费、发票。

### 2. 【核心级】需要我行动 (Action Required)
* **PAPER**
    * **定义**：**仅限**我正在投稿流程中的论文状态变更。
    * **包含**：Submission confirmation, Revision required, Decision (Accept/Reject), Author query, Proofs。
    * **🚫 严格排除（移至 TRASH）**：已发表论文的推销（Order Reprints, Posters）、引用提醒。
* **REVIEW**
    * **定义**：需要我审稿的任务。
    * **特征**：Review Invitation, Review Reminder, Thank you for reviewing。
* **NOTICE**
    * **定义**：来自学校/单位的官方行政通知。
    * **特征**：通常来自 `.edu.cn`，关于政策、放假、IT维护的官方通告。
    * **🚫 严格排除（移至 TRASH）**：算力平台通知、图书馆新书推荐。

### 3. 【社交级】真实的人 (Human)
* **PERSONAL**
    * **定义**：同事、导师、朋友发来的非群发邮件。
    * **特征**：语气私人，非自动化模板。

### 4. 【噪音级】最大的垃圾桶 (The Filter)
* **TRASH**
    * **定义**：任何不需要我立刻行动、付费或回复的信息。**这是最大的默认类别。**
    * **包含 - 学术虚荣指标（重要！）**：引用提醒 (Citation Alert)、ResearchGate 阅读量通知、Google Scholar 更新。
    * **包含 - 学术推销**：会议征稿 (CFP)、特刊邀请、版面费打折、书稿邀请、购买抽印本 (Order Reprints)。
    * **包含 - 资源通知**：AutoDL/阿里云/腾讯云的资源包到期、显卡释放、活动通知（除非是欠费停机，否则都是垃圾）。
    * **包含 - 其他**：Newsletter、问卷调查、GitHub 自动通知、系统验证码、TOS 更新。

### 5. 【兜底】
* **UNKNOWN**
    * **定义**：经过上述判断仍无法确定的。

---

## 你的思考过程 (Internal Monologue)

在输出前，请先自问：
1. "这封邮件是关于考试(EXAM)或钱(BILLING)吗？" -> 是 -> 归类。
2. "这封邮件是我正在投的论文(PAPER)或要审的稿(REVIEW)吗？" -> **警惕**：如果是叫我买Reprint或告诉我被引用了，这是推销，归入 TRASH。
3. "这是学校行政(NOTICE)或真人(PERSONAL)吗？" -> **警惕**：算力平台通知是广告，归入 TRASH。
4. "如果不属于以上所有，它就是 TRASH。"

## 输出格式
请直接返回 JSON 数组，不要包含 Markdown 标记：
[
  {"id": 1, "category": "TRASH", "reason": "引用提醒，属于学术虚荣指标，无需操作"},
  {"id": 2, "category": "PAPER", "reason": "收到修改意见，属于核心投稿流程"}
]"""

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
                print(f"   ⚠️ Stage 1 JSON解析失败，返回内容: {content[:200]}...")
                for email in needs_llm:
                    email["_stage1_category"] = self.CATEGORY_UNKNOWN
        except Exception as e:
            print(f"   ⚠️ Stage 1 批次分析失败: {e}")
            for email in needs_llm:
                email["_stage1_category"] = self.CATEGORY_UNKNOWN

    def stage2_analyze_content(self, emails: List[Dict]) -> Dict:
        """Stage 2: 逐封分析邮件内容，提取详细信息"""
        if not emails:
            return {"items": [], "classifications": []}

        all_items = []
        all_classifications = []

        total = len(emails)
        for i, email in enumerate(emails, 1):
            print(f"   📄 Stage 2: 分析 {i}/{total}...")
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

        system_prompt = """# Role: 我的学术情报官 (Academic Intelligence Officer)

## 你的核心任务
你是我的信息提取引擎。你需要阅读邮件，剥离所有客套话和噪音，将**核心结构化数据**填入我的仪表盘。
**你的风格：** 像电报员一样精炼，像审计员一样严谨。

---

## 步骤 1：重要性评分协议 (Importance Protocol)

请基于邮件对我的**职业生存**和**时间紧迫性**的影响进行评分（1-5分）：

* **5分 (CRITICAL / 紧急)**: **涉及“死线”或“前途”**。
    * *逻辑*：如果我现在不看，我会挂科、被拒稿、违约或错过最后期限。
    * *场景*：准考证/成绩单 (EXAM)、审稿/修稿剩余时间 < 7天、必须立即处理的行政命令。
* **4分 (HIGH / 重要)**: **核心工作流**。
    * *逻辑*：这是我的主要工作（发论文/审稿），需要安排时间处理，但不是今天就要炸。
    * *场景*：新的审稿邀请、论文状态变更（接收/拒稿/大修）、考试报名确认。
* **3分 (NORMAL / 一般)**: **信息同步**。
    * *逻辑*：我需要知道这件事，但不需要我做什么。
    * *场景*：系统维护通知、无具体deadline的行政通知、账单出账通知（自动扣款）。
* **2分 (LOW / 闲杂)**: **可有可无**。
    * *逻辑*：看了不亏，不看也没事。
    * *场景*：讲座海报、非强制性的活动通知。
* **1分 (TRASH / 垃圾)**: **噪音**。
    * *逻辑*：任何试图推销东西、或者提供“虚荣指标”的邮件。
    * *场景*：广告、积分营销、引用提醒、抽印本推销。

## 步骤 2：行动判定协议 (Action Protocol)

判断 `needs_action` (true/false)。**标准极度严格：**

* **TRUE (必须行动)**：
    * 邮件明确要求我**回复(Reply)**、**提交(Submit)**、**确认(Confirm)**、**支付(Pay)**或**打印(Print)**。
    * *特例*：审稿/修稿任务，只要没完成，全是 true。
* **FALSE (无需行动)**：
    * **好消息**：论文被接收 (Accepted) -> 这是结果，不是动作。
    * **已完成**：审稿完成感谢信 -> 任务结束。
    * **纯通知**：账单金额通知（除非写着"支付失败"）、系统更新。
    * **学术噪音**：引用提醒、下载量报告 -> 绝对 false。

## 步骤 3：学术噪音识别 (Spam Detection)

**【最高警惕】** 学术圈有很多伪装成“重要通知”的垃圾。
如果邮件包含以下特征，直接标记为 `importance: 1` 且 `is_published_spam: true`：
1.  **推销周边**：关键词 "order reprints", "order copies", "buy poster", "webshop"。
2.  **虚荣指标**：关键词 "citation alert", "new citation", "article metrics"。
3.  **已发表后续**：标题包含 "nearing publication" 但内容是让你买东西。

## 步骤 4：信息提取与摘要 (Extraction)

* **Venue (期刊/会议)**：必须准确提取（如 IEEE TGRS, CVPR, Nature）。
* **Summary (摘要)**：**电报风格**，严禁废话，20字以内。
    * *Good*: "TGRS论文需大修 DDL:2/15"
    * *Good*: "雅思准考证已出 3/2考试"
    * *Good*: "拒绝审稿邀请 Access"
    * *Bad*: "这是一封来自IEEE的邮件，通知您的论文..." (太啰嗦)

---

## 输出格式 (JSON Only)

请严格按照此结构返回 JSON，不要包含 Markdown 代码块标记：

{
    "item": {
        // 仅当邮件是 Paper (投稿中) 或 Review (审稿中) 时填写，否则为 null
        // 注意：如果是 EXAM 或 BILLING 或 TRASH，这里必须是 null
        "type": "paper" 或 "review",
        "venue_type": "journal" 或 "conference",
        "category": "Paper/Journal" (论文) 或 "Review/Active" (审稿) 或 "Trash/Published" (学术垃圾),
        "manuscript_id": "提取稿件号，如 TGRS-2024-1234",
        "title": "提取论文标题",
        "venue": "期刊缩写，如 IEEE TGRS",
        "status": "状态，如 Under Review / Major Revision",
        "deadline": "YYYY-MM-DD" (仅当明确提到截止日期时填写，否则 null),
        "is_published_spam": false // 命中步骤3特征时为 true
    },
    "classification": {
        "category": "分类 (PAPER/REVIEW/EXAM/BILLING/NOTICE/TRASH)",
        "importance": 1-5 (整数),
        "needs_action": true/false,
        "summary": "20字电报式摘要",
        "venue": "期刊名 (仅论文/审稿类填写，其他为空)"
    }
}"""

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
                print(f"      ⚠️ Stage 2 JSON解析失败")
        except Exception as e:
            print(f"      ⚠️ 分析失败: {e}")

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
