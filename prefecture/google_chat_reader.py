import argparse
import datetime
import json
import os
from typing import Any, Dict, List, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from prefect import task
from slugify import slugify
import dotenv

dotenv.load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/chat.messages.readonly']

class GoogleChatReader:
    def __init__(
        self, 
        config_dir: str, 
        client_id: str, 
        client_secret: str, 
        refresh_token: str, 
        spaces: List[Dict[str, Any]], 
        max_messages: Optional[int] = None, 
        max_hours_ago: Optional[int] = None
    ):
        self.config_dir = config_dir
        self.client_id = os.path.expandvars(client_id)
        self.client_secret = os.path.expandvars(client_secret)
        self.refresh_token = os.path.expandvars(refresh_token)
        self.spaces = spaces
        self.max_messages = max_messages
        self.max_hours_ago = max_hours_ago

    def _get_credentials(self) -> Credentials:
        creds = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=SCOPES
        )
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f"Failed to refresh token: {e}")
            raise
        return creds

    @task(name="GoogleChatReader")
    def __call__(self, run_dir: str) -> None:
        print(f"Starting Google Chat reader in {run_dir}")
        
        if not self.client_id or not self.client_secret or not self.refresh_token:
            raise ValueError("client_id, client_secret, and refresh_token must be specified")

        print(f"Debug: client_id starts with: {self.client_id[:10]}")
        creds = self._get_credentials()
        service = build('chat', 'v1', credentials=creds)

        raw_dir = os.path.join(run_dir, 'chat', 'raw')
        os.makedirs(raw_dir, exist_ok=True)

        all_messages = []

        cutoff_time = None
        if self.max_hours_ago:
            cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(hours=self.max_hours_ago)

        for space in self.spaces:
            space_id = space['id']
            display_name = space['display_name']
            slug = slugify(display_name)
            
            print(f"Reading space: {display_name} ({space_id})")
            
            messages = []
            page_token = None
            
            while True:
                try:
                    parent = f"spaces/{space_id}"
                    request = service.spaces().messages().list(
                        parent=parent,
                        pageSize=100,
                        pageToken=page_token
                    )
                    response = request.execute()
                    
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
                        
                except Exception as e:
                    print(f"Error fetching messages for {display_name}: {e}")
                    break

            # Save raw data
            raw_file = os.path.join(raw_dir, f"{slug}.json")
            with open(raw_file, 'w') as f:
                json.dump(messages, f, indent=2)
            print(f"Saved {len(messages)} raw messages to {raw_file}")

            # Process for union
            for msg in messages:
                if msg.get('sender', {}).get('type') == 'BOT':
                    continue
                    
                text = msg.get('text', '')
                
                # Construct link
                chat_link = ''
                if 'name' in msg:
                    parts = msg['name'].split('/')
                    if len(parts) >= 4:
                        s_id = parts[1]
                        m_id = parts[3].split('.')[0]
                        chat_link = f"https://chat.google.com/room/{s_id}/{m_id}"
                        
                all_messages.append({
                    'space': display_name,
                    'text': text,
                    'link': chat_link
                })

        # Save union data
        data_file = os.path.join(run_dir, 'chat', 'data.json')
        with open(data_file, 'w') as f:
            json.dump(all_messages, f, indent=2)
        print(f"Saved {len(all_messages)} simplified messages to {data_file}")

def main():
    parser = argparse.ArgumentParser(description="Google Chat Reader")
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    parser.add_argument("--run-dir", default=".", help="Directory to save output")
    args = parser.parse_args()

    try:
        import yaml
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load config: {e}")
        return

    reader_config = config.get('google_chat_reader', {})
    
    reader = GoogleChatReader(
        config_dir=os.path.dirname(args.config),
        **reader_config
    )
    
    reader(run_dir=args.run_dir)

if __name__ == "__main__":
    main()
