import os
import requests
from prefect import task
from requests.auth import HTTPBasicAuth

class NtfySender:
    def __init__(self, *, host: str = "https://ntfy.sh", user: str = None, password: str = None, topic: str):
        self.host = host
        self.user = user
        self.password = password
        self.topic = topic
        
        # Ensure scheme is present
        if not self.host.startswith("http://") and not self.host.startswith("https://"):
            self.host = "https://" + self.host
            
        # Ensure host doesn't end with slash
        if self.host.endswith("/"):
            self.host = self.host[:-1]
            
    def __call__(self, markdown: str):
        url = f"{self.host}/{self.topic}"
        
        headers = {"Title": "AI Digest Ready", "Tags": "robot,page_facing_up"}
        
        auth = None
        if self.user and self.password:
            auth = HTTPBasicAuth(self.user, self.password)
            
        try:
            response = requests.post(
                url,
                data=markdown.encode('utf-8'),
                headers=headers,
                auth=auth
            )
            response.raise_for_status()
            print(f"Successfully sent notification to {url}")
        except Exception as e:
            print(f"Error sending notification: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    from pathlib import Path
    import sys
    
    load_dotenv(override=True)
    
    print("Testing NtfySender...")
    topic = os.environ.get("NTFY_TOPIC", "test")
    host = os.environ.get("NTFY_HOST", "https://ntfy.sh")
    user = os.environ.get("NTFY_USER")
    password = os.environ.get("NTFY_PASSWORD")
    
    sender = NtfySender(host=host, user=user, password=password, topic=topic)
    
    try:
        sender("This is a test notification from NtfySender class.")
    except Exception as e:
        print(f"Error in ntfy test: {e}")
