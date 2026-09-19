import datetime as dt
from pathlib import Path

from model_compare.prompts import custom_prompt
from model_compare.report import write_results
from model_compare.runner import ModelResult


def test_write_results_records_custom_prompt_and_paths(tmp_path: Path) -> None:
    prompt = custom_prompt("One-off question", "Why?", "Be clear.")
    results = [ModelResult(alias="test", slug="vendor/test", content="Because.")]

    artifacts = write_results(
        tmp_path,
        prompt,
        results,
        include_html=False,
        now=dt.datetime(2026, 9, 19, 12, 34, 56, tzinfo=dt.UTC),
    )

    assert artifacts.run_dir.name == "20260919-123456-one-off-question"
    assert artifacts.markdown_path == artifacts.run_dir / "report.md"
    assert artifacts.html_path is None
    report = artifacts.markdown_path.read_text()
    assert "**Prompt source:** Custom prompt" in report
    assert "Why?" in report
