from pathlib import Path

import pytest

from model_compare.config import add_model, delete_model, load_config, validate_model


def test_add_model_preserves_comments_and_settings(tmp_path: Path) -> None:
    path = tmp_path / "models.toml"
    path.write_text(
        '# Keep this comment\nold = "vendor/old" # Inline comment\n\n'
        'default_system_prompt = "Be concise."\n'
    )

    add_model(path, "new-model", "vendor/new-model")

    content = path.read_text()
    assert "# Keep this comment" in content
    assert '# Inline comment' in content
    assert 'default_system_prompt = "Be concise."' in content
    assert load_config(path).aliases == {
        "old": "vendor/old",
        "new-model": "vendor/new-model",
    }


def test_delete_model_preserves_other_content(tmp_path: Path) -> None:
    path = tmp_path / "models.toml"
    path.write_text(
        '# Keep this comment\nold = "vendor/old"\nkeep = "vendor/keep"\n'
        'default_system_prompt = "Be concise."\n'
    )

    delete_model(path, "old")

    content = path.read_text()
    assert "# Keep this comment" in content
    assert "old =" not in content
    assert load_config(path).aliases == {"keep": "vendor/keep"}
    assert load_config(path).default_system_prompt == "Be concise."


def test_add_model_rejects_an_existing_alias(tmp_path: Path) -> None:
    path = tmp_path / "models.toml"
    path.write_text('existing = "vendor/model"\n')

    with pytest.raises(ValueError, match="already exists"):
        add_model(path, "existing", "vendor/other")


@pytest.mark.parametrize(
    ("alias", "slug"),
    [
        ("has spaces", "vendor/model"),
        ("default_system_prompt", "vendor/model"),
        ("valid", "missing-provider"),
        ("valid", "too/many/slashes"),
    ],
)
def test_validate_model_rejects_invalid_values(alias: str, slug: str) -> None:
    with pytest.raises(ValueError):
        validate_model(alias, slug)
