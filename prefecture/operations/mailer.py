"""Gmail mailer tasks for Prefecture."""

import base64
from email import encoders
from email.mime import base
from email.mime import multipart
from email.mime import text
import mimetypes
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
from prefecture.operations import templating
import requests
import yaml


class GmailMailer:
    """Sends emails using Gmail API."""

    def __init__(
        self,
        *,
        config_dir: pathlib.Path,
        run_dir: pathlib.Path,
        gmail_client_id: str,
        gmail_client_secret: str,
        gmail_refresh_token: str,
        recipients: list[str],
        content_file_name: str,
        attachments: list[dict[str, str]] | None = None,
    ):
        """Initializes the GmailMailer."""
        self.client_id = gmail_client_id
        self.client_secret = gmail_client_secret
        self.refresh_token = gmail_refresh_token
        self.recipients = recipients
        self.content_file_name = content_file_name
        self.attachments = attachments or []
        self.config_dir = config_dir
        self.run_dir = run_dir

    def __repr__(self) -> str:
        return f"GmailMailer(recipients={self.recipients}, content_file_name={repr(self.content_file_name)}, attachments={self.attachments})"

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
    def __call__(self):
        """Sends email with content from specified file."""
        content_path = self.run_dir / self.content_file_name
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

        env = jinja2.Environment(loader=jinja2.PackageLoader("prefecture.operations", ""))
        template = env.get_template("email_base.html.j2")
        rendered_html = template.render(context)

        inlined_html = premailer.transform(rendered_html)

        # Read attachments if specified
        attachments_to_add = []
        for att in self.attachments:
            if "image_file_name" in att:
                image_name = att["image_file_name"]
                image_path = self.run_dir / image_name
                with open(image_path, "rb") as f:
                    data = f.read()
                mime_type, _ = mimetypes.guess_type(image_path)
                if mime_type is None:
                    mime_type = "application/octet-stream"
                main_type, sub_type = mime_type.split("/", 1)
                attachments_to_add.append({
                    "data": data,
                    "name": image_path.name,
                    "main_type": main_type,
                    "sub_type": sub_type,
                })

        # Send email
        try:
            access_token = self.get_access_token()

            for recipient in self.recipients:
                msg = multipart.MIMEMultipart()
                msg["To"] = recipient
                msg["Subject"] = subject

                msg.attach(text.MIMEText(inlined_html, "html"))

                for att in attachments_to_add:
                    img_part = base.MIMEBase(att["main_type"], att["sub_type"])
                    img_part.set_payload(att["data"])
                    encoders.encode_base64(img_part)
                    img_part.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=att["name"],
                    )
                    msg.attach(img_part)

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

    @property
    def dependencies(self) -> set[str]:
        deps = set()
        if getattr(self, "content_file_name", None):
            path = pathlib.Path(self.content_file_name)
            if not path.is_absolute():
                path = self.run_dir / path
            deps.add(str(path.resolve()))
        for att in getattr(self, "attachments", []):
            if "image_file_name" in att:
                path = pathlib.Path(att["image_file_name"])
                if not path.is_absolute():
                    path = self.run_dir / path
                deps.add(str(path.resolve()))
        return deps

    @property
    def outputs(self) -> set[str]:
        return set()



