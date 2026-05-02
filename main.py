#!/usr/bin/env python3
"""
邮件管理系统 - 统一入口

使用方法:
    python main.py              # 运行一次检查
    python main.py --watch      # 持续监控模式
    python main.py --stats      # 查看统计信息
"""

import os
import sys
import argparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.logger import get_logger, setup_logging
from core.validator import require_valid_config
from core.notification_manager import NotificationManager
from scheduler.watcher import EmailWatcher
from core.state import StateManager

# 初始化日志系统
setup_logging()
logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='邮件管理系统')
    parser.add_argument('--watch', '-w', action='store_true', help='持续监控模式')
    parser.add_argument('--interval', '-i', type=int, default=600, help='检查间隔（秒）')
    parser.add_argument('--stats', '-s', action='store_true', help='查看统计信息')
    parser.add_argument('--cleanup', '-c', type=int, metavar='DAYS', help='清理N天前的记录')
    parser.add_argument('--send-test', metavar='MESSAGE', help='向飞书发送测试消息')

    args = parser.parse_args()

    if args.stats:
        # 显示统计信息
        state = StateManager()
        stats = state.get_stats()
        print("\n📊 邮件处理统计")
        print("=" * 40)
        print(f"总处理邮件: {stats['total']}")
        print("\nStage 1 分类:")
        for k, v in stats.get('by_stage1', {}).items():
            print(f"  {k}: {v}")
        print("\nStage 2 分类:")
        for k, v in stats.get('by_category', {}).items():
            print(f"  {k}: {v}")
        return

    if args.cleanup:
        state = StateManager()
        deleted = state.cleanup_old(args.cleanup)
        print(f"✓ 已清理 {deleted} 条旧记录")
        return

    if args.send_test:
        notifier = NotificationManager()
        if not notifier.has_enabled_backends():
            print("飞书通知未启用")
            return

        sent_count = notifier.send_text(args.send_test, respect_quiet_hours=False)
        print(f"已尝试发送到 {sent_count} 个飞书通知渠道")
        return

    require_valid_config()

    watcher = EmailWatcher()

    if args.watch:
        # 持续监控模式
        watcher.run_forever(interval=args.interval)
    else:
        # 运行一次
        watcher.run_once()


if __name__ == "__main__":
    main()
