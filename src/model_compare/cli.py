"""CLI entry point for model-compare."""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
import random
import sys
from pathlib import Path

from .config import Config, load_config, resolve_models
from .prompts import PromptSpec, load_prompt
from .report import slugify, write_html, write_run
from .runner import ModelResult, run_all


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader; never overrides existing environment variables."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="model-compare",
        description="Run one prompt against many OpenRouter models and build a "
        "side-by-side comparison report (markdown + HTML).",
    )
    parser.add_argument("prompt_file", type=Path, help="Markdown prompt file with YAML frontmatter")
    parser.add_argument(
        "--models",
        help="Comma-separated aliases (models.toml) or OpenRouter slugs; overrides "
        "--preset and frontmatter",
    )
    parser.add_argument("--preset", help="Preset name from models.toml")
    parser.add_argument("--config", type=Path, default=Path("models.toml"), help="Config path")
    parser.add_argument("--out", type=Path, default=Path("runs"), help="Output root directory")
    parser.add_argument(
        "--timeout", type=float, default=180.0, help="Per-model request timeout in seconds"
    )
    parser.add_argument("--no-html", action="store_true", help="Skip HTML export")
    parser.add_argument(
        "--dry-run", action="store_true", help="Use canned responses instead of calling the API"
    )
    return parser.parse_args(argv)


def _select_models(args: argparse.Namespace, prompt: PromptSpec, config: Config) -> list[str]:
    if args.models:
        return [m for m in args.models.split(",") if m.strip()]
    if args.preset:
        preset = config.presets.get(args.preset)
        if preset is None:
            raise SystemExit(
                f"error: unknown preset '{args.preset}'. "
                f"Available: {', '.join(sorted(config.presets)) or '(none)'}"
            )
        return preset
    if prompt.models:
        return prompt.models
    default = config.presets.get("default")
    if not default:
        raise SystemExit(
            "error: no models specified. Use --models, --preset, frontmatter 'models', "
            "or a 'default' preset in models.toml."
        )
    return default


def _dry_results(pairs: list[tuple[str, str]]) -> list[ModelResult]:
    results: list[ModelResult] = []
    for alias, slug in pairs:
        latency = random.uniform(0.6, 3.4)
        results.append(
            ModelResult(
                alias=alias,
                slug=slug,
                content=(
                    f"[dry-run] Sample response from **{alias}** ({slug}).\n\n"
                    "I would pull the lever, diverting the trolley onto the side track. "
                    "While any loss of life is tragic, most consequentialist — and many "
                    "deontological — framings accept that five deaths outweigh one, and the "
                    "action is taken under genuine necessity rather than malice.\n\n"
                    "```mermaid\n"
                    "flowchart TD\n"
                    '    A["Trolley approaching 5 workers"] --> B{"Pull the lever?"}\n'
                    '    B -- "Yes" --> C["Diverted: 1 death"]\n'
                    '    B -- "No" --> D["Continues: 5 deaths"]\n'
                    f'    C --> E["{alias}: fewer deaths, active choice"]\n'
                    f'    D --> F["{alias}: inaction preserves innocence"]\n'
                    "```\n"
                ),
                latency_s=latency,
                prompt_tokens=random.randint(90, 240),
                completion_tokens=random.randint(140, 420),
                cost=round(random.uniform(0.00002, 0.0015), 6),
            )
        )
    return results


def _print_summary(results: list[ModelResult]) -> None:
    width = max(len(r.alias) for r in results)
    for r in results:
        if r.ok:
            print(
                f"  ok    {r.alias:{width}}  {_fmt_latency(r.latency_s):>6}  "
                f"{r.prompt_tokens} -> {r.completion_tokens} tok  {_fmt_cost(r.cost)}"
            )
        else:
            print(f"  ERROR {r.alias:{width}}  {r.error}")


def _fmt_latency(seconds: float) -> str:
    return f"{seconds:.1f}s"


def _fmt_cost(value: float | None) -> str:
    return "—" if value is None else f"${value:.6f}"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    _load_dotenv(Path(".env"))
    config = load_config(args.config)

    if not args.prompt_file.exists():
        print(f"error: prompt file not found: {args.prompt_file}", file=sys.stderr)
        return 1
    try:
        prompt = load_prompt(args.prompt_file, config.default_system_prompt)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    raw_models = _select_models(args, prompt, config)
    pairs = resolve_models(raw_models, config)
    if not pairs:
        print(
            "error: no resolvable models. Add aliases to models.toml or use full slugs.",
            file=sys.stderr,
        )
        return 1

    if args.dry_run:
        results = _dry_results(pairs)
    else:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            print(
                "error: OPENROUTER_API_KEY is not set. Add it to .env or export it.",
                file=sys.stderr,
            )
            return 1
        print(f"Running '{prompt.title}' against {len(pairs)} model(s)...")
        results = asyncio.run(
            run_all(pairs, prompt.system_prompt, prompt.body, api_key, args.timeout)
        )

    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    run_dir = args.out / f"{stamp}-{slugify(prompt.title)}"
    md_path = write_run(run_dir, prompt, results, stamp)
    html_path = None if args.no_html else write_html(md_path, prompt.title)

    print()
    _print_summary(results)
    print(f"\nRun:    {run_dir}")
    print(f"Report: {md_path}")
    if html_path:
        print(f"HTML:   {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
