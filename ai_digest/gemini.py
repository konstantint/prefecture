import os
from pathlib import Path
from google import genai
from google.genai import types
from prefect import task
from prefect.cache_policies import NO_CACHE
from prefect.artifacts import create_markdown_artifact

class GeminiGenerator:
    def __init__(self, *, config_dir: Path, api_key: str, model: str = "gemini-3.1-flash-lite", prompt_file_name: str, output_file_name: str, use_google_search: bool = False):
        if not api_key:
            raise ValueError("api_key is required")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.prompt_file_name = prompt_file_name
        self.output_file_name = output_file_name
        self.use_google_search = use_google_search
        self.config_dir = config_dir

    # cache_policy NO_CACHE because otherwise we get
    #   JSON error: Unable to serialize unknown type: <class 'ai_digest.gemini.GeminiGenerator'>
    @task(name="GeminiGenerator", cache_policy=NO_CACHE)
    def __call__(self, run_dir: Path) -> str:
        prompt_path = run_dir / self.prompt_file_name
        with open(prompt_path, "r") as f:
            prompt = f.read()
        system_instruction = """
        """
        
        tools = []
        if self.use_google_search:
            tools.append(types.Tool(googleSearch=types.GoogleSearch()))
            
        generate_content_config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=tools,
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
                
        out_path = run_dir / self.output_file_name
        with open(out_path, "w") as f:
            f.write(full_text)
            
        create_markdown_artifact(
            key="digest",
            markdown=full_text,
            description="Generated Gemini Digest"
        )
            
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
