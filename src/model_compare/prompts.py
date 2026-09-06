"""Prompt file loading: markdown body + YAML frontmatter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import frontmatter


@dataclass
class PromptSpec:
    title: str
    system_prompt: str
    models: list[str]
    body: str
    source_path: Path


def load_prompt(path: Path, default_system_prompt: str) -> PromptSpec:
    post = frontmatter.load(str(path))
    meta = post.metadata
    body = (post.content or "").strip()
    if not body:
        raise ValueError(f"prompt file has no body text: {path}")
    title = str(meta.get("title") or path.stem.replace("-", " ").replace("_", " ").title())
    system_prompt = str(meta.get("system_prompt") or default_system_prompt).strip()
    models = [str(m) for m in (meta.get("models") or [])]
    return PromptSpec(
        title=title,
        system_prompt=system_prompt,
        models=models,
        body=body,
        source_path=path,
    )
