"""Loading of models.toml (aliases + presets) and model resolution."""

from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomlkit

DEFAULT_SYSTEM_PROMPT = (
    "You are a thoughtful, knowledgeable assistant. "
    "Answer directly and clearly, and follow any format requirements given."
)
MODEL_ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


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


def validate_model(alias: str, slug: str) -> tuple[str, str]:
    """Validate and normalize a model alias and OpenRouter slug."""
    alias = alias.strip()
    slug = slug.strip()
    if not MODEL_ALIAS_PATTERN.fullmatch(alias) or alias == "default_system_prompt":
        raise ValueError("alias must use letters, numbers, dots, dashes, or underscores")
    if slug.count("/") != 1 or any(character.isspace() for character in slug):
        raise ValueError("model slug must look like provider/model")
    provider, model = slug.split("/", 1)
    if not provider or not model:
        raise ValueError("model slug must look like provider/model")
    return alias, slug


def add_model(path: Path, alias: str, slug: str) -> None:
    """Add a model while preserving the existing TOML formatting and comments."""
    alias, slug = validate_model(alias, slug)
    document = tomlkit.parse(path.read_text()) if path.exists() else tomlkit.document()
    if alias in document:
        raise ValueError(f"model alias already exists: {alias}")
    document[alias] = slug
    _write_toml(path, tomlkit.dumps(document))


def delete_model(path: Path, alias: str) -> None:
    """Delete one model alias while preserving the rest of the TOML document."""
    document = tomlkit.parse(path.read_text()) if path.exists() else tomlkit.document()
    if alias not in document or alias == "default_system_prompt":
        raise ValueError(f"model alias not found: {alias}")
    del document[alias]
    _write_toml(path, tomlkit.dumps(document))


def _write_toml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content)
    temporary.replace(path)


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
