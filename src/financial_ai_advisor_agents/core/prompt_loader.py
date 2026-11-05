from pathlib import Path


class PromptLoader:
    def __init__(self, root: Path):
        self.root = root

    def load(self, relative_path: str) -> str:
        path = (self.root / relative_path).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("Prompt path escapes the prompt directory")
        return path.read_text(encoding="utf-8")
