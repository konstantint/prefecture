"""Ntfy notification tasks for Prefecture."""

import os
import pathlib
import sys

import dotenv
import prefect
from prefecture.core.caching import operator_cache_key
from prefect import cache_policies
import requests
from requests import auth


class NtfySender:
    """Sends notifications using ntfy."""

    def __init__(
        self,
        *,
        config_dir: pathlib.Path,
        run_dir: pathlib.Path,
        host: str = "https://ntfy.sh",
        user: str | None = None,
        password: str | None = None,
        topic: str,
        content_file_name: str | None = None,
        content: str | None = None,
        title: str = "Notification",
        tags: str = "robot,page_facing_up",
    ):
        """Initializes the NtfySender."""
        if (content_file_name is not None) and (content is not None):
            raise ValueError(
                "Specify either content_file_name or content, not both"
            )
        if (content_file_name is None) and (content is None):
            raise ValueError(
                "Must specify either content_file_name or content"
            )

        self.host = host
        self.user = user
        self.password = password
        self.topic = topic
        self.content_file_name = content_file_name
        self.content = content
        self.title = title
        self.tags = tags
        self.config_dir = config_dir
        self.run_dir = run_dir

        # Ensure scheme is present
        if not self.host.startswith("http://") and not self.host.startswith(
            "https://"
        ):
            self.host = "https://" + self.host

        # Ensure host doesn't end with slash
        if self.host.endswith("/"):
            self.host = self.host[:-1]

    def __repr__(self) -> str:
        return f"NtfySender(host={repr(self.host)}, topic={repr(self.topic)}, title={repr(self.title)}, tags={repr(self.tags)}, content_file_name={repr(self.content_file_name)}, content={repr(self.content)})"

    @prefect.task(name="NtfySender")
    def __call__(self) -> None:
        """Sends notification."""
        if self.content is not None:
            markdown_content = self.content
        else:
            content_path = self.run_dir / self.content_file_name
            with open(content_path, "r") as f:
                markdown_content = f.read()
        url = f"{self.host}/{self.topic}"

        headers = {"Title": self.title, "Tags": self.tags}

        http_auth = None
        if self.user and self.password:
            http_auth = auth.HTTPBasicAuth(self.user, self.password)

        try:
            response = requests.post(
                url,
                data=markdown_content.encode("utf-8"),
                headers=headers,
                auth=http_auth,
            )
            response.raise_for_status()
            print(f"Successfully sent notification to {url}")
        except Exception as e:
            print(f"Error sending notification: {e}")

    # We don't define any dependencies.
    # This means the step will always wait for all preceding steps to complete.
    # @property
    # def dependencies(self) -> set[str]:
    #     if getattr(self, "content_file_name", None):
    #         path = pathlib.Path(self.content_file_name)
    #         if not path.is_absolute():
    #             path = self.run_dir / path
    #         return {str(path.resolve())}
    #     return set()

    @property
    def outputs(self) -> set[str]:
        return set()



