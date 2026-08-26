"""Tests for GoogleChatReader retry logic."""

import json
import os
from unittest import mock
import pytest
from googleapiclient.errors import HttpError
from prefect.testing.utilities import prefect_test_harness
from prefecture.operations.google_chat_reader import GoogleChatReader

@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    with prefect_test_harness():
        yield


@mock.patch('prefecture.operations.google_chat_reader.discovery.build')
def test_google_chat_reader_success_no_retry(mock_build, tmp_path):
    """Test successful read without any retries."""
    mock_service = mock.Mock()
    mock_build.return_value = mock_service
    mock_messages = mock_service.spaces.return_value.messages.return_value
    mock_list = mock_messages.list

    success_response = {
        'messages': [
            {
                'text': 'Hello',
                'createTime': '2026-05-17T20:00:00Z',
                'space': {'name': 'spaces/test'},
            }
        ]
    }
    mock_execute = mock.Mock(return_value=success_response)
    mock_list.return_value.execute = mock_execute

    reader = GoogleChatReader(
        config_dir=str(tmp_path),
        run_dir=str(tmp_path),
        client_id="test_client",
        client_secret="test_secret",
        refresh_token="test_token",
        spaces=[{'id': 'test_space', 'display_name': 'Test Space'}],
    )
    reader._get_credentials = mock.Mock()

    reader()

    assert mock_execute.call_count == 1
    
    # Verify file content
    data_file = os.path.join(tmp_path, 'chat', 'data.json')
    assert os.path.exists(data_file)
    with open(data_file, 'r') as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]['text'] == 'Hello'


@mock.patch('prefecture.operations.google_chat_reader.discovery.build')
def test_google_chat_reader_retry_and_success(mock_build, tmp_path):
    """Test retrying on transient errors and eventually succeeding."""
    mock_service = mock.Mock()
    mock_build.return_value = mock_service
    mock_messages = mock_service.spaces.return_value.messages.return_value
    mock_list = mock_messages.list

    # Mock responses for HttpError
    mock_resp_429 = mock.Mock()
    mock_resp_429.status = 429
    mock_resp_429.reason = "Too Many Requests"
    error_429 = HttpError(mock_resp_429, b'Rate limit exceeded')

    mock_resp_503 = mock.Mock()
    mock_resp_503.status = 503
    mock_resp_503.reason = "Service Unavailable"
    error_503 = HttpError(mock_resp_503, b'THROTTLED_TASK_LIMIT')

    success_response = {
        'messages': [
            {
                'text': 'Hello after retry',
                'createTime': '2026-05-17T20:00:00Z',
                'space': {'name': 'spaces/test'},
            }
        ]
    }

    mock_execute = mock.Mock()
    mock_execute.side_effect = [error_429, error_503, success_response]
    mock_list.return_value.execute = mock_execute

    reader = GoogleChatReader(
        config_dir=str(tmp_path),
        run_dir=str(tmp_path),
        client_id="test_client",
        client_secret="test_secret",
        refresh_token="test_token",
        spaces=[{'id': 'test_space', 'display_name': 'Test Space'}],
        num_retries=3,
        initial_backoff=0.001,  # very small for fast tests
    )
    reader._get_credentials = mock.Mock()

    reader()

    assert mock_execute.call_count == 3
    
    data_file = os.path.join(tmp_path, 'chat', 'data.json')
    with open(data_file, 'r') as f:
        data = json.load(f)
        assert data[0]['text'] == 'Hello after retry'


@mock.patch('prefecture.operations.google_chat_reader.discovery.build')
def test_google_chat_reader_max_retries_exceeded(mock_build, tmp_path):
    """Test that it eventually raises error if retries are exhausted."""
    mock_service = mock.Mock()
    mock_build.return_value = mock_service
    mock_messages = mock_service.spaces.return_value.messages.return_value
    mock_list = mock_messages.list

    mock_resp_503 = mock.Mock()
    mock_resp_503.status = 503
    mock_resp_503.reason = "Service Unavailable"
    error_503 = HttpError(mock_resp_503, b'THROTTLED_TASK_LIMIT')

    # Always fail
    mock_execute = mock.Mock(side_effect=error_503)
    mock_list.return_value.execute = mock_execute

    reader = GoogleChatReader(
        config_dir=str(tmp_path),
        run_dir=str(tmp_path),
        client_id="test_client",
        client_secret="test_secret",
        refresh_token="test_token",
        spaces=[{'id': 'test_space', 'display_name': 'Test Space'}],
        num_retries=2,
        initial_backoff=0.001,
    )
    reader._get_credentials = mock.Mock()

    # Should raise HttpError after 1 initial + 2 retries = 3 attempts
    with pytest.raises(HttpError):
        reader()

    assert mock_execute.call_count == 3


@mock.patch('prefecture.operations.google_chat_reader.discovery.build')
def test_google_chat_reader_non_retryable_error(mock_build, tmp_path):
    """Test that non-retryable errors (e.g. 400) fail immediately."""
    mock_service = mock.Mock()
    mock_build.return_value = mock_service
    mock_messages = mock_service.spaces.return_value.messages.return_value
    mock_list = mock_messages.list

    mock_resp_400 = mock.Mock()
    mock_resp_400.status = 400
    mock_resp_400.reason = "Bad Request"
    error_400 = HttpError(mock_resp_400, b'Invalid argument')

    mock_execute = mock.Mock(side_effect=error_400)
    mock_list.return_value.execute = mock_execute

    reader = GoogleChatReader(
        config_dir=str(tmp_path),
        run_dir=str(tmp_path),
        client_id="test_client",
        client_secret="test_secret",
        refresh_token="test_token",
        spaces=[{'id': 'test_space', 'display_name': 'Test Space'}],
        num_retries=3,
        initial_backoff=0.001,
    )
    reader._get_credentials = mock.Mock()

    # Should raise HttpError immediately on first attempt
    with pytest.raises(HttpError):
        reader()

    assert mock_execute.call_count == 1
