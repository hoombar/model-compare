"""Loading of models.toml (aliases + presets) and model resolution."""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SYSTEM_PROMPT = (
    "You are a thoughtful, knowledgeable assistant. "
    "Answer directly and clearly, and follow any format requirements given."
)


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without replacing environment variables."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


@dataclass
class Config:
    aliases: dict[str, str] = field(default_factory=dict)
    default_system_prompt: str = DEFAULT_SYSTEM_PROMPT


def load_config(path: Path | None = None) -> Config:
    """Load models.toml. Missing file yields an empty config (slugs still work)."""
    candidate = path if path is not None else Path("models.toml")
    config = Config()
    if not candidate.exists():
        return config
    with candidate.open("rb") as f:
        data = tomllib.load(f)
    default_system_prompt = data.pop("default_system_prompt", None)
    config.aliases = {str(k): str(v) for k, v in data.items()}
    if default_system_prompt:
        config.default_system_prompt = str(default_system_prompt)
    return config


def resolve_models(raw: list[str], config: Config) -> list[tuple[str, str]]:
    """Resolve (alias, slug) pairs from aliases or full OpenRouter slugs."""
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw:
        entry = entry.strip()
        if not entry:
            continue
        if entry in config.aliases:
            pair = (entry, config.aliases[entry])
        elif "/" in entry:
            pair = (entry, entry)
        else:
            print(
                f"warning: '{entry}' is not an alias in models.toml and not an "
                "OpenRouter slug; skipping",
                file=sys.stderr,
            )
            continue
        if pair not in seen:
            seen.add(pair)
            pairs.append(pair)
    return pairs
