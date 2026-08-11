# Image Prompt Registry

[Simplified Chinese](README.zh-CN.md) | [Prompt record specification](docs/prompt-format.md) | [JSON Schema](schema/prompt.schema.json)

Image Prompt Registry collects public image-prompt sources, normalizes their records, validates them, and publishes static JSON for downstream applications. Consumers such as Infinite Canvas, Codex skills, websites, and local tools can read one stable format instead of maintaining a parser for every upstream source.

## Published data

Each successful sync writes the following files:

- `dist/manifest.json`: registry version, generation time, item count, source metadata, paths, and SHA-256 checksums.
- `dist/prompts.json`: every normalized prompt record in one JSON array.
- `dist/sources/<source-id>.json`: one JSON array for each configured source.

Start with `dist/manifest.json`. Use `promptsPath` for the combined registry or select a source entry and fetch its `path`. Verify a source payload with its `sha256` value when integrity matters.

The generated files can be served through GitHub Raw, GitHub Pages, jsDelivr, or any static file host.

## Prompt record

Every record follows schema version 1 and is validated against `schema/prompt.schema.json` before any generated file is replaced.

```json
{
  "id": "example-source:0123456789abcdef",
  "sourceId": "example-source",
  "title": "Editorial product portrait",
  "prompt": "Create an editorial product portrait with soft window light.",
  "description": "",
  "coverUrl": "https://example.com/cover.jpg",
  "referenceImageUrls": [],
  "tags": ["editorial", "portrait"],
  "author": "Example Author",
  "sourceUrl": "https://example.com/original-prompt",
  "createdAt": "2026-08-11",
  "imageMode": "generate",
  "imageModel": "gpt-image-2"
}
```

The full contract, including field semantics, empty-value rules, normalization, stable ID generation, and compatibility requirements, is documented in [Prompt Record Format](docs/prompt-format.md).

## Included sources

Source definitions live in `sources.json`.

| Source ID | Source | Default model |
| --- | --- | --- |
| `banana-prompt-quicker` | Banana Prompt Quicker | Unspecified |
| `davidwu-gpt-image2-prompts` | DavidWu GPT Image 2 Prompts | Set by the adapter |
| `freestylefly-gpt-image-2` | Freestylefly GPT Image 2 | `gpt-image-2` |
| `awesome-gpt-image` | Awesome GPT Image | Set by the adapter |
| `awesome-gpt4o-image-prompts` | Awesome GPT-4o Image Prompts | Set by the adapter |
| `youmind-gpt-image-2` | YouMind GPT Image 2 | `gpt-image-2` |
| `youmind-nano-banana-pro` | YouMind Nano Banana Pro | `nano-banana-pro` |

Each source declares a minimum expected item count. A failed request, parse error, schema violation, or unexpectedly small result fails the complete sync and preserves the last valid `dist` output.

## Local development

Requirements: Python 3.11 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m prompt_registry
.\.venv\Scripts\python -m pytest
```

Fetch and validate all sources without writing generated files:

```powershell
.\.venv\Scripts\python -m prompt_registry --check
```

Write generated files to another directory:

```powershell
.\.venv\Scripts\python -m prompt_registry --output .\build\registry
```

## Adding or changing a source

1. Add or update the source definition in `sources.json`.
2. Implement or update its adapter in `prompt_registry/parsers.py`.
3. Normalize records through `prompt_registry.models.make_prompt`.
4. Add parser fixtures and assertions under `tests/`.
5. Run the test suite and a network-backed `--check` before publishing.

Do not write source-specific fields directly into generated records. Extend the versioned public schema deliberately when a new cross-source field is required.

## Automated updates

`.github/workflows/sync.yml` runs daily and supports manual dispatch. A sync commits generated files only when normalized prompt content or source metadata changes; a new timestamp alone does not create a commit.

## License and upstream rights

The synchronization code and repository documentation are licensed under the MIT License. Prompts, images, names, and other upstream material remain subject to their original terms. This registry preserves source identifiers and URLs, does not relicense upstream content, and stores image URLs rather than copying image files. See [NOTICE.md](NOTICE.md).
