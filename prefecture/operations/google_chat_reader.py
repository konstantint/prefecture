"""Google Chat reader tasks for Prefecture."""

import argparse
import datetime
import json
import os
import typing

import dotenv
from google.auth.transport import requests
from google.oauth2 import credentials
from google_auth_oauthlib import flow
from googleapiclient import discovery
import prefect
import slugify

SCOPES = ['https://www.googleapis.com/auth/chat.messages.readonly']

class GoogleChatReader:
    """Reads messages from Google Chat."""

    def __init__(
        self,
        config_dir: str,
        run_dir: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        spaces: list[dict[str, typing.Any]],
        max_messages: int | None = None,
        max_hours_ago: int | None = None,
        num_retries: int = 5,
        initial_backoff: float = 1.0,
    ):
        """Initializes the GoogleChatReader."""
        self.config_dir = config_dir
        self.run_dir = run_dir
        self.client_id = os.path.expandvars(client_id)
        self.client_secret = os.path.expandvars(client_secret)
        self.refresh_token = os.path.expandvars(refresh_token)
        self.spaces = spaces
        self.max_messages = max_messages
        self.max_hours_ago = max_hours_ago
        self.num_retries = num_retries
        self.initial_backoff = initial_backoff

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

    def _execute_request_with_retry(self, request: typing.Any) -> typing.Any:
        """Executes a Google API request with retry logic."""
        import time
        import random
        from googleapiclient.errors import HttpError

        max_attempts = self.num_retries + 1
        for attempt in range(1, max_attempts + 1):
            try:
                return request.execute()
            except HttpError as e:
                if attempt == max_attempts:
                    print(f"Failed to execute request after {max_attempts} attempts.")
                    raise

                status = e.resp.status
                content_str = e.content.decode('utf-8') if isinstance(e.content, bytes) else str(e.content)

                is_retryable = (
                    status in [429, 503] or
                    "THROTTLED_TASK_LIMIT" in content_str
                )

                if is_retryable:
                    # Exponential backoff with jitter
                    sleep_time = (self.initial_backoff * (2 ** (attempt - 1))) + random.random()
                    print(
                        f"Attempt {attempt} failed with status {status} (retryable). "
                        f"Retrying in {sleep_time:.2f} seconds... Error: {content_str.strip()}"
                    )
                    time.sleep(sleep_time)
                else:
                    raise

    @prefect.task(name="GoogleChatReader")
    def __call__(self) -> None:
        """Reads messages from Google Chat and saves them."""
        print(f"Starting Google Chat reader in {self.run_dir}")

        if (
            not self.client_id
            or not self.client_secret
            or not self.refresh_token
        ):
            raise ValueError(
                "client_id, client_secret, and refresh_token must be specified"
            )

        print(f"Debug: client_id starts with: {self.client_id[:10]}")
        creds = self._get_credentials()
        service = discovery.build("chat", "v1", credentials=creds)

        raw_dir = os.path.join(self.run_dir, "chat", "raw")
        os.makedirs(raw_dir, exist_ok=True)

        all_messages = []

        cutoff_time = None
        if self.max_hours_ago:
            cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(
                hours=self.max_hours_ago
            )

        for space in self.spaces:
            space_id = space['id']
            display_name = space['display_name']
            slug = slugify.slugify(display_name)
            
            print(f"Reading space: {display_name} ({space_id})")
            
            messages = []
            page_token = None
            
            while True:
                parent = f"spaces/{space_id}"
                request = service.spaces().messages().list(
                    parent=parent,
                    pageSize=1000,
                    pageToken=page_token
                )
                response = self._execute_request_with_retry(request)
                
                batch = response.get('messages', [])
                if not batch:
                    break
                    
                for msg in batch:
                    if cutoff_time:
                        create_time_str = msg.get('createTime')
                        if create_time_str:
                            if create_time_str.endswith('Z'):
                                create_time_str = create_time_str[:-1]
                            create_time = datetime.datetime.fromisoformat(create_time_str)
                            if create_time < cutoff_time:
                                continue
                    
                    messages.append(msg)
                    
                    if self.max_messages and len(messages) >= self.max_messages:
                        break
                        
                if self.max_messages and len(messages) >= self.max_messages:
                    break
                    
                page_token = response.get('nextPageToken')
                if not page_token:
                    break

            # Save raw data
            raw_file = os.path.join(raw_dir, f"{slug}.json")
            with open(raw_file, 'w') as f:
                json.dump(messages, f, indent=2)
            print(f"Saved {len(messages)} raw messages to {raw_file}")

            # Process for union
            for msg in messages:
                msg['space']['displayName'] = display_name
                all_messages.append(msg)

        # Save union data
        data_file = os.path.join(self.run_dir, 'chat', 'data.json')
        with open(data_file, 'w') as f:
            json.dump(all_messages, f, indent=2)
        print(f"Saved {len(all_messages)} simplified messages to {data_file}")

def main():
    """Main function to run the Google Chat reader."""
    dotenv.load_dotenv()  # Load environment variables here

    parser = argparse.ArgumentParser(description="Google Chat Reader")
    parser.add_argument(
        "--config", required=True, help="Path to YAML config file"
    )
    parser.add_argument(
        "--run-dir", default=".", help="Directory to save output"
    )
    args = parser.parse_args()

    try:
        import yaml

        with open(args.config, "r") as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load config: {e}")
        return

    reader_config = cfg.get("google_chat_reader", {})

    reader = GoogleChatReader(
        config_dir=os.path.dirname(args.config),
        run_dir=args.run_dir,
        **reader_config
    )

    reader()

if __name__ == "__main__":
    main()
