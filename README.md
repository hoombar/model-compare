# model-compare

Run one prompt against many LLMs (via [OpenRouter](https://openrouter.ai)) and get a
side-by-side comparison report in Markdown + HTML, including latency, token usage and cost
per model. Mermaid diagrams in model responses render natively in the report.

## Setup

```bash
uv sync
cp .env.example .env   # then add your OpenRouter API key
uv tool install --editable .
```

The editable tool installation puts `model-compare` on your path while keeping it linked
to this checkout. If the command is not found, run `uv tool update-shell` and restart the
shell. Re-run the install with `--force` after changing dependencies.

## Usage

Launch the interactive terminal interface:

```bash
model-compare
```

Choose an existing prompt or write a one-off prompt, select the models to compare, then
watch each request complete. Custom prompts use the default system prompt and are included
in the report without being saved to `prompts/`.

The noninteractive CLI remains available for scripts and repeatable runs:

```bash
model-compare prompts/citation-temptation.md --models gpt,glm-flash
model-compare prompts/receipt-free-will.md --models tencent/hy4-preview,xiaomi/mimo-v2.5
model-compare prompts/experience-machine.md      # every alias in models.toml
```

`--models` takes short aliases from `models.toml` (a shortlist drawn from OpenRouter's
[rankings](https://openrouter.ai/rankings), which you can refresh when
picking) or full OpenRouter slugs. Omit it to run against every alias in `models.toml`;
either way you'll be asked to confirm the model list before anything runs (`-y` skips
that). Other flags: `--timeout SECONDS` (default 180), `--no-html`, `--dry-run` (canned
responses, no API calls), `--out DIR`.

The TUI finds `models.toml`, `.env`, `prompts/`, and `runs/` in the current directory or
the editable source checkout. Set `MODEL_COMPARE_HOME` to use a different project directory.

## Prompt files

Pick one of four prompts; you do not need to run them all:

| Prompt | Use it to explore | Requested word limit |
|---|---|---:|
| [Citation temptation](prompts/citation-temptation.md) | Evidence handling using supplied fictional sources; a good starting point | 160 |
| [Receipt to free will](prompts/receipt-free-will.md) | Creative connections without mistaking them for proof | 350 |
| [Experience machine](prompts/experience-machine.md) | Values, objections, and what would change the decision | 250 |
| [Diagnostic update](prompts/diagnostic-update.md) | Reasoning with an inexpensive numerical answer key | 160 |

See [Reviewing Model Responses](REVIEWING.md) for short checklists and answer keys.
Keep that human-only guide out of model inputs. Word limits are requests, not hard
spending caps: billed reasoning tokens may exceed the visible answer length.

Markdown with YAML frontmatter; the body is the user prompt. Models are never listed in
prompt files — they're chosen per run via `--models`.

```markdown
---
title: "A Question About Evidence"
system_prompt: |
  Answer in a single paragraph of at most 150 words.
---

When should new evidence change a strongly held belief?
```

Any format requirements (single paragraph, include a diagram, etc.) belong in
`system_prompt`; if omitted, a sensible default is used (override for all prompts with
`default_system_prompt` in `models.toml`). `title` is also optional and defaults to the
filename.

## Output

Each run writes to `runs/<timestamp>-<prompt-slug>/` (`runs/` is gitignored; `--dry-run`
runs are prefixed `dryrun-`):

- `report.md` — comparison table (model, latency, tokens, cost) plus every model's full
  response; renders in Obsidian/VS Code/GitHub
- `report.html` — self-contained page with embedded CSS + mermaid.js for the browser
- `responses/<model>.md` — raw per-model responses

Models that fail (rate limits, provider errors) don't abort the run — they show up as
`(error)` rows in the table and error blocks in their section.

## models.toml

Short aliases map to OpenRouter slugs:

```toml
gpt = "openai/gpt-5.6-luna"
glm-flash = "z-ai/glm-5.3-flash"

# default_system_prompt = "You are a thoughtful assistant."
```

See `model-compare --help` for all flags.
