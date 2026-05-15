import os
from pathlib import Path
from datetime import datetime
from prefect import task
from prefect.cache_policies import NO_CACHE
from ai_digest.templating import render_template

class ContextLoader:
    def __call__(self, run_dir: Path) -> str:
        raise NotImplementedError

_registry = {}

def register_loader(name: str, loader_cls: type):
    _registry[name] = loader_cls

class RunDirFileLoader(ContextLoader):
    """Loads the contents of a file in the run_dir (or a run_dir of one of the previous days)."""
    def __init__(self, file_name: str, days_ago: int = 0, fail_on_error: bool = False):
        self.file_name = file_name
        self.days_ago = days_ago
        self.fail_on_error = fail_on_error
        
    def __call__(self, run_dir: Path) -> str:
        from datetime import datetime, timedelta
        
        if self.days_ago == 0:
            target_path = run_dir / self.file_name
        else:
            try:
                current_date = datetime.strptime(run_dir.name, "%Y-%m-%d")
                prev_date = current_date - timedelta(days=self.days_ago)
                prev_date_str = prev_date.strftime("%Y-%m-%d")
                target_path = run_dir.parent / prev_date_str / self.file_name
            except ValueError:
                if self.fail_on_error:
                    raise ValueError(f"Could not parse date from run_dir name: {run_dir.name}")
                return None
                
        try:
            with open(target_path, "r") as f:
                return f.read()
        except Exception as e:
             if self.fail_on_error:
                raise ValueError(f"could not load {target_path}: {e}")
             return None

register_loader("run_dir_file", RunDirFileLoader)

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
                loader_cls = _registry[loader_type]
                loader_params = loader_cfg.get("params", {})
                loader_instance = loader_cls(**loader_params)
                data = loader_instance(run_dir)
                context.update({assign_to: data})
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
