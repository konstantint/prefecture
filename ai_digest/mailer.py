import os
import base64
import requests
import markdown
import premailer
import re
import yaml
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from prefect import task
from ai_digest.templating import render_template

class GmailMailer:
    def __init__(self, *, gmail_client_id: str, gmail_client_secret: str, gmail_refresh_token: str, recipients: list[str]):
        self.client_id = gmail_client_id
        self.client_secret = gmail_client_secret
        self.refresh_token = gmail_refresh_token
        self.recipients = recipients
        
    def get_access_token(self) -> str:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]
        
    def __call__(self, md_content: str):
        # Parse frontmatter
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", md_content, re.DOTALL)
        if match:
            frontmatter_text = match.group(1)
            metadata = yaml.safe_load(frontmatter_text)
            subject = metadata.get("subject", "No Subject")
            body = md_content[match.end():]
        else:
            subject = "No Subject"
            body = md_content
            
        # Compile HTML
        html_body = markdown.markdown(body)
        
        context = {"content": html_body, "subject": subject}
        from jinja2 import Environment, PackageLoader
        env = Environment(loader=PackageLoader('ai_digest', ''))
        template = env.get_template('email_base.html.j2')
        rendered_html = template.render(context)
        
        inlined_html = premailer.transform(rendered_html)
        
        # Send email
        try:
            access_token = self.get_access_token()
            
            for recipient in self.recipients:
                msg = MIMEMultipart()
                msg["To"] = recipient
                msg["Subject"] = subject
                
                msg.attach(MIMEText(inlined_html, "html"))
                
                raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
                
                response = requests.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"raw": raw_message},
                )
                response.raise_for_status()
                print(f"Successfully sent email to {recipient}")
                
        except Exception as e:
            print(f"Error sending email: {e}")
            raise

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    
    # Load environment variables from .env file if it exists in CWD
    load_dotenv(override=True)
    
    print("Testing GmailMailer...")
    
    if len(sys.argv) < 2:
        print("Usage: python mailer.py <target_email>")
        print("Test mode: Not sending any emails because no target email provided.")
        sys.exit(0)
        
    target_email = sys.argv[1]
    print(f"Target email: {target_email}")
    
    # Create a dummy markdown content with frontmatter
    md_content = """---
subject: Test Frontmatter Subject
---
# Test Digest
This is a **test** digest email with frontmatter.
"""
    
    mailer = GmailMailer(
        gmail_client_id=os.environ.get("GMAIL_CLIENT_ID"),
        gmail_client_secret=os.environ.get("GMAIL_CLIENT_SECRET"),
        gmail_refresh_token=os.environ.get("GMAIL_REFRESH_TOKEN"),
        recipients=[target_email]
    )
    
    try:
        mailer(md_content)
    except Exception as e:
        print(f"Error in mailer test: {e}")
