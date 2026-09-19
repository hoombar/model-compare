"""Prompt file loading: markdown body + YAML frontmatter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import frontmatter


@dataclass
class PromptSpec:
    title: str
    system_prompt: str
    body: str
    source_path: Path | None


def load_prompt(path: Path, default_system_prompt: str) -> PromptSpec:
    post = frontmatter.load(str(path))
    meta = post.metadata
    body = (post.content or "").strip()
    if not body:
        raise ValueError(f"prompt file has no body text: {path}")
    title = str(meta.get("title") or path.stem.replace("-", " ").replace("_", " ").title())
    system_prompt = str(meta.get("system_prompt") or default_system_prompt).strip()
    return PromptSpec(
        title=title,
        system_prompt=system_prompt,
        body=body,
        source_path=path,
    )


def discover_prompts(directory: Path, default_system_prompt: str) -> list[PromptSpec]:
    """Load available Markdown prompts in filename order."""
    if not directory.is_dir():
        return []
    return [load_prompt(path, default_system_prompt) for path in sorted(directory.glob("*.md"))]


def custom_prompt(title: str, body: str, default_system_prompt: str) -> PromptSpec:
    """Build a one-off prompt that is not backed by a file."""
    title = title.strip()
    body = body.strip()
    if not title:
        raise ValueError("custom prompt needs a title")
    if not body:
        raise ValueError("custom prompt has no body text")
    return PromptSpec(
        title=title,
        system_prompt=default_system_prompt,
        body=body,
        source_path=None,
    )
