"""
测试状态管理器
"""

import pytest
import os
import sqlite3
from datetime import datetime, timedelta

from core.state import StateManager


class TestStateManager:
    """测试状态管理器"""

    @pytest.fixture
    def state_manager(self, tmp_path):
        """创建临时数据库的状态管理器"""
        db_path = tmp_path / "test_state.db"
        return StateManager(str(db_path))

    def _get_conn(self, state_manager):
        """获取数据库连接（用于测试验证）"""
        return sqlite3.connect(state_manager.db_path)

    def test_init_creates_table(self, state_manager):
        """测试初始化创建表"""
        # 验证表存在
        conn = self._get_conn(state_manager)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_emails'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_mark_processed(self, state_manager):
        """测试标记邮件为已处理"""
        state_manager.mark_processed(
            message_id="<test123@example.com>",
            account="QQ邮箱",
            subject="Test Subject",
            stage1_result="PAPER"
        )

        # 验证记录存在
        conn = self._get_conn(state_manager)
        cursor = conn.execute(
            "SELECT * FROM processed_emails WHERE message_id = ?",
            ("<test123@example.com>",)
        )
        row = cursor.fetchone()
        assert row is not None
        conn.close()

    def test_is_processed(self, state_manager):
        """测试检查邮件是否已处理"""
        message_id = "<test456@example.com>"

        # 未处理
        assert state_manager.is_processed(message_id) is False

        # 标记处理
        state_manager.mark_processed(
            message_id=message_id,
            account="QQ邮箱",
            subject="Test",
            stage1_result="TRASH"
        )

        # 已处理
        assert state_manager.is_processed(message_id) is True

    def test_get_processed_ids(self, state_manager):
        """测试获取已处理的邮件 ID 列表"""
        # 添加几封邮件
        for i in range(3):
            state_manager.mark_processed(
                message_id=f"<test{i}@example.com>",
                account="QQ邮箱",
                subject=f"Test {i}",
                stage1_result="NOTICE"
            )

        ids = state_manager.get_processed_ids()
        assert len(ids) == 3
        assert "<test0@example.com>" in ids
        assert "<test1@example.com>" in ids
        assert "<test2@example.com>" in ids

    def test_get_stats(self, state_manager):
        """测试获取统计信息"""
        # 添加不同分类的邮件
        categories = ["PAPER", "PAPER", "TRASH", "BILLING", "NOTICE"]
        for i, cat in enumerate(categories):
            state_manager.mark_processed(
                message_id=f"<test{i}@example.com>",
                account="QQ邮箱",
                subject=f"Test {i}",
                stage1_result=cat
            )

        stats = state_manager.get_stats()
        assert stats["total"] == 5
        assert stats["by_stage1"]["PAPER"] == 2
        assert stats["by_stage1"]["TRASH"] == 1
        assert stats["by_stage1"]["BILLING"] == 1
        assert stats["by_stage1"]["NOTICE"] == 1

    def test_cleanup_old(self, state_manager):
        """测试清理旧记录"""
        # 添加一条"旧"记录（需要手动设置时间）
        old_time = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
        conn = self._get_conn(state_manager)
        conn.execute(
            """
            INSERT INTO processed_emails
            (message_id, account, subject, processed_at, stage1_result)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("<old@example.com>", "QQ邮箱", "Old Email", old_time, "TRASH")
        )
        conn.commit()
        conn.close()

        # 添加一条新记录
        state_manager.mark_processed(
            message_id="<new@example.com>",
            account="QQ邮箱",
            subject="New Email",
            stage1_result="PAPER"
        )

        # 清理 30 天前的记录
        deleted = state_manager.cleanup_old(30)
        assert deleted == 1

        # 验证只剩下新记录
        ids = state_manager.get_processed_ids()
        assert "<new@example.com>" in ids
        assert "<old@example.com>" not in ids

    def test_mark_processed_with_stage2(self, state_manager):
        """测试标记处理时包含 Stage 2 分类"""
        state_manager.mark_processed(
            message_id="<test@example.com>",
            account="QQ邮箱",
            subject="Test",
            stage1_result="PAPER",
            stage2_category="Paper/Submission",
            synced=True,
            marked_read=True
        )

        conn = self._get_conn(state_manager)
        cursor = conn.execute(
            "SELECT stage2_category, synced_to_notion, marked_read FROM processed_emails WHERE message_id = ?",
            ("<test@example.com>",)
        )
        row = cursor.fetchone()
        assert row[0] == "Paper/Submission"
        assert row[1] == 1  # True
        assert row[2] == 1  # True
        conn.close()

    def test_duplicate_message_id(self, state_manager):
        """测试重复的 message_id（应该更新而不是报错）"""
        message_id = "<dup@example.com>"

        # 第一次插入
        state_manager.mark_processed(
            message_id=message_id,
            account="QQ邮箱",
            subject="First",
            stage1_result="UNKNOWN"
        )

        # 第二次插入（相同 ID）
        state_manager.mark_processed(
            message_id=message_id,
            account="QQ邮箱",
            subject="Second",
            stage1_result="PAPER"
        )

        # 验证只有一条记录
        conn = self._get_conn(state_manager)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM processed_emails WHERE message_id = ?",
            (message_id,)
        )
        assert cursor.fetchone()[0] == 1
        conn.close()
