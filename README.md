# model-compare

Run one prompt against many LLMs (via [OpenRouter](https://openrouter.ai)) and get a
side-by-side comparison report in Markdown + HTML, including latency, token usage and cost
per model. Mermaid diagrams in model responses render natively in the report.

## Setup

```bash
uv sync
cp .env.example .env   # then add your OpenRouter API key
```

## Usage

```bash
uv run model-compare prompts/trolley.md                          # models from prompt frontmatter
uv run model-compare prompts/trolley.md --models gpt,claude,gemini
uv run model-compare prompts/political-bias.md --preset budget
```

Models can be short aliases from `models.toml` or full OpenRouter slugs
(e.g. `openai/gpt-5-mini`). Precedence: `--models` > `--preset` > frontmatter `models`
> `default` preset. Useful flags: `--timeout SECONDS` (default 180), `--no-html`,
`--dry-run` (canned responses, no API calls), `--out DIR`.

## Prompt files

Markdown with YAML frontmatter; the body is the user prompt.

```markdown
---
title: "The Trolley Problem"
models: [gpt, claude, gemini]
system_prompt: |
  You are a thoughtful assistant. Answer in a single paragraph (max 150 words).
  Then include a mermaid flowchart (fenced ```mermaid block) illustrating your reasoning.
---

A runaway trolley is heading toward five people...
```

Any format requirements (single paragraph, include a diagram, etc.) belong in
`system_prompt`.

## Output

Each run writes to `runs/<timestamp>-<prompt-slug>/`:

- `report.md` — comparison table (model, latency, tokens, cost) plus every model's full
  response; renders in Obsidian/VS Code/GitHub
- `report.html` — self-contained page with embedded CSS + mermaid.js for the browser
- `responses/<model>.md` — raw per-model responses

## models.toml

Short aliases map to OpenRouter slugs; presets group models:

```toml
gpt = "openai/gpt-5-mini"
claude = "anthropic/claude-sonnet-4.5"

[presets]
default = ["gpt", "claude"]
budget = ["flash", "haiku"]
```
