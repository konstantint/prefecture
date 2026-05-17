"""Gmail mailer tasks for Prefecture."""

import base64
from email.mime import multipart
from email.mime import text
import os
import pathlib
import re
import sys

import dotenv
import jinja2
from markdown_it import MarkdownIt
import premailer
import prefect
from prefect import cache_policies
from prefecture import templating
import requests
import yaml


class GmailMailer:
    """Sends emails using Gmail API."""

    def __init__(
        self,
        *,
        config_dir: pathlib.Path,
        gmail_client_id: str,
        gmail_client_secret: str,
        gmail_refresh_token: str,
        recipients: list[str],
        content_file_name: str,
    ):
        """Initializes the GmailMailer."""
        self.client_id = gmail_client_id
        self.client_secret = gmail_client_secret
        self.refresh_token = gmail_refresh_token
        self.recipients = recipients
        self.content_file_name = content_file_name
        self.config_dir = config_dir

    def get_access_token(self) -> str:
        """Gets OAuth2 access token for Gmail."""
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

    @prefect.task(name="GmailMailer")
    def __call__(self, run_dir: pathlib.Path):
        """Sends email with content from specified file."""
        content_path = run_dir / self.content_file_name
        with open(content_path, "r") as f:
            md_content = f.read()
        # Parse frontmatter
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", md_content, re.DOTALL)
        if match:
            frontmatter_text = match.group(1)
            metadata = yaml.safe_load(frontmatter_text)
            subject = metadata.get("subject", "No Subject")
            body = md_content[match.end() :]
        else:
            subject = "No Subject"
            body = md_content

        # Compile HTML
        md = MarkdownIt('gfm-like')
        html_body = md.render(body)

        context = {"content": html_body, "subject": subject}

        env = jinja2.Environment(loader=jinja2.PackageLoader("prefecture", ""))
        template = env.get_template("email_base.html.j2")
        rendered_html = template.render(context)

        inlined_html = premailer.transform(rendered_html)

        # Send email
        try:
            access_token = self.get_access_token()

            for recipient in self.recipients:
                msg = multipart.MIMEMultipart()
                msg["To"] = recipient
                msg["Subject"] = subject

                msg.attach(text.MIMEText(inlined_html, "html"))

                raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode(
                    "utf-8"
                )

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
    # Load environment variables from .env file if it exists in CWD
    dotenv.load_dotenv(override=True)

    print("Testing GmailMailer...")

    if len(sys.argv) < 2:
        print("Usage: python mailer.py <target_email>")
        print(
            "Test mode: Not sending any emails because no target email provided."
        )
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

    # Note: This will fail because __init__ requires more arguments now.
    gmail_mailer = GmailMailer(
        gmail_client_id=os.environ.get("GMAIL_CLIENT_ID"),
        gmail_client_secret=os.environ.get("GMAIL_CLIENT_SECRET"),
        gmail_refresh_token=os.environ.get("GMAIL_REFRESH_TOKEN"),
        recipients=[target_email],
    )

    try:
        gmail_mailer(md_content)
    except Exception as e:
        print(f"Error in mailer test: {e}")
