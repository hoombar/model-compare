from pathlib import Path

import pytest

from model_compare.prompts import custom_prompt, discover_prompts


def test_discover_prompts_loads_markdown_in_filename_order(tmp_path: Path) -> None:
    (tmp_path / "z-last.md").write_text("---\ntitle: Last\n---\nLast body\n")
    (tmp_path / "a-first.md").write_text("First body\n")
    (tmp_path / "ignored.txt").write_text("Not a prompt\n")

    prompts = discover_prompts(tmp_path, "Default system")

    assert [prompt.title for prompt in prompts] == ["A First", "Last"]
    assert [prompt.body for prompt in prompts] == ["First body", "Last body"]
    assert all(prompt.system_prompt == "Default system" for prompt in prompts)


def test_discover_prompts_returns_empty_for_missing_directory(tmp_path: Path) -> None:
    assert discover_prompts(tmp_path / "missing", "Default system") == []


def test_custom_prompt_is_trimmed_and_has_no_source_file() -> None:
    prompt = custom_prompt("  My question  ", "  What is true?  ", "Default system")

    assert prompt.title == "My question"
    assert prompt.body == "What is true?"
    assert prompt.system_prompt == "Default system"
    assert prompt.source_path is None


@pytest.mark.parametrize(
    ("title", "body", "message"),
    [("", "Body", "needs a title"), ("Title", "  ", "no body text")],
)
def test_custom_prompt_rejects_missing_fields(title: str, body: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        custom_prompt(title, body, "Default system")
