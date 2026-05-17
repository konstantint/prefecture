"""Tests for GmailMailer in Prefecture."""

import base64
from email import message_from_bytes
import pathlib
from unittest import mock

from prefecture.mailer import GmailMailer
import pytest


def test_gmail_mailer_markdown_rendering(tmp_path):
    """Test that GmailMailer renders markdown to HTML correctly, especially lists."""
    # Create a dummy content file
    content_file = tmp_path / "digest.md"
    content_file.write_text("""---
subject: Test Markdown Subject
---
This is a paragraph
* List item 1
* List item 2
""")

    mailer = GmailMailer(
        config_dir=tmp_path,
        gmail_client_id="mock_id",
        gmail_client_secret="mock_secret",
        gmail_refresh_token="mock_token",
        recipients=["test@example.com"],
        content_file_name="digest.md",
    )

    # Mock requests.post
    with mock.patch("requests.post") as mock_post:
        # Mock token response
        mock_token_resp = mock.Mock()
        mock_token_resp.json.return_value = {"access_token": "mock_access_token"}
        mock_token_resp.raise_for_status.return_value = None

        # Mock send response
        mock_send_resp = mock.Mock()
        mock_send_resp.raise_for_status.return_value = None

        mock_post.side_effect = [mock_token_resp, mock_send_resp]

        # Call the mailer task
        mailer(run_dir=tmp_path)

        # Verify requests were made
        assert mock_post.call_count == 2

        # Find the send call
        send_call = None
        for call in mock_post.call_args_list:
            if "gmail.googleapis.com" in call[0][0]:
                send_call = call
                break

        assert send_call is not None
        raw_message_b64 = send_call[1]["json"]["raw"]

        decoded_bytes = base64.urlsafe_b64decode(raw_message_b64)
        msg = message_from_bytes(decoded_bytes)

        # Get HTML payload
        html_payload = None
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html_payload = part.get_payload(decode=True).decode("utf-8")
                break

        assert html_payload is not None

        # Print HTML for debugging if test fails
        print(f"Rendered HTML:\n{html_payload}")

        # We expect GFM-like rendering where lists don't need preceding blank line.
        # In python-markdown, this would NOT render as <li> because it lacks blank line before '*'.
        # In markdown-it-py, it SHOULD render as <li>.
        assert "<li>List item 1</li>" in html_payload
        assert "<li>List item 2</li>" in html_payload
