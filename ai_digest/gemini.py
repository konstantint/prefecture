import os
from google import genai
from google.genai import types

class GeminiGenerator:
    def __init__(self, *, api_key: str, model: str = "gemini-3.1-flash-lite"):
        if not api_key:
            raise ValueError("api_key is required")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        
    def __call__(self, prompt: str) -> str:
        system_instruction = """
        """
        
        generate_content_config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[types.Tool(googleSearch=types.GoogleSearch())],
        )
        
        response_stream = self.client.models.generate_content_stream(
            model=self.model,
            contents=[prompt],
            config=generate_content_config,
        )
        
        full_text = ""
        for chunk in response_stream:
            if chunk.text:
                full_text += chunk.text
                
        return full_text

if __name__ == "__main__":
    from dotenv import load_dotenv
    from pathlib import Path
    import sys
    
    load_dotenv(override=True)
    
    print("Testing GeminiGenerator...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set in .env")
        sys.exit(1)
        
    generator = GeminiGenerator(api_key=api_key)
    prompt = "Tell me a short joke."
    try:
        result = generator(prompt)
        print(f"Result:\n{result}")
    except Exception as e:
        print(f"Error: {e}")
