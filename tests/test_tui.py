from pathlib import Path

import pytest
from textual.widgets import Input, SelectionList, Static, TextArea

from model_compare import tui
from model_compare.runner import ModelResult
from model_compare.tui import ModelCompareApp, find_project_dir


def make_project(path: Path) -> None:
    (path / "models.toml").write_text(
        'first = "vendor/first"\nsecond = "vendor/second"\n'
    )
    prompts = path / "prompts"
    prompts.mkdir()
    (prompts / "question.md").write_text("---\ntitle: Existing question\n---\nWhy?\n")


def test_project_dir_can_be_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MODEL_COMPARE_HOME", str(tmp_path))

    assert find_project_dir() == tmp_path


@pytest.mark.asyncio
async def test_tui_loads_prompts_and_preselects_models(tmp_path: Path) -> None:
    make_project(tmp_path)
    app = ModelCompareApp(tmp_path)

    async with app.run_test():
        assert app.prompts[0].title == "Existing question"
        assert "Why?" in str(app.query_one("#prompt-preview", Static).content)
        assert app.query_one("#model-choice", SelectionList).selected == ["first", "second"]


@pytest.mark.asyncio
async def test_tui_persists_selected_theme(tmp_path: Path) -> None:
    make_project(tmp_path)
    theme_path = tmp_path / "settings" / "theme"
    app = ModelCompareApp(tmp_path, theme_path=theme_path)

    async with app.run_test() as pilot:
        app.theme = "textual-light"
        await pilot.pause()

    assert theme_path.read_text() == "textual-light\n"
    assert ModelCompareApp(tmp_path, theme_path=theme_path).theme == "textual-light"


@pytest.mark.asyncio
async def test_tui_builds_a_custom_prompt(tmp_path: Path) -> None:
    make_project(tmp_path)
    app = ModelCompareApp(tmp_path)

    async with app.run_test() as pilot:
        await pilot.click("#prompt-custom")
        app.query_one("#custom-title", Input).value = "One-off"
        app.query_one("#custom-body", TextArea).load_text("What changed?")

        prompt = app._selected_prompt()

        assert prompt.title == "One-off"
        assert prompt.body == "What changed?"
        assert prompt.source_path is None


@pytest.mark.asyncio
async def test_tui_adds_a_model_and_selects_it(tmp_path: Path) -> None:
    make_project(tmp_path)
    app = ModelCompareApp(tmp_path)

    async with app.run_test() as pilot:
        await pilot.click("#add-model")
        app.screen.query_one("#new-model-alias", Input).value = "new"
        app.screen.query_one("#new-model-slug", Input).value = "vendor/new"
        await pilot.click("#add-model-save")
        await pilot.pause()

        assert app.config.aliases["new"] == "vendor/new"
        assert app.query_one("#model-choice", SelectionList).selected == [
            "first",
            "second",
            "new",
        ]
        assert 'new = "vendor/new"' in (tmp_path / "models.toml").read_text()


@pytest.mark.asyncio
async def test_tui_deletes_a_model_and_refreshes_choices(tmp_path: Path) -> None:
    make_project(tmp_path)
    app = ModelCompareApp(tmp_path)

    async with app.run_test() as pilot:
        await pilot.click("#delete-model")
        await pilot.click("#delete-model-confirm")
        await pilot.pause()

        assert app.config.aliases == {"second": "vendor/second"}
        assert app.query_one("#model-choice", SelectionList).selected == ["second"]
        assert "first =" not in (tmp_path / "models.toml").read_text()


@pytest.mark.asyncio
async def test_tui_runs_selected_models_and_writes_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_project(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    async def fake_run_all(pairs, system_prompt, user_prompt, api_key, timeout, on_result):
        results = [
            ModelResult(alias=alias, slug=slug, content=f"Response from {alias}")
            for alias, slug in pairs
        ]
        for result in results:
            await on_result(result)
        return results

    monkeypatch.setattr(tui, "run_all", fake_run_all)
    app = ModelCompareApp(tmp_path)

    async with app.run_test() as pilot:
        await pilot.click("#run")
        await pilot.click("#confirm")
        await app.workers.wait_for_complete()

        assert "Run complete" in str(app.query_one("#run-message", Static).content)
        reports = list((tmp_path / "runs").glob("*/report.md"))
        assert len(reports) == 1
        assert "Response from first" in reports[0].read_text()
