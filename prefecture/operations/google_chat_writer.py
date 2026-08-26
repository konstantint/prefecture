"""Google Chat writer tasks for Prefecture."""

import argparse
import mimetypes
import os
import pathlib
import typing

import dotenv
from google.auth.transport import requests
from google.oauth2 import credentials
from googleapiclient import discovery
from googleapiclient.http import MediaFileUpload
import prefect
import yaml

SCOPES = ['https://www.googleapis.com/auth/chat.messages.create']


class GoogleChatWriter:
    """Sends messages to Google Chat spaces."""

    def __init__(
        self,
        *,
        config_dir: str | pathlib.Path,
        run_dir: str | pathlib.Path,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        space_id: str,
        content_file_name: str | None = None,
        content: str | None = None,
        use_markdown: bool = True,
        attachments: list[dict[str, str]] | None = None,
    ):
        """Initializes the GoogleChatWriter."""
        if (content_file_name is not None) and (content is not None):
            raise ValueError(
                "Specify either content_file_name or content, not both"
            )
        if (content_file_name is None) and (content is None):
            raise ValueError(
                "Must specify either content_file_name or content"
            )

        self.config_dir = pathlib.Path(config_dir)
        self.run_dir = pathlib.Path(run_dir)
        self.client_id = os.path.expandvars(client_id)
        self.client_secret = os.path.expandvars(client_secret)
        self.refresh_token = os.path.expandvars(refresh_token)
        self.space_id = space_id
        self.content_file_name = content_file_name
        self.content = content
        self.use_markdown = use_markdown
        self.attachments = attachments or []

    def __repr__(self) -> str:
        return f"GoogleChatWriter(space_id={repr(self.space_id)}, use_markdown={self.use_markdown}, content_file_name={repr(self.content_file_name)}, content={repr(self.content)}, attachments={self.attachments})"

    def _get_credentials(self) -> credentials.Credentials:
        """Gets Google API credentials."""
        creds = credentials.Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=SCOPES,
        )
        try:
            creds.refresh(requests.Request())
        except Exception as e:
            print(f"Failed to refresh token: {e}")
            raise
        return creds

    @prefect.task(name="GoogleChatWriter")
    def __call__(self) -> None:
        """Sends a message to a Google Chat space."""
        print(f"Starting Google Chat writer in {self.run_dir}")

        if (
            not self.client_id
            or not self.client_secret
            or not self.refresh_token
        ):
            raise ValueError(
                "client_id, client_secret, and refresh_token must be specified"
            )

        if self.content is not None:
            message_text = self.content
        else:
            content_path = self.run_dir / self.content_file_name
            with open(content_path, "r", encoding="utf-8") as f:
                message_text = f.read()

        creds = self._get_credentials()
        service = discovery.build("chat", "v1", credentials=creds)

        parent = f"spaces/{self.space_id}"

        try:
            body: dict[str, typing.Any] = {"text": message_text}
            if self.use_markdown:
                # Tell Google Chat API to parse as standard Markdown
                body["markupSyntax"] = "MARKUP_SYNTAX_MARKDOWN"

            appended_attachments = []
            for att in self.attachments:
                if "image_file_name" in att:
                    image_name = att["image_file_name"]
                    image_path = self.run_dir / image_name
                    mime_type, _ = mimetypes.guess_type(image_path)
                    if mime_type is None:
                        mime_type = "application/octet-stream"
                    media = MediaFileUpload(str(image_path), mimetype=mime_type)
                    upload_result = service.media().upload(
                        parent=parent,
                        body={'filename': image_path.name},
                        media_body=media
                    ).execute()
                    if "attachmentDataRef" in upload_result:
                        appended_attachments.append({"attachmentDataRef": upload_result["attachmentDataRef"]})

            if appended_attachments:
                body["attachment"] = appended_attachments

            response = service.spaces().messages().create(
                parent=parent,
                body=body
            ).execute()
            print(f"Successfully sent message to {parent}. Message name: {response.get('name')}")
        except Exception as e:
            print(f"Error sending message to {parent}: {e}")
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


def main():
    """Main function to run the Google Chat writer."""
    dotenv.load_dotenv()  # Load environment variables here

    parser = argparse.ArgumentParser(description="Google Chat Writer")
    parser.add_argument(
        "--config", required=True, help="Path to YAML config file"
    )
    parser.add_argument(
        "--run-dir", default=".", help="Directory to save output"
    )
    args = parser.parse_args()

    try:
        with open(args.config, "r") as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load config: {e}")
        return

    writer_config = cfg.get("google_chat_writer", {})

    writer = GoogleChatWriter(
        config_dir=os.path.dirname(args.config),
        run_dir=args.run_dir,
        **writer_config
    )

    writer()


if __name__ == "__main__":
    main()
