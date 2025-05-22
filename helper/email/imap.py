import time
import poplib
import email
import logging
import re
from email.policy import default
from datetime import datetime

from ._email_server import EmailServer

# 设置日志格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('PopEmail')

class Imap(EmailServer):

    def __init__(self, pop_server, pop_port, username, password, email_to = None):
        logger.info(f"Initializing POP3 connection: server={pop_server}, port={pop_port}, user={username}")
        try:
            self.mail = poplib.POP3_SSL(pop_server, pop_port)
            logger.info(f"POP3_SSL connection successful")
            self.mail.user(username)
            logger.info(f"Username set successfully")
            self.mail.pass_(password)
            logger.info(f"Password set successfully")

            self.email_to = email_to
            logger.info(f"Target email: {email_to}")
            
            # 获取邮件数量
            resp, items, octets = self.mail.list()
            msg_count = len(items)
            logger.info(f"Total emails in mailbox: {msg_count}")
            self.latest_id = msg_count if msg_count > 0 else 0
            self.prev_count = self.latest_id
            logger.info(f"Set latest email ID: {self.latest_id}, prev_count: {self.prev_count}")
        except Exception as e:
            logger.error(f"POP3 connection initialization failed: {str(e)}")
            raise

    def fetch_emails_since(self, since_timestamp):
        logger.info(f"Attempting to fetch emails after timestamp {since_timestamp}, current latest ID: {self.latest_id}")
        if self.latest_id is None or self.latest_id == 0:
            logger.warning("No emails to check")
            return None

        try:
            # POP3 不支持像 IMAP 那样的搜索功能
            # 我们将检查最新的邮件
            logger.info(f"Retrieving email ID: {self.latest_id}")
            _, lines, _ = self.mail.retr(self.latest_id)
            raw_email = b'\r\n'.join(lines)
            logger.info(f"Retrieved raw email, length: {len(raw_email)} bytes")
            msg = email.message_from_bytes(raw_email, policy=default)

            # 提取常见头信息
            from_header = msg.get('From')
            to_header = msg.get('To')
            subject_header = msg.get('Subject')
            date_header = msg.get('Date')
            
            logger.info(f"Email details: From={from_header}, To={to_header}, Subject={subject_header}, Date={date_header}")

            if self.email_to not in (None, to_header):
                logger.warning(f"Target email mismatch: Expected={self.email_to}, Actual={to_header}")
                return None

            logger.info(f"Parsing email date: {date_header}")
            try:
                email_datetime = datetime.strptime(date_header.replace(' (UTC)', ''), '%a, %d %b %Y %H:%M:%S %z').timestamp()
                logger.info(f"Email timestamp: {email_datetime}, comparison timestamp: {since_timestamp}")
            except Exception as e:
                logger.error(f"Date parsing failed: {str(e)}, raw date: {date_header}")
                return None
                
            if email_datetime < since_timestamp:
                logger.warning(f"Email is too old ({email_datetime} < {since_timestamp})")
                return None

            logger.info("Getting email body")
            text_part = msg.get_body(preferencelist=('plain',))
            if text_part:
                logger.info("Found plain text part")
                content = text_part.get_content()
            else:
                logger.info("No plain text part found, getting all content")
                content = msg.get_content()
            
            logger.info(f"Email content first 100 chars: {content[:100] if content else 'No content'}")
            # Log email content for debugging verification code
            logger.info(f"Full email content for code extraction: {content}")
            
            # Look for common verification code patterns
            code_match = re.search(r'(\d{4,8})', content)
            if code_match:
                logger.info(f"Possible verification code found: {code_match.group(1)}")
            else:
                logger.warning("No verification code pattern found in email content")

            return {
                "from": from_header,
                "to": to_header,
                "date": date_header,
                "subject": subject_header,
                "content": content
            }
        except Exception as e:
            logger.error(f"Failed to fetch email: {str(e)}")
            return None
    
    def wait_for_new_message(self, delay=5, timeout=60):
        logger.info(f"Waiting for new message, delay={delay}s, timeout={timeout}s")
        start_time = time.time()

        while time.time() - start_time <= timeout:
            try:
                # 更新邮件数量
                logger.info("Checking for new emails")
                resp, items, octets = self.mail.list()
                msg_count = len(items)
                logger.info(f"Current email count: {msg_count}, previous count: {self.prev_count}")
                
                if msg_count > self.prev_count:
                    logger.info(f"New email(s) found: {msg_count} > {self.prev_count}")
                    # Find new email ID - typically the last one
                    self.latest_id = msg_count
                    logger.info(f"Setting latest email ID to: {self.latest_id}")
                    email = self.fetch_emails_since(start_time)
                    # Update previous count after processing
                    self.prev_count = msg_count
                    if email is not None:
                        logger.info("Successfully retrieved new email")
                        return email
                    else:
                        logger.warning("Retrieved new email does not meet criteria")
                else:
                    logger.info("No new emails")
                    # Update previous count to handle fluctuations
                    self.prev_count = msg_count
            except Exception as e:
                logger.error(f"Error checking for new emails: {str(e)}")
                pass
            
            logger.info(f"Waiting {delay} seconds before checking again")
            time.sleep(delay)

        logger.warning(f"Timeout waiting for new message ({timeout} seconds)")
        return None
