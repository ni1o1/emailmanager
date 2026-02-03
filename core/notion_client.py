"""
Notion 客户端
负责数据库操作
"""

import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Optional

from config.settings import (
    NOTION_API_URL, NOTION_TOKEN, NOTION_VERSION,
    NOTION_DB_PAPERS, NOTION_DB_REVIEWS, NOTION_DB_EMAILS, NOTION_PARENT_PAGE_ID
)
from config.categories import normalize_paper_status, normalize_review_status
from core.logger import get_logger
from core.exceptions import NotionError

logger = get_logger(__name__)


class NotionClient:
    """Notion API 客户端"""

    def __init__(self):
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)

        self.headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION
        }

        # 缓存数据库ID
        self._db_cache = {}

    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """发送API请求"""
        url = f"{NOTION_API_URL}{endpoint}"

        for attempt in range(3):
            try:
                start_time = time.time()
                if method == "GET":
                    response = self.session.get(url, headers=self.headers, timeout=30)
                elif method == "POST":
                    response = self.session.post(url, headers=self.headers, json=data, timeout=30)
                elif method == "PATCH":
                    response = self.session.patch(url, headers=self.headers, json=data, timeout=30)
                else:
                    return {"error": f"Unsupported method: {method}"}

                duration = time.time() - start_time
                result = response.json()

                # 检查 API 错误
                if response.status_code != 200:
                    logger.warning(
                        f"Notion API 错误: {response.status_code} "
                        f"({result.get('code', 'unknown')}: {result.get('message', 'no message')})"
                    )

                logger.debug(f"Notion API {method} {endpoint}: {duration:.2f}s")
                return result
            except Exception as e:
                logger.warning(f"Notion API 请求失败 (尝试 {attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(2)
                    continue
                logger.error(f"Notion API 请求最终失败: {e}")
                return {"error": str(e)}

    def find_database(self, name_contains: str) -> Optional[str]:
        """查找数据库ID"""
        if name_contains in self._db_cache:
            return self._db_cache[name_contains]

        result = self._request("POST", "/search", {
            "query": name_contains,
            "filter": {"property": "object", "value": "database"}
        })

        for db in result.get("results", []):
            title = ""
            if db.get("title"):
                title = "".join([t.get("plain_text", "") for t in db["title"]])
            if name_contains in title:
                db_id = db["id"]
                self._db_cache[name_contains] = db_id
                return db_id
        return None

    def get_papers_db(self) -> Optional[str]:
        """获取论文投稿数据库ID"""
        db_id = self.find_database("论文投稿")
        if db_id:
            return db_id

        # 创建数据库
        pages = self._request("POST", "/search", {"filter": {"property": "object", "value": "page"}})
        if not pages.get("results"):
            return None

        parent_id = pages["results"][0]["id"]
        db_data = {
            "parent": {"type": "page_id", "page_id": parent_id},
            "title": [{"type": "text", "text": {"content": NOTION_DB_PAPERS}}],
            "properties": {
                "论文标题": {"title": {}},
                "稿件编号": {"rich_text": {}},
                "类型": {
                    "select": {
                        "options": [
                            {"name": "期刊", "color": "blue"},
                            {"name": "会议", "color": "purple"},
                        ]
                    }
                },
                "期刊/会议": {"rich_text": {}},
                "状态": {
                    "select": {
                        "options": [
                            {"name": "已投稿", "color": "blue"},
                            {"name": "审稿中", "color": "yellow"},
                            {"name": "小修", "color": "orange"},
                            {"name": "大修", "color": "red"},
                            {"name": "已接收", "color": "green"},
                            {"name": "被拒稿", "color": "gray"},
                        ]
                    }
                },
                "最后更新": {"date": {}},
                "备注": {"rich_text": {}},
            }
        }
        result = self._request("POST", "/databases", db_data)
        if "id" in result:
            self._db_cache["论文投稿"] = result["id"]
            return result["id"]
        return None

    def get_reviews_db(self) -> Optional[str]:
        """获取审稿任务数据库ID"""
        db_id = self.find_database("审稿任务")
        if db_id:
            return db_id

        pages = self._request("POST", "/search", {"filter": {"property": "object", "value": "page"}})
        if not pages.get("results"):
            return None

        parent_id = pages["results"][0]["id"]
        db_data = {
            "parent": {"type": "page_id", "page_id": parent_id},
            "title": [{"type": "text", "text": {"content": NOTION_DB_REVIEWS}}],
            "properties": {
                "论文标题": {"title": {}},
                "期刊": {"rich_text": {}},
                "状态": {
                    "select": {
                        "options": [
                            {"name": "待接受", "color": "yellow"},
                            {"name": "已接受", "color": "blue"},
                            {"name": "审稿中", "color": "orange"},
                            {"name": "已提交", "color": "green"},
                        ]
                    }
                },
                "截止日期": {"date": {}},
                "备注": {"rich_text": {}},
            }
        }
        result = self._request("POST", "/databases", db_data)
        if "id" in result:
            self._db_cache["审稿任务"] = result["id"]
            return result["id"]
        return None

    def get_existing_records(self, db_id: str) -> Dict[str, dict]:
        """获取现有记录"""
        result = self._request("POST", f"/databases/{db_id}/query", {})
        existing = {}
        for page in result.get("results", []):
            props = page.get("properties", {})

            # 用稿件编号或标题作为key
            key = ""
            if props.get("稿件编号", {}).get("rich_text"):
                texts = props["稿件编号"]["rich_text"]
                if texts:
                    key = texts[0]["text"]["content"]

            if not key and props.get("论文标题", {}).get("title"):
                titles = props["论文标题"]["title"]
                if titles:
                    key = titles[0]["text"]["content"][:50]

            if key:
                existing[key] = {"page_id": page["id"], "props": props}
        return existing

    def sync_paper(self, paper: Dict) -> bool:
        """同步论文记录"""
        db_id = self.get_papers_db()
        if not db_id:
            return False

        existing = self.get_existing_records(db_id)
        manuscript_id = paper.get("manuscript_id", "") or ""
        title = (paper.get("title", "") or "")[:100]

        # 标题不能为空
        if not title:
            return False

        status = normalize_paper_status(paper.get("status", ""))

        # 期刊/会议类型
        venue_type = paper.get("venue_type", "journal")
        venue_type_name = "期刊" if venue_type == "journal" else "会议"

        # 期刊/会议名称
        venue = (paper.get("venue", "") or paper.get("journal", "") or "")[:100]

        # 查找是否已存在
        existing_record = existing.get(manuscript_id) or existing.get(title[:50])

        if existing_record:
            # 更新
            update_data = {
                "properties": {
                    "状态": {"select": {"name": status}},
                    "备注": {"rich_text": [{"text": {"content": (paper.get("summary", "") or paper.get("notes", "") or "")[:500]}}]},
                }
            }
            if paper.get("last_update"):
                update_data["properties"]["最后更新"] = {"date": {"start": paper["last_update"]}}

            result = self._request("PATCH", f"/pages/{existing_record['page_id']}", update_data)
            return "id" in result
        else:
            # 创建
            page_data = {
                "parent": {"database_id": db_id},
                "properties": {
                    "论文标题": {"title": [{"text": {"content": title}}]},
                    "稿件编号": {"rich_text": [{"text": {"content": manuscript_id}}]},
                    "类型": {"select": {"name": venue_type_name}},
                    "期刊/会议": {"rich_text": [{"text": {"content": venue}}]},
                    "状态": {"select": {"name": status}},
                    "备注": {"rich_text": [{"text": {"content": (paper.get("summary", "") or paper.get("notes", "") or "")[:500]}}]},
                }
            }
            if paper.get("last_update"):
                page_data["properties"]["最后更新"] = {"date": {"start": paper["last_update"]}}

            result = self._request("POST", "/pages", page_data)
            return "id" in result

    def sync_review(self, review: Dict) -> bool:
        """同步审稿记录"""
        db_id = self.get_reviews_db()
        if not db_id:
            return False

        existing = self.get_existing_records(db_id)
        title = (review.get("title", "") or "未知论文")[:100]
        status = normalize_review_status(review.get("status", ""))

        existing_record = existing.get(title[:50])

        if existing_record:
            update_data = {
                "properties": {
                    "状态": {"select": {"name": status}},
                    "备注": {"rich_text": [{"text": {"content": (review.get("notes", "") or "")[:500]}}]},
                }
            }
            if review.get("deadline"):
                update_data["properties"]["截止日期"] = {"date": {"start": review["deadline"]}}

            result = self._request("PATCH", f"/pages/{existing_record['page_id']}", update_data)
            return "id" in result
        else:
            page_data = {
                "parent": {"database_id": db_id},
                "properties": {
                    "论文标题": {"title": [{"text": {"content": title}}]},
                    "期刊": {"rich_text": [{"text": {"content": (review.get("journal", "") or "")[:100]}}]},
                    "状态": {"select": {"name": status}},
                    "备注": {"rich_text": [{"text": {"content": (review.get("notes", "") or "")[:500]}}]},
                }
            }
            if review.get("deadline"):
                page_data["properties"]["截止日期"] = {"date": {"start": review["deadline"]}}

            result = self._request("POST", "/pages", page_data)
            return "id" in result

    def get_emails_db(self) -> Optional[str]:
        """获取邮件整理数据库ID"""
        db_id = self.find_database("邮件整理")
        if db_id:
            return db_id

        # 创建数据库（使用统一的父页面）
        db_data = {
            "parent": {"type": "page_id", "page_id": NOTION_PARENT_PAGE_ID},
            "title": [{"type": "text", "text": {"content": NOTION_DB_EMAILS}}],
            "properties": {
                "标题": {"title": {}},
                "发件人": {"rich_text": {}},
                "邮箱": {
                    "select": {
                        "options": [
                            {"name": "QQ邮箱", "color": "blue"},
                            {"name": "PKU邮箱", "color": "red"},
                        ]
                    }
                },
                "分类": {
                    "select": {
                        "options": [
                            {"name": "学术", "color": "purple"},
                            {"name": "审稿", "color": "orange"},
                            {"name": "账单", "color": "green"},
                            {"name": "通知", "color": "blue"},
                            {"name": "考试", "color": "pink"},
                            {"name": "个人", "color": "yellow"},
                        ]
                    }
                },
                "重要程度": {
                    "select": {
                        "options": [
                            {"name": "5-紧急", "color": "red"},
                            {"name": "4-重要", "color": "orange"},
                            {"name": "3-一般", "color": "yellow"},
                            {"name": "2-可选", "color": "blue"},
                            {"name": "1-低", "color": "gray"},
                        ]
                    }
                },
                "需处理": {"checkbox": {}},
                "期刊/会议": {"rich_text": {}},
                "日期": {"date": {}},
                "摘要": {"rich_text": {}},
            }
        }
        result = self._request("POST", "/databases", db_data)
        if "id" in result:
            self._db_cache["邮件整理"] = result["id"]
            return result["id"]
        return None

    def sync_email(self, email: Dict, category: str, importance: int = 3, needs_action: bool = False, summary: str = "", venue: str = "") -> bool:
        """
        同步邮件记录到邮件整理数据库

        Args:
            email: 邮件数据
            category: 分类（学术、审稿、账单、通知、考试、个人）
            importance: 重要程度 1-5
            needs_action: 是否需要处理
            summary: 10字内摘要
            venue: 期刊/会议名称
        """
        db_id = self.get_emails_db()
        if not db_id:
            return False

        subject = (email.get("subject", "") or "无标题")[:100]
        from_addr = (email.get("from", "") or "")[:100]
        account = email.get("account", "QQ邮箱")
        date_str = email.get("date_str", "")

        # 使用LLM生成的摘要
        if not summary:
            summary = email.get("_summary", "")
        summary = summary[:20]  # 限制20字

        # 期刊/会议名
        if not venue:
            venue = email.get("_venue", "") or ""
        venue = (venue or "")[:50]

        # 重要程度映射
        importance_map = {
            5: "5-紧急",
            4: "4-重要",
            3: "3-一般",
            2: "2-可选",
            1: "1-低",
        }
        importance_name = importance_map.get(importance, "2-可选")

        # 构建页面数据
        page_data = {
            "parent": {"database_id": db_id},
            "properties": {
                "标题": {"title": [{"text": {"content": subject}}]},
                "发件人": {"rich_text": [{"text": {"content": from_addr}}]},
                "邮箱": {"select": {"name": account}},
                "分类": {"select": {"name": category}},
                "重要程度": {"select": {"name": importance_name}},
                "需处理": {"checkbox": needs_action},
                "期刊/会议": {"rich_text": [{"text": {"content": venue}}]},
                "摘要": {"rich_text": [{"text": {"content": summary}}]},
            }
        }

        # 解析日期
        if date_str:
            try:
                from datetime import datetime
                # 尝试多种日期格式
                for fmt in ["%Y-%m-%d %H:%M:%S", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d"]:
                    try:
                        dt = datetime.strptime(date_str.split(" +")[0].split(" -")[0].strip(), fmt)
                        page_data["properties"]["日期"] = {"date": {"start": dt.strftime("%Y-%m-%d")}}
                        break
                    except:
                        continue
            except:
                pass

        result = self._request("POST", "/pages", page_data)
        return "id" in result
