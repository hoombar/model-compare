"""Interactive terminal interface for model-compare."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    SelectionList,
    Static,
    TextArea,
)

from .config import (
    Config,
    add_model,
    delete_model,
    load_config,
    load_dotenv,
    validate_model,
)
from .prompts import PromptSpec, custom_prompt, discover_prompts
from .report import write_results
from .runner import ModelResult, run_all


def find_project_dir() -> Path:
    """Find prompts and configuration for local and editable installations."""
    if configured := os.environ.get("MODEL_COMPARE_HOME"):
        return Path(configured).expanduser()
    cwd = Path.cwd()
    if (cwd / "models.toml").exists() or (cwd / "prompts").is_dir():
        return cwd
    source_root = Path(__file__).resolve().parents[2]
    if (source_root / "models.toml").exists() or (source_root / "prompts").is_dir():
        return source_root
    return cwd


class ConfirmRun(ModalScreen[bool]):
    """Confirm a potentially billable model run."""

    DEFAULT_CSS = """
    ConfirmRun {
        align: center middle;
    }

    ConfirmRun > Vertical {
        width: 56;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }

    ConfirmRun Horizontal {
        height: auto;
        align-horizontal: right;
        margin-top: 1;
    }

    ConfirmRun Button {
        margin-left: 1;
    }
    """

    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]

    def __init__(self, prompt_title: str, model_count: int) -> None:
        super().__init__()
        self.prompt_title = prompt_title
        self.model_count = model_count

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Run comparison?", classes="dialog-title")
            yield Static(
                f"[b]{self.prompt_title}[/b]\n{self.model_count} model(s) will call OpenRouter."
            )
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button("Run", id="confirm", variant="primary")

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def action_cancel(self) -> None:
        self.dismiss(False)


class AddModel(ModalScreen[tuple[str, str] | None]):
    """Collect a new model alias and OpenRouter slug."""

    DEFAULT_CSS = """
    AddModel {
        align: center middle;
    }

    AddModel > Vertical {
        width: 64;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }

    AddModel Input, AddModel #add-model-message {
        margin-bottom: 1;
    }

    AddModel #add-model-message {
        height: auto;
        min-height: 1;
        color: $warning;
    }

    AddModel Horizontal {
        height: auto;
        align-horizontal: right;
    }

    AddModel Button {
        margin-left: 1;
    }
    """

    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]

    def __init__(self, existing_aliases: set[str]) -> None:
        super().__init__()
        self.existing_aliases = existing_aliases

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Add model", classes="dialog-title")
            yield Input(placeholder="Short alias, e.g. sonnet", id="new-model-alias")
            yield Input(placeholder="OpenRouter slug, e.g. anthropic/model-name", id="new-model-slug")
            yield Static(id="add-model-message")
            with Horizontal():
                yield Button("Cancel", id="add-model-cancel")
                yield Button("Add", id="add-model-save", variant="primary")

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        if event.button.id == "add-model-cancel":
            self.dismiss(None)
            return
        try:
            model = validate_model(
                self.query_one("#new-model-alias", Input).value,
                self.query_one("#new-model-slug", Input).value,
            )
            if model[0] in self.existing_aliases:
                raise ValueError(f"model alias already exists: {model[0]}")
        except ValueError as exc:
            self.query_one("#add-model-message", Static).update(str(exc))
            return
        self.dismiss(model)

    def action_cancel(self) -> None:
        self.dismiss(None)


class DeleteModel(ModalScreen[str | None]):
    """Choose one configured model to remove."""

    DEFAULT_CSS = """
    DeleteModel {
        align: center middle;
    }

    DeleteModel > Vertical {
        width: 68;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: round $error;
        background: $surface;
    }

    DeleteModel RadioSet {
        height: auto;
        max-height: 18;
        margin-bottom: 1;
    }

    DeleteModel Horizontal {
        height: auto;
        align-horizontal: right;
    }

    DeleteModel Button {
        margin-left: 1;
    }
    """

    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]

    def __init__(self, models: list[tuple[str, str]]) -> None:
        super().__init__()
        self.models = models

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Delete model from models.toml", classes="dialog-title")
            yield RadioSet(
                *[
                    RadioButton(
                        f"{alias}  [dim]{slug}[/dim]",
                        value=index == 0,
                        id=f"delete-choice-{index}",
                    )
                    for index, (alias, slug) in enumerate(self.models)
                ],
                id="delete-model-choice",
            )
            with Horizontal():
                yield Button("Cancel", id="delete-model-cancel")
                yield Button("Delete", id="delete-model-confirm", variant="error")

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        if event.button.id == "delete-model-cancel":
            self.dismiss(None)
            return
        pressed = self.query_one("#delete-model-choice", RadioSet).pressed_button
        if pressed is None:
            return
        index = int((pressed.id or "").removeprefix("delete-choice-"))
        self.dismiss(self.models[index][0])

    def action_cancel(self) -> None:
        self.dismiss(None)


class ModelCompareApp(App[None]):
    """Select a prompt and models, then monitor a comparison run."""

    TITLE = "Model Compare"
    SUB_TITLE = "OpenRouter evaluation runner"
    CSS = """
    Screen {
        background: $background;
    }

    #selection-view, #run-view {
        height: 1fr;
        padding: 1 2;
    }

    #selection-columns {
        height: 1fr;
    }

    .pane {
        width: 1fr;
        height: 1fr;
        margin: 0 1;
        padding: 1 2;
        border: round $panel;
    }

    .pane-title, .dialog-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #prompt-choice {
        height: auto;
        max-height: 12;
    }

    #prompt-preview {
        height: 1fr;
        margin-top: 1;
        padding: 1;
        background: $surface;
        overflow-y: auto;
    }

    #custom-fields {
        display: none;
        height: 1fr;
    }

    #custom-title {
        margin-bottom: 1;
    }

    #custom-body {
        height: 1fr;
        border: round $panel;
    }

    #model-choice {
        height: 1fr;
    }

    #model-actions {
        height: auto;
        margin-top: 1;
    }

    #model-actions Button {
        margin-right: 1;
    }

    #selection-message, #run-message {
        height: auto;
        min-height: 1;
        color: $warning;
        margin: 1 1 0 1;
    }

    #run-actions {
        height: auto;
        align-horizontal: right;
        margin: 0 1;
    }

    #run-view {
        display: none;
    }

    #run-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #results-table {
        height: 1fr;
    }

    #artifacts {
        height: auto;
        margin-top: 1;
        padding: 1;
        border: round $success;
        display: none;
    }
    """
    BINDINGS: ClassVar = [("q", "quit", "Quit")]

    def __init__(self, project_dir: Path | None = None) -> None:
        super().__init__()
        self.project_dir = project_dir or find_project_dir()
        self.config = Config()
        self.prompts: list[PromptSpec] = []
        self.startup_error: str | None = None
        try:
            load_dotenv(self.project_dir / ".env")
            self.config = load_config(self.project_dir / "models.toml")
            self.prompts = discover_prompts(
                self.project_dir / "prompts", self.config.default_system_prompt
            )
        except (OSError, ValueError) as exc:
            self.startup_error = str(exc)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="selection-view"):
            with Horizontal(id="selection-columns"):
                with Vertical(classes="pane"):
                    yield Label("1. Choose a prompt", classes="pane-title")
                    buttons = [
                        RadioButton(prompt.title, value=index == 0, id=f"prompt-{index}")
                        for index, prompt in enumerate(self.prompts)
                    ]
                    buttons.append(
                        RadioButton(
                            "Write a custom prompt",
                            value=not self.prompts,
                            id="prompt-custom",
                        )
                    )
                    yield RadioSet(*buttons, id="prompt-choice")
                    with Vertical(id="custom-fields"):
                        yield Input(placeholder="Prompt title", id="custom-title")
                        yield TextArea(id="custom-body")
                    yield Static(id="prompt-preview")
                with Vertical(classes="pane"):
                    yield Label("2. Choose models", classes="pane-title")
                    yield SelectionList[str](
                        *[
                            (f"{alias}  [dim]{slug}[/dim]", alias, True)
                            for alias, slug in self.config.aliases.items()
                        ],
                        id="model-choice",
                    )
                    with Horizontal(id="model-actions"):
                        yield Button("Add model", id="add-model")
                        yield Button("Delete model", id="delete-model", variant="error")
            yield Static(id="selection-message")
            with Horizontal(id="run-actions"):
                yield Button("Run comparison", id="run", variant="primary")
        with Container(id="run-view"):
            yield Static(id="run-title")
            yield DataTable(id="results-table", zebra_stripes=True)
            yield Static(id="run-message")
            yield Static(id="artifacts")
        yield Footer()

    def on_mount(self) -> None:
        if self.prompts:
            self._show_prompt_preview(0)
        else:
            self.query_one("#custom-fields").display = True
            self.query_one("#prompt-preview").display = False
        if self.startup_error:
            self._show_selection_error(f"Could not load project files: {self.startup_error}")
        elif not self.config.aliases:
            self._show_selection_error("No model aliases found in models.toml.")

    @on(RadioSet.Changed, "#prompt-choice")
    def prompt_changed(self, event: RadioSet.Changed) -> None:
        button_id = event.pressed.id or ""
        custom = button_id == "prompt-custom"
        self.query_one("#custom-fields").display = custom
        self.query_one("#prompt-preview").display = not custom
        if not custom and button_id.startswith("prompt-"):
            self._show_prompt_preview(int(button_id.removeprefix("prompt-")))

    def _show_prompt_preview(self, index: int) -> None:
        prompt = self.prompts[index]
        source = prompt.source_path.name if prompt.source_path else "Custom prompt"
        self.query_one("#prompt-preview", Static).update(
            f"[b]{source}[/b]\n\n{prompt.body}"
        )

    def _selected_prompt(self) -> PromptSpec:
        pressed = self.query_one("#prompt-choice", RadioSet).pressed_button
        if pressed is None:
            raise ValueError("select a prompt")
        if pressed.id == "prompt-custom":
            title = self.query_one("#custom-title", Input).value
            body = self.query_one("#custom-body", TextArea).text
            return custom_prompt(title, body, self.config.default_system_prompt)
        index = int((pressed.id or "").removeprefix("prompt-"))
        return self.prompts[index]

    def _selected_models(self) -> list[tuple[str, str]]:
        aliases = self.query_one("#model-choice", SelectionList).selected
        return [(alias, self.config.aliases[alias]) for alias in aliases]

    @on(Button.Pressed, "#add-model")
    def request_add_model(self) -> None:
        self.push_screen(AddModel(set(self.config.aliases)), self._add_model)

    def _add_model(self, model: tuple[str, str] | None) -> None:
        if model is None:
            return
        alias, slug = model
        selected = set(self.query_one("#model-choice", SelectionList).selected)
        try:
            add_model(self.project_dir / "models.toml", alias, slug)
            selected.add(alias)
            self._refresh_models(selected)
        except (OSError, ValueError) as exc:
            self._show_selection_error(f"Could not add model: {exc}")
            return
        self.query_one("#selection-message", Static).update("")
        self.notify(f"Added {alias}")

    @on(Button.Pressed, "#delete-model")
    def request_delete_model(self) -> None:
        if not self.config.aliases:
            self._show_selection_error("There are no models to delete.")
            return
        self.push_screen(DeleteModel(list(self.config.aliases.items())), self._delete_model)

    def _delete_model(self, alias: str | None) -> None:
        if alias is None:
            return
        selected = set(self.query_one("#model-choice", SelectionList).selected)
        selected.discard(alias)
        try:
            delete_model(self.project_dir / "models.toml", alias)
            self._refresh_models(selected)
        except (OSError, ValueError) as exc:
            self._show_selection_error(f"Could not delete model: {exc}")
            return
        self.query_one("#selection-message", Static).update("")
        self.notify(f"Deleted {alias}")

    def _refresh_models(self, selected: set[str]) -> None:
        self.config = load_config(self.project_dir / "models.toml")
        choices = self.query_one("#model-choice", SelectionList)
        choices.clear_options()
        choices.add_options(
            (
                f"{alias}  [dim]{slug}[/dim]",
                alias,
                alias in selected,
            )
            for alias, slug in self.config.aliases.items()
        )

    @on(Button.Pressed, "#run")
    def request_run(self) -> None:
        self.query_one("#selection-message", Static).update("")
        try:
            prompt = self._selected_prompt()
        except (ValueError, IndexError) as exc:
            self._show_selection_error(str(exc))
            return
        pairs = self._selected_models()
        if not pairs:
            self._show_selection_error("Select at least one model.")
            return
        if not os.environ.get("OPENROUTER_API_KEY"):
            self._show_selection_error(
                "OPENROUTER_API_KEY is not set. Add it to .env or export it."
            )
            return
        self.push_screen(
            ConfirmRun(prompt.title, len(pairs)),
            lambda confirmed: self._start_run(prompt, pairs) if confirmed else None,
        )

    def _start_run(self, prompt: PromptSpec, pairs: list[tuple[str, str]]) -> None:
        self.query_one("#selection-view").display = False
        self.query_one("#run-view").display = True
        self.query_one("#run-title", Static).update(
            f"Running [b]{prompt.title}[/b] against {len(pairs)} model(s)"
        )
        table = self.query_one("#results-table", DataTable)
        table.add_column("Model", key="model")
        table.add_column("Slug", key="slug")
        table.add_column("Status", key="status")
        table.add_column("Latency", key="latency")
        table.add_column("Tokens", key="tokens")
        table.add_column("Cost", key="cost")
        for alias, slug in pairs:
            table.add_row(alias, slug, "Pending", "", "", "", key=alias)
        self._run_models(prompt, pairs)

    @work(exclusive=True)
    async def _run_models(self, prompt: PromptSpec, pairs: list[tuple[str, str]]) -> None:
        table = self.query_one("#results-table", DataTable)
        for alias, _ in pairs:
            table.update_cell(alias, "status", "Running")

        async def report(result: ModelResult) -> None:
            status = "Complete" if result.ok else "Failed"
            tokens = (
                f"{result.prompt_tokens} -> {result.completion_tokens}"
                if result.prompt_tokens is not None and result.completion_tokens is not None
                else "-"
            )
            cost = f"${result.cost:.6f}" if result.cost is not None else "-"
            table.update_cell(result.alias, "status", status)
            table.update_cell(result.alias, "latency", f"{result.latency_s:.1f}s")
            table.update_cell(result.alias, "tokens", tokens)
            table.update_cell(result.alias, "cost", cost)

        try:
            results = await run_all(
                pairs,
                prompt.system_prompt,
                prompt.body,
                os.environ["OPENROUTER_API_KEY"],
                180.0,
                on_result=report,
            )
            artifacts = write_results(self.project_dir / "runs", prompt, results)
        except Exception as exc:  # noqa: BLE001 - keep failures visible inside the TUI
            self.query_one("#run-message", Static).update(f"Run failed: {exc}")
            return

        failed = sum(not result.ok for result in results)
        status = "Run complete" if not failed else f"Run complete with {failed} failure(s)"
        self.query_one("#run-message", Static).update(status)
        artifact_text = (
            f"[b]Report[/b]  {artifacts.markdown_path}\n"
            f"[b]HTML[/b]    {artifacts.html_path}"
        )
        artifact_widget = self.query_one("#artifacts", Static)
        artifact_widget.update(artifact_text)
        artifact_widget.display = True

    def _show_selection_error(self, message: str) -> None:
        self.query_one("#selection-message", Static).update(message)


def run_tui(project_dir: Path | None = None) -> None:
    ModelCompareApp(project_dir).run()
