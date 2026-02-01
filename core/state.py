"""
状态管理
使用SQLite记录已处理的邮件
"""

import sqlite3
from datetime import datetime
from typing import List, Optional, Set

from config.settings import STATE_DB_PATH


class StateManager:
    """邮件处理状态管理"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or STATE_DB_PATH
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_emails (
                message_id TEXT PRIMARY KEY,
                account TEXT,
                subject TEXT,
                processed_at DATETIME,
                stage1_result TEXT,
                stage2_category TEXT,
                synced_to_notion INTEGER DEFAULT 0,
                marked_read INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_at
            ON processed_emails(processed_at)
        """)

        conn.commit()
        conn.close()

    def is_processed(self, message_id: str) -> bool:
        """检查邮件是否已处理"""
        if not message_id:
            return False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM processed_emails WHERE message_id = ?",
            (message_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def get_processed_ids(self) -> Set[str]:
        """获取所有已处理的邮件ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT message_id FROM processed_emails")
        ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        return ids

    def mark_processed(
        self,
        message_id: str,
        account: str,
        subject: str,
        stage1_result: str = None,
        stage2_category: str = None,
        synced: bool = False,
        marked_read: bool = False
    ):
        """记录邮件已处理"""
        if not message_id:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO processed_emails
            (message_id, account, subject, processed_at, stage1_result, stage2_category, synced_to_notion, marked_read)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message_id,
            account,
            subject[:200] if subject else "",
            datetime.now().isoformat(),
            stage1_result,
            stage2_category,
            1 if synced else 0,
            1 if marked_read else 0
        ))

        conn.commit()
        conn.close()

    def update_synced(self, message_id: str, synced: bool = True):
        """更新同步状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE processed_emails SET synced_to_notion = ? WHERE message_id = ?",
            (1 if synced else 0, message_id)
        )
        conn.commit()
        conn.close()

    def get_stats(self, days: int = 7) -> dict:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM processed_emails")
        total = cursor.fetchone()[0]

        cursor.execute("""
            SELECT stage1_result, COUNT(*)
            FROM processed_emails
            GROUP BY stage1_result
        """)
        by_stage1 = dict(cursor.fetchall())

        cursor.execute("""
            SELECT stage2_category, COUNT(*)
            FROM processed_emails
            WHERE stage2_category IS NOT NULL
            GROUP BY stage2_category
        """)
        by_category = dict(cursor.fetchall())

        conn.close()

        return {
            "total": total,
            "by_stage1": by_stage1,
            "by_category": by_category,
        }

    def cleanup_old(self, days: int = 30):
        """清理旧记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM processed_emails
            WHERE processed_at < datetime('now', ?)
        """, (f'-{days} days',))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted
