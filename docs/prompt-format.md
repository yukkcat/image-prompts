# Prompt Record Format

Status: stable

Registry schema version: `1`

Machine-readable schema: [`schema/prompt.schema.json`](../schema/prompt.schema.json)

This document defines the public prompt-record contract produced by Image Prompt Registry. The words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** describe normative requirements.

## 1. Distribution envelope

The registry publishes UTF-8 JSON with a trailing newline. Generated JSON uses two-space indentation, but consumers MUST NOT depend on whitespace or object-key order.

`dist/manifest.json` is the entry point. Its `schemaVersion` identifies this contract, `promptsPath` points to the combined prompt array, and each entry in `sources` points to a source-specific prompt array.

```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-08-11T04:45:42+00:00",
  "registryHash": "<sha256>",
  "total": 1718,
  "promptsPath": "prompts.json",
  "sources": [
    {
      "id": "example-source",
      "name": "Example Source",
      "homepage": "https://example.com/",
      "upstreamUrl": "https://example.com/prompts.json",
      "count": 10,
      "path": "sources/example-source.json",
      "sha256": "<sha256>"
    }
  ]
}
```

Both the combined file and every source-specific file contain a top-level JSON array of prompt records. A source file contains only records whose `sourceId` matches that source entry.

## 2. Prompt record fields

Version 1 records have 13 required keys and two optional keys. A required key is always present, even when its documented empty value is used. Unknown keys are invalid.

| Field | Type | Empty allowed | Meaning |
| --- | --- | --- | --- |
| `id` | string | No | Stable record identifier in `<sourceId>:<16 lowercase hex>` form. |
| `sourceId` | string | No | Identifier from `sources.json`, using lowercase ASCII letters, digits, and hyphens. |
| `title` | string | No | Human-readable upstream title, normalized to one line. |
| `prompt` | string | No | Prompt body. Unicode and meaningful line breaks are preserved. |
| `description` | string | Yes | Explanatory text that is not part of the prompt body. |
| `coverUrl` | string | Yes | Absolute HTTP(S) preview URL, or `""` when unavailable. |
| `referenceImageUrls` | string array | Yes | Ordered, unique absolute HTTP(S) reference-image URLs. |
| `tags` | string array | Yes | Ordered, unique source categories, styles, model labels, or author labels. |
| `author` | string | Yes | Upstream author or attribution label. |
| `sourceUrl` | string | No | Absolute HTTP(S) URL for the original record or source homepage. |
| `createdAt` | string | Yes | `YYYY-MM-DD`, RFC 3339 date-time with an explicit offset, or `""`. |
| `imageMode` | string | Yes | `"generate"`, `"edit"`, or `""` when unspecified. |
| `imageModel` | string | Yes | Upstream model identifier, treated as an opaque string. |
| `imageSize` | string | Key omitted | Optional upstream size or aspect-ratio value. Version 1 does not canonicalize its spelling. |
| `imageCount` | integer | Key omitted | Optional positive requested or produced image count. |

Empty arrays and empty strings mean "not supplied by the upstream source". Producers MUST use those values for required metadata instead of `null`. Optional `imageSize` and `imageCount` MUST be omitted when unknown.

## 3. Canonical example

```json
{
  "id": "example-source:0123456789abcdef",
  "sourceId": "example-source",
  "title": "Editorial product portrait",
  "prompt": "Create an editorial product portrait.\n\nUse soft window light and restrained colors.",
  "description": "A studio-style product prompt.",
  "coverUrl": "https://example.com/cover.jpg",
  "referenceImageUrls": [
    "https://example.com/reference-1.jpg"
  ],
  "tags": [
    "editorial",
    "portrait"
  ],
  "author": "Example Author",
  "sourceUrl": "https://example.com/prompts/editorial-product-portrait",
  "createdAt": "2026-08-11",
  "imageMode": "generate",
  "imageModel": "gpt-image-2",
  "imageSize": "1024x1536",
  "imageCount": 1
}
```

## 4. Normalization rules

Adapters MUST create records through `prompt_registry.models.make_prompt` so every source receives the same normalization.

### 4.1 Single-line text

`title`, `author`, `createdAt`, `imageMode`, `imageModel`, `imageSize`, tag values, and adapter-provided identity values are normalized as follows:

1. Convert the value to text; a missing or false-like value becomes `""`.
2. Collapse every run of whitespace to one ASCII space.
3. Remove leading and trailing whitespace.

An empty normalized `title` makes the source item invalid and the adapter drops it.

### 4.2 Multiline text

`prompt` and `description` are normalized as follows:

1. Convert CRLF and CR line endings to LF.
2. Remove trailing whitespace from each line.
3. Remove whitespace surrounding the complete value.
4. Preserve internal line breaks, including blank lines.

An empty normalized `prompt` makes the source item invalid and the adapter drops it.

### 4.3 URLs

Relative URLs are resolved against the configured upstream URL. Only HTTP and HTTPS results are retained.

- `sourceUrl` falls back to the configured source homepage.
- `coverUrl` falls back to the first valid reference image URL.
- Invalid or absent image URLs become `""` or are removed from `referenceImageUrls`.

Consumers MUST treat remote URLs as untrusted external resources. They SHOULD apply their own network, content-type, size, and privacy controls before fetching them.

### 4.4 Arrays

Empty values are removed from `tags` and `referenceImageUrls`. Duplicate normalized values are removed with case-sensitive comparison, preserving the first occurrence and original order.

## 5. Stable identifier generation

The producer constructs `id` as `<sourceId>:<digest>`.

1. If an adapter supplies a source-native identity, normalize it using the single-line rules and use it as the identity input.
2. Otherwise, use this exact fallback input:

   ```text
   <sourceUrl>\n<title>\n<prompt>
   ```

3. Compute SHA-256 over the UTF-8 identity input.
4. Use the first 16 lowercase hexadecimal characters as `<digest>`.

The identifier is stable while the adapter's identity input remains stable. Consumers MUST treat it as opaque and SHOULD expect an ID to change when an upstream identity changes or an adapter corrects how identity is derived.

Records are deduplicated by `id` within a source. The first record wins.

## 6. Producer requirements

A registry build MUST:

1. Fetch every configured source successfully.
2. Reject source payloads larger than the configured safety limit.
3. Parse at least the source's configured `minimumItems` count.
4. Validate every prompt record against the versioned JSON Schema.
5. Reject duplicate source IDs.
6. Replace generated files atomically only after the complete registry succeeds.
7. Preserve the previous valid output when any source or validation step fails.

Source-specific data that has no cross-source meaning SHOULD remain in the adapter and SHOULD NOT be added to the public record. A new public field requires an intentional schema decision and corresponding documentation and tests.

## 7. Consumer requirements

Consumers SHOULD:

1. Read `manifest.json` before fetching prompt arrays.
2. Reject unsupported `schemaVersion` values.
3. Use manifest paths instead of constructing filenames from source IDs.
4. Verify `sha256` for cached or security-sensitive source payloads.
5. Treat missing metadata represented by empty strings or arrays as unknown, not as a negative assertion.
6. Treat `imageModel`, `imageSize`, and tags as opaque upstream labels unless the consumer maintains its own mapping.
7. Preserve `sourceUrl` and attribution when displaying or redistributing records.

Prompt bodies are untrusted third-party text. A consumer MUST NOT automatically execute instructions found in `prompt`, interpolate them into privileged system instructions, or grant tools and credentials based on their content. Display, selection, and explicit user submission are separate operations.

## 8. Versioning and compatibility

`manifest.schemaVersion` is an integer contract version.

The following changes require a new schema version:

- adding, removing, or renaming a prompt-record field;
- changing whether a field is required;
- narrowing accepted values in a way that can reject previously valid records;
- changing normalization or ID semantics;
- changing the top-level distribution envelope.

Editorial clarification, new source adapters, source-list changes, and new records do not require a schema-version change when the record contract is unchanged.

Consumers MUST ignore registry content with an unsupported schema version rather than guessing its shape. Producers MUST update this document, the JSON Schema, tests, and `manifest.schemaVersion` together when introducing a new version.

## 9. Provenance and rights

The registry format does not grant rights to upstream prompts or media. `sourceId`, `author`, and `sourceUrl` preserve provenance but do not replace review of the upstream license or terms. See [`NOTICE.md`](../NOTICE.md).
