from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    adapter: str
    url: str
    homepage: str
    minimum_items: int
    model: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Source":
        source = cls(
            id=inline(value.get("id")),
            name=inline(value.get("name")),
            adapter=inline(value.get("adapter")),
            url=inline(value.get("url")),
            homepage=inline(value.get("homepage")),
            minimum_items=max(1, int(value.get("minimumItems", 1))),
            model=inline(value.get("model")),
        )
        if not re.fullmatch(r"[a-z0-9-]+", source.id):
            raise ValueError(f"Invalid source id: {source.id!r}")
        if not source.name or not source.adapter:
            raise ValueError(f"Source {source.id} is missing a name or adapter")
        for field_name in ("url", "homepage"):
            if urlparse(getattr(source, field_name)).scheme not in {"http", "https"}:
                raise ValueError(f"Source {source.id} has an invalid {field_name}")
        return source

    def manifest_entry(self, *, count: int, path: str, sha256: str) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "homepage": self.homepage,
            "upstreamUrl": self.url,
            "count": count,
            "path": path,
            "sha256": sha256,
        }


def inline(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def multiline(value: object) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def absolute_url(base: str, value: object) -> str:
    candidate = inline(value)
    if not candidate:
        return ""
    result = urljoin(base, candidate)
    return result if urlparse(result).scheme in {"http", "https"} else ""


def unique(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = inline(value)
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def make_prompt(
    source: Source,
    *,
    title: object,
    prompt: object,
    raw_id: object = "",
    description: object = "",
    cover_url: object = "",
    reference_image_urls: Iterable[object] = (),
    tags: Iterable[object] = (),
    author: object = "",
    source_url: object = "",
    created_at: object = "",
    image_mode: object = "",
    image_model: object = "",
    image_size: object = "",
    image_count: object = 0,
) -> dict[str, Any] | None:
    normalized_title = inline(title)
    normalized_prompt = multiline(prompt)
    if not normalized_title or not normalized_prompt:
        return None

    item_source_url = absolute_url(source.url, source_url) or source.homepage
    references = unique(absolute_url(source.url, value) for value in reference_image_urls)
    cover = absolute_url(source.url, cover_url) or (references[0] if references else "")
    identity = inline(raw_id)
    if not identity:
        identity = f"{item_source_url}\n{normalized_title}\n{normalized_prompt}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]

    item: dict[str, Any] = {
        "id": f"{source.id}:{digest}",
        "sourceId": source.id,
        "title": normalized_title,
        "prompt": normalized_prompt,
        "description": multiline(description),
        "coverUrl": cover,
        "referenceImageUrls": references,
        "tags": unique(tags),
        "author": inline(author),
        "sourceUrl": item_source_url,
        "createdAt": inline(created_at),
        "imageMode": inline(image_mode),
        "imageModel": inline(image_model) or source.model,
    }
    normalized_size = inline(image_size)
    if normalized_size:
        item["imageSize"] = normalized_size
    try:
        count = int(image_count)
    except (TypeError, ValueError):
        count = 0
    if count > 0:
        item["imageCount"] = count
    return item


def deduplicate(items: Iterable[dict[str, Any] | None]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if item and item["id"] not in seen:
            seen.add(item["id"])
            result.append(item)
    return result
