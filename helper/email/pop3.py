import time
import poplib
import email
from email.policy import default
from datetime import datetime

from ._email_server import EmailServer

class Pop3(EmailServer):

    def __init__(self, pop3_server, pop3_port, username, password, email_to = None):
        self.pop3_server = pop3_server
        self.pop3_port = pop3_port
        self.username = username
        self.password = password
        self.email_to = email_to

        self.mail = poplib.POP3_SSL(pop3_server, pop3_port)
        self.mail.user(username)
        self.mail.pass_(password)
        
        # 记录最后检查的时间点，而不是消息数量
        self.last_check_time = time.time()
        # 确保初始连接正常
        self.mail.noop()

    def fetch_emails_since(self, since_timestamp):
        try:
            # 保持连接活跃
            self.mail.noop()
            
            # 获取邮件列表
            message_count = len(self.mail.list()[1])
            if message_count == 0:
                return None
                
            # 检查所有邮件，从最新的开始
            for i in range(message_count, 0, -1):
                try:
                    # 获取邮件内容
                    resp, lines, octets = self.mail.retr(i)
                    
                    # 解析邮件
                    raw_email = b'\n'.join(lines)
                    msg = email.message_from_bytes(raw_email, policy=default)
                    
                    # 提取邮件头信息
                    from_header = msg.get('From')
                    to_header = msg.get('To')
                    subject_header = msg.get('Subject')
                    date_header = msg.get('Date')
                    
                    # 如果指定了接收邮箱，则检查收件人
                    if self.email_to is not None and self.email_to not in to_header:
                        continue
                    
                    # 提取邮件日期并比较
                    if date_header:
                        try:
                            email_datetime = datetime.strptime(date_header.replace(' (UTC)', ''), '%a, %d %b %Y %H:%M:%S %z').timestamp()
                            # 只处理新邮件，检查是否是在指定时间之后收到的
                            if email_datetime < since_timestamp:
                                continue
                        except Exception as e:
                            # 日期解析失败，考虑时间戳格式可能不同
                            pass
                    
                    # 获取邮件正文
                    content = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            # 跳过附件
                            if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is not None:
                                continue
                            # 提取文本内容
                            if part.get_content_type() == 'text/plain':
                                content = part.get_payload(decode=True).decode()
                                break
                    else:
                        content = msg.get_payload(decode=True).decode()
                    
                    # 返回找到的第一封符合条件的邮件
                    return {
                        "from": from_header,
                        "to": to_header,
                        "date": date_header,
                        "subject": subject_header,
                        "content": content
                    }
                except Exception as e:
                    print(f"Error processing email {i}: {str(e)}")
                    continue
            
            return None
        except Exception as e:
            print(f"Error fetching emails: {str(e)}")
            # 尝试重新连接
            try:
                self.mail.quit()
                self.mail = poplib.POP3_SSL(self.pop3_server, self.pop3_port)
                self.mail.user(self.username)
                self.mail.pass_(self.password)
            except:
                pass
            return None
    
    def wait_for_new_message(self, delay=5, timeout=60):
        start_time = time.time()
        
        print(f"[POP3] Waiting for new emails, timeout: {timeout} seconds")
        
        while time.time() - start_time <= timeout:
            try:
                email_data = self.fetch_emails_since(start_time)
                if email_data is not None:
                    print(f"[POP3] Email received successfully, subject: {email_data.get('subject', 'No subject')}")
                    return email_data
            except Exception as e:
                print(f"[POP3] Error while waiting for email: {str(e)}")
            
            time.sleep(delay)
        
        print(f"[POP3] Timeout waiting for email, no new messages received")
        return None 