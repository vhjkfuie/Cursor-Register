import time
import poplib
import email
from email.policy import default
from datetime import datetime

from ._email_server import EmailServer

class Pop3(EmailServer):

    def __init__(self, pop3_server, pop3_port, username, password, email_to = None):
        self.mail = poplib.POP3_SSL(pop3_server, pop3_port)
        self.mail.user(username)
        self.mail.pass_(password)

        self.email_to = email_to
        
        # Get message count
        message_count, _ = self.mail.stat()
        self.last_msg_count = message_count

    def fetch_emails_since(self, since_timestamp):
        # Get current message count
        message_count, _ = self.mail.stat()
        
        # Check if there are new messages
        if message_count <= self.last_msg_count:
            return None
        
        # Update the last message count
        new_messages = message_count - self.last_msg_count
        self.last_msg_count = message_count
        
        # Get the latest message
        resp, lines, octets = self.mail.retr(message_count)
        
        # Convert byte data to message
        raw_email = b'\n'.join(lines)
        msg = email.message_from_bytes(raw_email, policy=default)

        # Extract common headers
        from_header = msg.get('From')
        to_header = msg.get('To')
        subject_header = msg.get('Subject')
        date_header = msg.get('Date')

        if self.email_to not in (None, to_header):
            return None

        # Parse date if it exists
        if date_header:
            try:
                email_datetime = datetime.strptime(date_header.replace(' (UTC)', ''), '%a, %d %b %Y %H:%M:%S %z').timestamp()
                if email_datetime < since_timestamp:
                    return None
            except:
                # If date parsing fails, proceed anyway
                pass

        # Get email content
        text_part = msg.get_body(preferencelist=('plain',))
        content = text_part.get_content() if text_part else msg.get_content()

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
                email = self.fetch_emails_since(start_time)
                if email is not None:
                    return email
            except Exception as e:
                pass
            time.sleep(delay)

        return None 