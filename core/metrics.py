"""
性能指标收集器

收集和记录系统运行指标，便于性能分析和问题排查
"""

import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MetricsData:
    """指标数据"""

    # LLM 调用指标
    llm_calls: int = 0
    llm_total_time: float = 0.0
    llm_errors: int = 0
    llm_tokens_used: int = 0

    # 邮件处理指标
    emails_processed: int = 0
    emails_by_category: Dict[str, int] = field(default_factory=dict)

    # Notion 同步指标
    notion_syncs: int = 0
    notion_errors: int = 0
    notion_total_time: float = 0.0

    # 通知指标
    notifications_sent: int = 0
    notifications_failed: int = 0

    # 时间戳
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None


class Metrics:
    """
    性能指标收集器（单例模式）

    线程安全的指标收集器，用于记录系统各模块的性能数据

    使用方法:
        from core.metrics import metrics

        # 记录 LLM 调用
        with metrics.track_llm_call():
            response = call_llm(...)

        # 记录邮件处理
        metrics.record_email("PAPER")

        # 获取摘要
        print(metrics.summary())
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._data = MetricsData()
        self._data.start_time = datetime.now()
        self._lock = threading.Lock()
        self._initialized = True

    def reset(self):
        """重置所有指标"""
        with self._lock:
            self._data = MetricsData()
            self._data.start_time = datetime.now()

    @contextmanager
    def track_llm_call(self):
        """
        跟踪 LLM 调用的上下文管理器

        使用方法:
            with metrics.track_llm_call():
                response = llm.call(...)
        """
        start = time.time()
        try:
            yield
            duration = time.time() - start
            self.record_llm_call(duration)
        except Exception as e:
            duration = time.time() - start
            self.record_llm_error(duration)
            raise

    def record_llm_call(self, duration: float, tokens: int = 0):
        """记录成功的 LLM 调用"""
        with self._lock:
            self._data.llm_calls += 1
            self._data.llm_total_time += duration
            self._data.llm_tokens_used += tokens
            self._data.last_update = datetime.now()

    def record_llm_error(self, duration: float = 0):
        """记录失败的 LLM 调用"""
        with self._lock:
            self._data.llm_errors += 1
            self._data.llm_total_time += duration
            self._data.last_update = datetime.now()

    @contextmanager
    def track_notion_sync(self):
        """
        跟踪 Notion 同步的上下文管理器

        使用方法:
            with metrics.track_notion_sync():
                notion.sync_paper(...)
        """
        start = time.time()
        try:
            yield
            duration = time.time() - start
            self.record_notion_sync(duration, success=True)
        except Exception:
            duration = time.time() - start
            self.record_notion_sync(duration, success=False)
            raise

    def record_notion_sync(self, duration: float, success: bool = True):
        """记录 Notion 同步"""
        with self._lock:
            self._data.notion_syncs += 1
            self._data.notion_total_time += duration
            if not success:
                self._data.notion_errors += 1
            self._data.last_update = datetime.now()

    def record_email(self, category: str):
        """记录处理的邮件"""
        with self._lock:
            self._data.emails_processed += 1
            if category not in self._data.emails_by_category:
                self._data.emails_by_category[category] = 0
            self._data.emails_by_category[category] += 1
            self._data.last_update = datetime.now()

    def record_notification(self, success: bool = True):
        """记录通知发送"""
        with self._lock:
            if success:
                self._data.notifications_sent += 1
            else:
                self._data.notifications_failed += 1
            self._data.last_update = datetime.now()

    @property
    def data(self) -> MetricsData:
        """获取指标数据副本"""
        with self._lock:
            return MetricsData(
                llm_calls=self._data.llm_calls,
                llm_total_time=self._data.llm_total_time,
                llm_errors=self._data.llm_errors,
                llm_tokens_used=self._data.llm_tokens_used,
                emails_processed=self._data.emails_processed,
                emails_by_category=dict(self._data.emails_by_category),
                notion_syncs=self._data.notion_syncs,
                notion_errors=self._data.notion_errors,
                notion_total_time=self._data.notion_total_time,
                notifications_sent=self._data.notifications_sent,
                notifications_failed=self._data.notifications_failed,
                start_time=self._data.start_time,
                last_update=self._data.last_update,
            )

    def summary(self) -> str:
        """生成指标摘要"""
        d = self.data
        runtime = (datetime.now() - d.start_time).total_seconds() if d.start_time else 0

        avg_llm_time = d.llm_total_time / d.llm_calls if d.llm_calls > 0 else 0
        avg_notion_time = d.notion_total_time / d.notion_syncs if d.notion_syncs > 0 else 0

        lines = [
            "=" * 50,
            "性能指标摘要",
            "=" * 50,
            f"运行时间: {runtime:.0f}s",
            "",
            "LLM 调用:",
            f"  - 总调用次数: {d.llm_calls}",
            f"  - 失败次数: {d.llm_errors}",
            f"  - 平均耗时: {avg_llm_time:.2f}s",
            f"  - Token 消耗: {d.llm_tokens_used}",
            "",
            "邮件处理:",
            f"  - 总处理数: {d.emails_processed}",
        ]

        if d.emails_by_category:
            for cat, count in sorted(d.emails_by_category.items()):
                lines.append(f"    - {cat}: {count}")

        lines.extend([
            "",
            "Notion 同步:",
            f"  - 总同步次数: {d.notion_syncs}",
            f"  - 失败次数: {d.notion_errors}",
            f"  - 平均耗时: {avg_notion_time:.2f}s",
            "",
            "通知:",
            f"  - 发送成功: {d.notifications_sent}",
            f"  - 发送失败: {d.notifications_failed}",
            "=" * 50,
        ])

        return "\n".join(lines)

    def log_summary(self):
        """将摘要输出到日志"""
        logger.info(self.summary())


# 全局单例实例
metrics = Metrics()
