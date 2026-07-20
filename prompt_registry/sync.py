from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from jsonschema import Draft202012Validator

from .models import Source
from .parsers import parse_source


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "dist"
USER_AGENT = "image-prompt-registry/0.1 (+https://github.com/)"
MAX_SOURCE_BYTES = 8 * 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(description="Build normalized prompt registry JSON files")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Fetch and validate without writing files")
    args = parser.parse_args()

    sources = load_sources(ROOT / "sources.json")
    schema = json.loads((ROOT / "schema" / "prompt.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    parsed = fetch_all(sources)

    for source in sources:
        for index, item in enumerate(parsed[source.id]):
            errors = sorted(validator.iter_errors(item), key=lambda error: list(error.path))
            if errors:
                path = ".".join(str(part) for part in errors[0].path)
                raise ValueError(f"{source.id}[{index}].{path}: {errors[0].message}")

    if args.check:
        print_summary(sources, parsed, changed=False, check_only=True)
        return 0

    changed = write_registry(args.output.resolve(), sources, parsed)
    print_summary(sources, parsed, changed=changed, check_only=False)
    return 0


def load_sources(path: Path) -> list[Source]:
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, list):
        raise ValueError("sources.json must contain an array")
    sources = [Source.from_dict(value) for value in values]
    ids = [source.id for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("sources.json contains duplicate source ids")
    return sources


def fetch_all(sources: list[Source]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    errors: list[str] = []
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(30, connect=10),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/markdown,text/plain,*/*;q=0.5"},
    ) as client:
        with ThreadPoolExecutor(max_workers=min(4, len(sources))) as pool:
            futures = {pool.submit(fetch_one, client, source): source for source in sources}
            for future in as_completed(futures):
                source = futures[future]
                try:
                    result[source.id] = future.result()
                except Exception as error:
                    errors.append(f"{source.id}: {error}")
    if errors:
        raise RuntimeError("Prompt synchronization failed:\n- " + "\n- ".join(sorted(errors)))
    return result


def fetch_one(client: httpx.Client, source: Source) -> list[dict[str, Any]]:
    response = client.get(source.url)
    response.raise_for_status()
    payload = response.content
    if len(payload) > MAX_SOURCE_BYTES:
        raise ValueError(f"response exceeds {MAX_SOURCE_BYTES // 1024 // 1024} MiB")
    return parse_source(source, payload)


def write_registry(
    output: Path,
    sources: list[Source],
    parsed: dict[str, list[dict[str, Any]]],
) -> bool:
    source_payloads = {source.id: json_bytes(parsed[source.id]) for source in sources}
    all_items = [item for source in sources for item in parsed[source.id]]
    combined_payload = json_bytes(all_items)
    source_entries = []
    for source in sources:
        payload = source_payloads[source.id]
        source_entries.append(
            source.manifest_entry(
                count=len(parsed[source.id]),
                path=f"sources/{source.id}.json",
                sha256=hashlib.sha256(payload).hexdigest(),
            )
        )

    registry_hash = hashlib.sha256(
        json.dumps(source_entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + combined_payload
    ).hexdigest()
    current_manifest = read_manifest(output / "manifest.json")
    if current_manifest.get("registryHash") == registry_hash:
        return False

    manifest = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "registryHash": registry_hash,
        "total": len(all_items),
        "promptsPath": "prompts.json",
        "sources": source_entries,
    }

    output.mkdir(parents=True, exist_ok=True)
    (output / "sources").mkdir(parents=True, exist_ok=True)
    for source in sources:
        atomic_write(output / "sources" / f"{source.id}.json", source_payloads[source.id])
    atomic_write(output / "prompts.json", combined_payload)
    atomic_write(output / "manifest.json", json_bytes(manifest))
    return True


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def print_summary(
    sources: list[Source],
    parsed: dict[str, list[dict[str, Any]]],
    *,
    changed: bool,
    check_only: bool,
) -> None:
    for source in sources:
        print(f"{source.id}: {len(parsed[source.id])}")
    total = sum(len(items) for items in parsed.values())
    status = "validated" if check_only else "updated" if changed else "unchanged"
    print(f"total: {total} ({status})")


if __name__ == "__main__":
    raise SystemExit(main())
