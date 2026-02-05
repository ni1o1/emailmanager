"""
邮件客户端
负责IMAP读取和SMTP发送
"""

import imaplib
import smtplib
import email
import re
from email.message import Message
from email.header import decode_header
from email.utils import parsedate_to_datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, List, Dict

from config.settings import EMAIL_ACCOUNTS, EMAIL_SIGNATURE


class EmailClient:
    """邮件客户端"""

    def __init__(self):
        self.accounts = EMAIL_ACCOUNTS

    @staticmethod
    def _decode_header(header_value: Optional[str]) -> str:
        """解码邮件头部"""
        if header_value is None:
            return ""
        decoded_parts = decode_header(header_value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                charset = charset or 'utf-8'
                try:
                    result.append(part.decode(charset))
                except (UnicodeDecodeError, LookupError):
                    try:
                        result.append(part.decode('gbk'))
                    except UnicodeDecodeError:
                        result.append(part.decode('utf-8', errors='ignore'))
            else:
                result.append(part)
        return ''.join(result)

    @staticmethod
    def _get_body(msg: Message, max_length: int = 3000) -> str:
        """提取邮件正文"""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in content_disposition:
                    continue
                if content_type == "text/plain":
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode(charset, errors='ignore')
                            break
                    except Exception:
                        continue
                elif content_type == "text/html" and not body:
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        payload = part.get_payload(decode=True)
                        if payload:
                            html = payload.decode(charset, errors='ignore')
                            body = re.sub(r'<[^>]+>', '', html)
                            body = re.sub(r'\s+', ' ', body).strip()
                    except Exception:
                        continue
        else:
            try:
                charset = msg.get_content_charset() or 'utf-8'
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode(charset, errors='ignore')
            except Exception:
                pass
        return body.strip()[:max_length]

    def fetch_unread_emails(self, account_name: str = None, limit: int = 50, max_age_days: int = None) -> List[Dict]:
        """获取未读邮件

        Args:
            account_name: 指定账户名，None则获取所有账户
            limit: 每个账户最多获取的邮件数
            max_age_days: 只获取最近N天的邮件，None则不限制

        Returns:
            邮件列表，每个邮件包含基础信息
        """
        from datetime import timedelta

        all_emails = []
        accounts = self.accounts if account_name is None else [
            a for a in self.accounts if a["name"] == account_name
        ]

        # 计算日期过滤条件
        since_date = None
        if max_age_days:
            since_date = (datetime.now() - timedelta(days=max_age_days)).strftime("%d-%b-%Y")

        for account in accounts:
            try:
                conn = imaplib.IMAP4_SSL(account["imap_host"], account["imap_port"])
                conn.login(account["address"], account["password"])
                conn.select("INBOX")

                # 只获取未读邮件（可选日期过滤）
                if since_date:
                    status, messages = conn.search(None, f'(UNSEEN SINCE {since_date})')
                else:
                    status, messages = conn.search(None, "UNSEEN")
                if status != "OK":
                    continue

                email_ids = messages[0].split()
                # 取最新的limit封
                email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids

                for email_id in email_ids:
                    try:
                        # BODY.PEEK 不会标记为已读
                        status, msg_data = conn.fetch(email_id, "(BODY.PEEK[] FLAGS)")
                        if status != "OK":
                            continue

                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)

                        # 提取Message-ID用于去重
                        message_id = msg.get("Message-ID", "")

                        subject = self._decode_header(msg.get("Subject"))
                        from_addr = self._decode_header(msg.get("From"))
                        date_str = msg.get("Date")

                        date = None
                        if date_str:
                            try:
                                date = parsedate_to_datetime(date_str)
                            except Exception:
                                pass

                        all_emails.append({
                            "message_id": message_id,
                            "email_id": email_id.decode() if isinstance(email_id, bytes) else str(email_id),
                            "account": account["name"],
                            "subject": subject,
                            "from": from_addr,
                            "from_lower": from_addr.lower(),
                            "date": date,
                            "date_str": date.strftime("%Y-%m-%d %H:%M") if date else "未知",
                            "body": None,  # 延迟加载正文
                            "_msg": msg,   # 保存原始消息用于后续提取
                        })
                    except Exception:
                        continue

                conn.logout()
            except Exception as e:
                print(f"   ⚠️ 获取 {account['name']} 邮件失败: {e}")

        # 按日期排序
        all_emails.sort(key=lambda x: x["date"] or datetime.min, reverse=True)
        return all_emails

    def load_email_body(self, email_item: Dict) -> str:
        """延迟加载邮件正文"""
        if email_item.get("body") is not None:
            return email_item["body"]

        msg = email_item.get("_msg")
        if msg:
            email_item["body"] = self._get_body(msg)
            del email_item["_msg"]  # 释放内存
        else:
            email_item["body"] = ""

        return email_item["body"]

    def mark_as_read(self, account_name: str, email_id: str) -> bool:
        """标记邮件为已读"""
        account = next((a for a in self.accounts if a["name"] == account_name), None)
        if not account:
            return False

        try:
            conn = imaplib.IMAP4_SSL(account["imap_host"], account["imap_port"])
            conn.login(account["address"], account["password"])
            conn.select("INBOX")
            conn.store(email_id, '+FLAGS', '\\Seen')
            conn.logout()
            return True
        except Exception:
            return False

    def fetch_recent_emails(self, days: int = 7, limit: int = 100) -> List[Dict]:
        """获取最近N天的所有邮件（包括已读）

        Args:
            days: 获取最近多少天的邮件
            limit: 每个账户最多获取的邮件数

        Returns:
            邮件列表
        """
        from datetime import timedelta
        all_emails = []

        # 计算日期范围
        since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

        for account in self.accounts:
            try:
                conn = imaplib.IMAP4_SSL(account["imap_host"], account["imap_port"])
                conn.login(account["address"], account["password"])
                conn.select("INBOX")

                # 获取指定日期之后的所有邮件
                status, messages = conn.search(None, f'(SINCE {since_date})')
                if status != "OK":
                    continue

                email_ids = messages[0].split()
                # 取最新的limit封
                email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids

                print(f"   {account['name']}: 找到 {len(email_ids)} 封邮件")

                for email_id in email_ids:
                    try:
                        # BODY.PEEK 不会标记为已读
                        status, msg_data = conn.fetch(email_id, "(BODY.PEEK[] FLAGS)")
                        if status != "OK":
                            continue

                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)

                        message_id = msg.get("Message-ID", "")
                        subject = self._decode_header(msg.get("Subject"))
                        from_addr = self._decode_header(msg.get("From"))
                        date_str = msg.get("Date")

                        date = None
                        if date_str:
                            try:
                                date = parsedate_to_datetime(date_str)
                            except Exception:
                                pass

                        all_emails.append({
                            "message_id": message_id,
                            "email_id": email_id.decode() if isinstance(email_id, bytes) else str(email_id),
                            "account": account["name"],
                            "subject": subject,
                            "from": from_addr,
                            "from_lower": from_addr.lower(),
                            "date": date,
                            "date_str": date.strftime("%Y-%m-%d %H:%M") if date else "未知",
                            "body": None,
                            "_msg": msg,
                        })
                    except Exception:
                        continue

                conn.logout()
            except Exception as e:
                print(f"   ⚠️ 获取 {account['name']} 邮件失败: {e}")

        # 按日期排序
        all_emails.sort(key=lambda x: x["date"] or datetime.min, reverse=True)
        return all_emails

    def send_email(self, to_addr: str, subject: str, body: str,
                   from_account: str = None, add_signature: bool = True) -> bool:
        """发送邮件"""
        account = next(
            (a for a in self.accounts if a["name"] == (from_account or "QQ邮箱")),
            self.accounts[0]
        )

        full_body = body + EMAIL_SIGNATURE if add_signature else body

        msg = MIMEMultipart()
        msg['From'] = account["address"]
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg.attach(MIMEText(full_body, 'plain', 'utf-8'))

        try:
            with smtplib.SMTP_SSL(account["smtp_host"], account["smtp_port"]) as server:
                server.login(account["address"], account["password"])
                server.send_message(msg)
                return True
        except Exception as e:
            print(f"   ⚠️ 发送失败: {e}")
            return False
