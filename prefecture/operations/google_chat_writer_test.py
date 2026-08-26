"""Tests for GoogleChatWriter logic."""

import os
from unittest import mock
import pytest
from googleapiclient.errors import HttpError
from prefect.testing.utilities import prefect_test_harness
from prefecture.operations.google_chat_writer import GoogleChatWriter

@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    with prefect_test_harness():
        yield


@mock.patch('prefecture.operations.google_chat_writer.GoogleChatWriter._get_credentials')
@mock.patch('prefecture.operations.google_chat_writer.discovery.build')
def test_google_chat_writer_inline_content(mock_build, mock_get_credentials, tmp_path):
    """Test successful write with inline content string."""
    mock_service = mock.Mock()
    mock_build.return_value = mock_service
    mock_messages = mock_service.spaces.return_value.messages.return_value
    mock_create = mock_messages.create
    mock_execute = mock.Mock(return_value={"name": "spaces/test_space/messages/123"})
    mock_create.return_value.execute = mock_execute

    writer = GoogleChatWriter(
        config_dir=str(tmp_path),
        run_dir=str(tmp_path),
        client_id="test_client",
        client_secret="test_secret",
        refresh_token="test_token",
        space_id="test_space",
        content="Hello, test!",
    )

    writer()

    mock_create.assert_called_once_with(
        parent="spaces/test_space",
        body={"text": "Hello, test!", "markupSyntax": "MARKUP_SYNTAX_MARKDOWN"}
    )
    mock_execute.assert_called_once()


@mock.patch('prefecture.operations.google_chat_writer.GoogleChatWriter._get_credentials')
@mock.patch('prefecture.operations.google_chat_writer.discovery.build')
def test_google_chat_writer_file_content(mock_build, mock_get_credentials, tmp_path):
    """Test successful write reading from content file."""
    mock_service = mock.Mock()
    mock_build.return_value = mock_service
    mock_messages = mock_service.spaces.return_value.messages.return_value
    mock_create = mock_messages.create
    mock_execute = mock.Mock(return_value={"name": "spaces/test_space/messages/123"})
    mock_create.return_value.execute = mock_execute

    # Create dummy content file
    content_file = os.path.join(tmp_path, "message.md")
    with open(content_file, "w") as f:
        f.write("Hello from file!")

    writer = GoogleChatWriter(
        config_dir=str(tmp_path),
        run_dir=str(tmp_path),
        client_id="test_client",
        client_secret="test_secret",
        refresh_token="test_token",
        space_id="test_space",
        content_file_name="message.md",
    )

    writer()

    mock_create.assert_called_once_with(
        parent="spaces/test_space",
        body={"text": "Hello from file!", "markupSyntax": "MARKUP_SYNTAX_MARKDOWN"}
    )
    mock_execute.assert_called_once()
    
def test_google_chat_writer_validation_error(tmp_path):
    """Test validations for config parameters."""
    with pytest.raises(ValueError, match="Specify either content_file_name or content, not both"):
        GoogleChatWriter(
            config_dir=str(tmp_path),
            run_dir=str(tmp_path),
            client_id="test_client",
            client_secret="test_secret",
            refresh_token="test_token",
            space_id="test_space",
            content_file_name="message.md",
            content="Hello",
        )

    with pytest.raises(ValueError, match="Must specify either content_file_name or content"):
        GoogleChatWriter(
            config_dir=str(tmp_path),
            run_dir=str(tmp_path),
            client_id="test_client",
            client_secret="test_secret",
            refresh_token="test_token",
            space_id="test_space",
        )

@mock.patch('prefecture.operations.google_chat_writer.GoogleChatWriter._get_credentials')
@mock.patch('prefecture.operations.google_chat_writer.discovery.build')
def test_google_chat_writer_api_error(mock_build, mock_get_credentials, tmp_path):
    """Test that API errors are propagated out."""
    mock_service = mock.Mock()
    mock_build.return_value = mock_service
    mock_messages = mock_service.spaces.return_value.messages.return_value
    mock_create = mock_messages.create
    
    mock_resp_500 = mock.Mock()
    mock_resp_500.status = 500
    mock_resp_500.reason = "Internal Server Error"
    error_500 = HttpError(mock_resp_500, b'Server failed')
    
    mock_execute = mock.Mock(side_effect=error_500)
    mock_create.return_value.execute = mock_execute

    writer = GoogleChatWriter(
        config_dir=str(tmp_path),
        run_dir=str(tmp_path),
        client_id="test_client",
        client_secret="test_secret",
        refresh_token="test_token",
        space_id="test_space",
        content="Fail, test!",
    )

    with pytest.raises(HttpError):
        writer()

    mock_create.assert_called_once_with(
        parent="spaces/test_space",
        body={"text": "Fail, test!", "markupSyntax": "MARKUP_SYNTAX_MARKDOWN"}
    )
    mock_execute.assert_called_once()
