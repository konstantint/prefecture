import os
from pathlib import Path
from datetime import datetime
from prefect import task
from prefect.cache_policies import NO_CACHE
from ai_digest.templating import render_template

class ContextLoader:
    def load(self) -> dict:
        raise NotImplementedError

class LastWeeksDigestLoader(ContextLoader):
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        
    def load(self) -> dict:
        if not self.data_dir.exists():
            return {"last_weeks_digest": ""}
            
        dates = []
        for d in self.data_dir.iterdir():
            if d.is_dir():
                try:
                    datetime.strptime(d.name, "%Y-%m-%d")
                    dates.append(d.name)
                except ValueError:
                    continue
                    
        dates.sort(reverse=True)
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        for d_str in dates:
            if d_str == today_str:
                continue
            path = self.data_dir / d_str / "digest.md"
            if path.exists():
                with open(path, "r") as f:
                    return {"last_weeks_digest": f.read()}
                    
        return {"last_weeks_digest": ""}

_registry = {}

def register_loader(name: str, loader: ContextLoader):
    _registry[name] = loader

class PromptGenerator:
    def __init__(self, *, config_dir: Path, template_file: str, output_file_name: str = None, context_loaders: list = None, params: dict = None):
        self.config_dir = config_dir
        self.template_file = template_file
        self.output_file_name = output_file_name
        self.context_loaders = context_loaders or []
        self.params = params or {}
        
    @task(name="PromptGenerator")
    def __call__(self, run_dir: Path) -> str:
        context = {}
        
        for loader_cfg in self.context_loaders:
            loader_type = loader_cfg["type"]
            assign_to = loader_cfg.get("assign_to", loader_type)
            
            if loader_type in _registry:
                loader = _registry[loader_type]
                data = loader.load()
                
                if "last_weeks_digest" in data and assign_to != "last_weeks_digest":
                    data[assign_to] = data.pop("last_weeks_digest")
                    
                context.update(data)
            else:
                print(f"Warning: Unknown context loader type: {loader_type}")
                
        context.update(self.params)
        
        template_path = Path(self.template_file)
        if not template_path.is_absolute():
            template_path = self.config_dir / template_path
            
        content = render_template(template_path, context)
        
        if self.output_file_name:
            out_path = run_dir / self.output_file_name
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                f.write(content)
                
        from prefect.artifacts import create_markdown_artifact
        create_markdown_artifact(
            key="prompt",
            markdown=content,
            description="Generated Prompt"
        )
                
        return content
