"""
账单本地数据库
管理信用卡、会员订阅等账单条目
本地SQLite作为主数据源，变更时同步到Notion
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional

from config.settings import STATE_DB_PATH


class BillingDB:
    """账单本地数据库"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or STATE_DB_PATH
        self._init_db()

    def _init_db(self):
        """初始化账单相关表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 账单条目表（信用卡、会员等）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                cycle TEXT,
                due_day INTEGER,
                amount REAL,
                currency TEXT DEFAULT 'CNY',
                status TEXT DEFAULT 'active',
                notion_page_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                synced_at DATETIME
            )
        """)

        # 账单记录表（每期账单）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                period TEXT NOT NULL,
                amount REAL,
                due_date TEXT,
                status TEXT DEFAULT 'pending',
                email_message_id TEXT,
                email_subject TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES billing_items(id),
                UNIQUE(item_id, period)
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_billing_records_item
            ON billing_records(item_id)
        """)

        conn.commit()
        conn.close()

    # ============== 账单条目管理 ==============

    def get_or_create_item(self, name: str, item_type: str, **kwargs) -> int:
        """获取或创建账单条目"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 查找现有
        cursor.execute("SELECT id FROM billing_items WHERE name = ?", (name,))
        row = cursor.fetchone()

        if row:
            item_id = row[0]
        else:
            # 创建新条目
            cursor.execute("""
                INSERT INTO billing_items (name, type, description, cycle, due_day, amount, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                item_type,
                kwargs.get("description", ""),
                kwargs.get("cycle", "monthly"),
                kwargs.get("due_day"),
                kwargs.get("amount"),
                kwargs.get("currency", "CNY"),
            ))
            item_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return item_id

    def get_all_items(self) -> List[Dict]:
        """获取所有账单条目"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM billing_items
            WHERE status = 'active'
            ORDER BY type, name
        """)

        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items

    def get_item_by_name(self, name: str) -> Optional[Dict]:
        """根据名称获取条目"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM billing_items WHERE name = ?", (name,))
        row = cursor.fetchone()

        conn.close()
        return dict(row) if row else None

    def update_item_notion_id(self, item_id: int, notion_page_id: str):
        """更新条目的Notion页面ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE billing_items
            SET notion_page_id = ?, synced_at = ?
            WHERE id = ?
        """, (notion_page_id, datetime.now().isoformat(), item_id))

        conn.commit()
        conn.close()

    # ============== 账单记录管理 ==============

    def add_or_update_record(
        self,
        item_id: int,
        period: str,
        amount: float = None,
        due_date: str = None,
        status: str = "pending",
        email_message_id: str = None,
        email_subject: str = None,
        notes: str = None
    ) -> tuple:
        """添加或更新账单记录

        Returns:
            (record_id, is_new, has_changes)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 查找现有记录
        cursor.execute("""
            SELECT * FROM billing_records
            WHERE item_id = ? AND period = ?
        """, (item_id, period))

        existing = cursor.fetchone()

        if existing:
            existing = dict(existing)
            # 检查是否有变化
            has_changes = False

            if amount is not None and existing.get("amount") != amount:
                has_changes = True
            if due_date is not None and existing.get("due_date") != due_date:
                has_changes = True
            if status and existing.get("status") != status:
                has_changes = True

            if has_changes:
                # 更新
                cursor.execute("""
                    UPDATE billing_records
                    SET amount = COALESCE(?, amount),
                        due_date = COALESCE(?, due_date),
                        status = COALESCE(?, status),
                        email_message_id = COALESCE(?, email_message_id),
                        notes = COALESCE(?, notes),
                        updated_at = ?
                    WHERE id = ?
                """, (amount, due_date, status, email_message_id, notes,
                      datetime.now().isoformat(), existing["id"]))

            conn.commit()
            conn.close()
            return (existing["id"], False, has_changes)
        else:
            # 创建新记录
            cursor.execute("""
                INSERT INTO billing_records
                (item_id, period, amount, due_date, status, email_message_id, email_subject, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, period, amount, due_date, status,
                  email_message_id, email_subject, notes))

            record_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return (record_id, True, True)

    def get_records_for_item(self, item_id: int, limit: int = 12) -> List[Dict]:
        """获取条目的账单记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM billing_records
            WHERE item_id = ?
            ORDER BY period DESC
            LIMIT ?
        """, (item_id, limit))

        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records

    def get_pending_records(self) -> List[Dict]:
        """获取待处理的账单记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT r.*, i.name as item_name, i.type as item_type
            FROM billing_records r
            JOIN billing_items i ON r.item_id = i.id
            WHERE r.status = 'pending'
            ORDER BY r.due_date
        """)

        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records

    def mark_record_paid(self, record_id: int):
        """标记账单为已支付"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE billing_records
            SET status = 'paid', updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), record_id))

        conn.commit()
        conn.close()

    # ============== 统计 ==============

    def get_summary(self) -> Dict:
        """获取账单摘要"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 条目数量
        cursor.execute("SELECT COUNT(*) FROM billing_items WHERE status = 'active'")
        total_items = cursor.fetchone()[0]

        # 按类型统计
        cursor.execute("""
            SELECT type, COUNT(*) FROM billing_items
            WHERE status = 'active'
            GROUP BY type
        """)
        by_type = dict(cursor.fetchall())

        # 待处理账单
        cursor.execute("""
            SELECT COUNT(*) FROM billing_records WHERE status = 'pending'
        """)
        pending_count = cursor.fetchone()[0]

        conn.close()

        return {
            "total_items": total_items,
            "by_type": by_type,
            "pending_records": pending_count,
        }
