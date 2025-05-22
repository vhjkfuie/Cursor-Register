import time
import poplib
import email
from email.policy import default
from datetime import datetime

from ._email_server import EmailServer

class Imap(EmailServer):

    def __init__(self, pop_server, pop_port, username, password, email_to = None):
        self.mail = poplib.POP3_SSL(pop_server, pop_port)
        self.mail.user(username)
        self.mail.pass_(password)

        self.email_to = email_to
        
        # Get message count
        msg_count = len(self.mail.list()[1])
        self.latest_id = msg_count if msg_count > 0 else None

    def fetch_emails_since(self, since_timestamp):
        if self.latest_id is None or self.latest_id == 0:
            return None

        # POP3 doesn't have search capability like IMAP
        # We'll check the latest email
        _, lines, _ = self.mail.retr(self.latest_id)
        raw_email = b'\r\n'.join(lines)
        msg = email.message_from_bytes(raw_email, policy=default)

        # Extract common headers
        from_header = msg.get('From')
        to_header = msg.get('To')
        subject_header = msg.get('Subject')
        date_header = msg.get('Date')

        if self.email_to not in (None, to_header):
            return None

        email_datetime = datetime.strptime(date_header.replace(' (UTC)', ''), '%a, %d %b %Y %H:%M:%S %z').timestamp()
        if email_datetime < since_timestamp:
            return None

        text_part = msg.get_body(preferencelist=('plain',))
        content = text_part.get_content() if text_part else msg.get_content()

        # Increment latest ID for next check
        self.latest_id += 1

        return {
            "from": from_header,
            "to": to_header,
            "date": date_header,
            "subject": subject_header,
            "content": content
        }
    
    def wait_for_new_message(self, delay=5, timeout=60):
        start_time = time.time()

        while time.time() - start_time <= timeout:
            try:
                # Update message count before checking
                msg_count = len(self.mail.list()[1])
                if msg_count > self.latest_id:
                    self.latest_id = msg_count
                    email = self.fetch_emails_since(start_time)
                    if email is not None:
                        return email
            except:
                pass
            time.sleep(delay)

        return None
