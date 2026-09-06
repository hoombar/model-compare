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
uv run model-compare prompts/trolley.md --models gpt,glm-flash,deepseek
uv run model-compare prompts/trolley.md --models tencent/hy4-preview,xiaomi/mimo-v2.5
```

Models can be short aliases from `models.toml` (currently the top 10 most popular models
on OpenRouter — refresh from the [rankings](https://openrouter.ai/rankings) when picking)
or full OpenRouter slugs. Precedence: `--models` > frontmatter `models`. Useful flags:
`--timeout SECONDS` (default 180), `--no-html`, `--dry-run` (canned responses, no API
calls), `--out DIR`.

## Prompt files

Markdown with YAML frontmatter; the body is the user prompt.

```markdown
---
title: "The Trolley Problem"
models: [gpt, glm-flash]
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

Short aliases map to OpenRouter slugs:

```toml
gpt = "openai/gpt-5.6-luna"
glm-flash = "z-ai/glm-5.3-flash"
```
