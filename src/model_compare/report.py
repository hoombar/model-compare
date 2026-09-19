"""Markdown and HTML report generation."""

from __future__ import annotations

import datetime as dt
import html
import re
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt

from .prompts import PromptSpec
from .runner import ModelResult

_MD = MarkdownIt("default", {"html": True})


@dataclass(frozen=True)
class RunArtifacts:
    run_dir: Path
    markdown_path: Path
    html_path: Path | None

HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
         max-width: 920px; margin: 0 auto; padding: 2rem 1.25rem 4rem;
         line-height: 1.6; color: #1f2328; background: #fff; }}
  h1, h2 {{ border-bottom: 1px solid #d1d9e0; padding-bottom: .3rem; margin-top: 2rem; }}
  code, pre {{ background: #f6f8fa; border-radius: 6px; font-size: .92em; }}
  code {{ padding: .15em .35em; }}
  pre {{ padding: .9rem 1rem; overflow-x: auto; }}
  pre code {{ padding: 0; background: none; font-size: 1em; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #d1d9e0; padding: .45rem .7rem; text-align: left; }}
  th {{ background: #f6f8fa; }}
  blockquote {{ border-left: 4px solid #d1d9e0; margin: 0; padding: 0 1em; color: #59636e; }}
  details {{ border: 1px solid #d1d9e0; border-radius: 6px; padding: .5rem .9rem; margin: 1rem 0; }}
  summary {{ cursor: pointer; font-weight: 600; }}
  .mermaid {{ display: flex; justify-content: center; margin: 1rem 0;
              background: #f6f8fa; border-radius: 6px; padding: 1rem; }}
  hr {{ border: none; border-top: 1px solid #d1d9e0; margin: 2rem 0; }}
  @media (prefers-color-scheme: dark) {{
    body {{ color: #e6edf3; background: #0d1117; }}
    h1, h2, th, td, details, hr {{ border-color: #3d444d; }}
    th {{ background: #151b23; }}
    code, pre {{ background: #151b23; }}
    blockquote {{ color: #9198a1; }}
    .mermaid {{ background: #151b23; }}
  }}
</style>
</head>
<body>
{body}
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  mermaid.initialize({{ startOnLoad: false, theme: dark ? "dark" : "default" }});
  for (const code of document.querySelectorAll("pre code.language-mermaid")) {{
    const div = document.createElement("div");
    div.className = "mermaid";
    div.textContent = code.textContent;
    code.closest("pre").replaceWith(div);
  }}
  await mermaid.run();
</script>
</body>
</html>
"""


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "prompt"


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def _fmt_latency(seconds: float) -> str:
    return f"{seconds:.1f}s"


def _fmt_int(value: int | None) -> str:
    return "—" if value is None else str(value)


def _fmt_cost(value: float | None) -> str:
    if value is None:
        return "—"
    if value == 0:
        return "$0"
    return f"${value:.6f}"


def build_markdown(prompt: PromptSpec, results: list[ModelResult], generated_at: str) -> str:
    lines: list[str] = []
    lines.append(f"# Model Compare: {prompt.title}")
    lines.append("")
    lines.append(f"- **Run:** {generated_at}")
    prompt_source = f"`{prompt.source_path}`" if prompt.source_path else "Custom prompt"
    lines.append(f"- **Prompt source:** {prompt_source}")
    lines.append(f"- **Models:** {len(results)}")
    lines.append("")
    lines.append("## Prompt")
    lines.append("")
    lines.append(prompt.body)
    lines.append("")
    lines.append("<details>")
    lines.append("<summary>System prompt</summary>")
    lines.append("")
    lines.append("```text")
    lines.append(prompt.system_prompt)
    lines.append("```")
    lines.append("")
    lines.append("</details>")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Model | Slug | Latency | Prompt tokens | Completion tokens | Cost |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        name = f"`{r.alias}`" if r.alias != r.slug else r.alias
        status = "" if r.ok else " (error)"
        lines.append(
            f"| {name}{status} | `{r.slug}` | {_fmt_latency(r.latency_s)} "
            f"| {_fmt_int(r.prompt_tokens)} | {_fmt_int(r.completion_tokens)} "
            f"| {_fmt_cost(r.cost)} |"
        )
    lines.append("")
    for r in results:
        lines.append("---")
        lines.append("")
        lines.append(f"## {r.alias}")
        lines.append("")
        meta = f"`{r.slug}` · {_fmt_latency(r.latency_s)} · {_fmt_cost(r.cost)}"
        lines.append(f"_{meta}_")
        lines.append("")
        if not r.ok:
            lines.append(f"> **Error:** {r.error}")
            lines.append("")
        elif r.content:
            lines.append(r.content.strip())
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Generated by [model-compare](https://github.com/hoombar/model-compare).*")
    lines.append("")
    return "\n".join(lines)


def write_run(
    run_dir: Path,
    prompt: PromptSpec,
    results: list[ModelResult],
    generated_at: str,
) -> Path:
    """Write report.md plus raw per-model responses; returns the report path."""
    run_dir.mkdir(parents=True, exist_ok=True)
    responses_dir = run_dir / "responses"
    responses_dir.mkdir(exist_ok=True)
    for r in results:
        if r.content:
            (responses_dir / f"{_safe_name(r.alias)}.md").write_text(r.content.strip() + "\n")
    md_path = run_dir / "report.md"
    md_path.write_text(build_markdown(prompt, results, generated_at))
    return md_path


def write_html(md_path: Path, title: str) -> Path:
    """Render report.md to a self-contained HTML file with mermaid.js."""
    body = _MD.render(md_path.read_text())
    html_path = md_path.with_suffix(".html")
    html_path.write_text(
        HTML_TEMPLATE.format(title=html.escape(title), body=body),
    )
    return html_path


def write_results(
    output_root: Path,
    prompt: PromptSpec,
    results: list[ModelResult],
    *,
    include_html: bool = True,
    dry_run: bool = False,
    now: dt.datetime | None = None,
) -> RunArtifacts:
    """Write all artifacts for a completed comparison run."""
    generated_at = (now or dt.datetime.now().astimezone()).strftime("%Y%m%d-%H%M%S")
    prefix = "dryrun-" if dry_run else ""
    run_dir = output_root / f"{prefix}{generated_at}-{slugify(prompt.title)}"
    markdown_path = write_run(run_dir, prompt, results, generated_at)
    html_path = write_html(markdown_path, prompt.title) if include_html else None
    return RunArtifacts(run_dir, markdown_path, html_path)
