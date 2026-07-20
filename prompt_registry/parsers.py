from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from markdown_it.token import Token

from .models import Source, absolute_url, deduplicate, inline, make_prompt, unique


MARKDOWN = MarkdownIt("commonmark", {"html": True}).enable("table")


def parse_source(source: Source, payload: bytes) -> list[dict[str, Any]]:
    parser = PARSERS.get(source.adapter)
    if not parser:
        raise ValueError(f"Unknown adapter {source.adapter!r} for {source.id}")
    items = parser(source, payload)
    if len(items) < source.minimum_items:
        raise ValueError(
            f"{source.id} produced {len(items)} items; expected at least {source.minimum_items}"
        )
    return items


def parse_banana_json(source: Source, payload: bytes) -> list[dict[str, Any]]:
    data = load_json_array(source, payload)
    return deduplicate(
        make_prompt(
            source,
            raw_id=f"{item.get('created', '')}|{item.get('title', '')}",
            title=item.get("title"),
            prompt=item.get("prompt"),
            cover_url=item.get("preview"),
            reference_image_urls=array(item.get("reference_image_urls")),
            tags=(item.get("category"), item.get("sub_category"), item.get("author")),
            author=item.get("author"),
            created_at=item.get("created"),
            image_mode=item.get("mode"),
        )
        for item in data
    )


def parse_davidwu_json(source: Source, payload: bytes) -> list[dict[str, Any]]:
    data = load_json_array(source, payload)
    result = []
    for index, item in enumerate(data, 1):
        image = item.get("image")
        tags = [item.get("category_cn"), item.get("category"), item.get("author"), item.get("source")]
        if item.get("needs_ref"):
            tags.append("需要参考图")
        result.append(
            make_prompt(
                source,
                raw_id=item.get("id") or index,
                title=item.get("title_cn") or item.get("title_en"),
                prompt=item.get("prompt"),
                description=item.get("note"),
                cover_url=image,
                reference_image_urls=[image] if image else [],
                tags=tags,
                author=item.get("author"),
                image_model="gpt-image-2",
            )
        )
    return deduplicate(result)


def parse_awesome_gpt_image(source: Source, payload: bytes) -> list[dict[str, Any]]:
    result = []
    for title, category, tokens in markdown_sections(decode(payload)):
        prompt = prompt_fence(tokens)
        if not prompt:
            continue
        images = extract_images(source, tokens)
        author, item_url = labeled_link(tokens, "来源")
        result.append(
            make_prompt(
                source,
                title=title,
                prompt=prompt,
                description=first_paragraph(tokens, exclude=("提示词", "来源")),
                cover_url=images[0] if images else "",
                reference_image_urls=images,
                tags=[clean_category(category), author],
                author=author,
                source_url=item_url,
                image_model="gpt-image-2",
            )
        )
    return deduplicate(result)


def parse_awesome_gpt4o(source: Source, payload: bytes) -> list[dict[str, Any]]:
    result = []
    for title, _category, tokens in markdown_sections(decode(payload)):
        prompt = labeled_code(tokens, "提示词文本")
        if not prompt:
            continue
        images = extract_images(source, tokens)
        author, item_url = labeled_link(tokens, "作者")
        result.append(
            make_prompt(
                source,
                title=title,
                prompt=prompt,
                description=first_paragraph(tokens, exclude=("模型", "提示词文本", "示例图片", "作者")),
                cover_url=images[0] if images else "",
                reference_image_urls=images,
                tags=["gpt4o", author],
                author=author,
                source_url=item_url,
                image_model="gpt4o",
            )
        )
    return deduplicate(result)


def parse_youmind(source: Source, payload: bytes) -> list[dict[str, Any]]:
    result = []
    for raw_title, _category, tokens in markdown_sections(decode(payload)):
        match = re.match(r"No\.\s*(\d+)\s*[:：]\s*(.+)", raw_title, re.I)
        if not match:
            continue
        item_number, title = match.groups()
        prompt = prompt_fence(tokens)
        if not prompt:
            continue
        images = extract_images(source, tokens)
        category = title.split(" - ", 1)[0] if " - " in title else ""
        author, _author_url = labeled_link(tokens, "作者")
        _source_name, item_url = labeled_link(tokens, "来源")
        result.append(
            make_prompt(
                source,
                raw_id=f"{item_number}\n{title}\n{prompt}",
                title=title,
                prompt=prompt,
                description=paragraph_after_heading(tokens, "描述"),
                cover_url=images[0] if images else "",
                reference_image_urls=images,
                tags=[source.model, category, author],
                author=author,
                source_url=item_url,
                created_at=published_date(tokens),
                image_model=source.model,
            )
        )
    return deduplicate(result)


def load_json_array(source: Source, payload: bytes) -> list[dict[str, Any]]:
    data = json.loads(payload.decode("utf-8-sig"))
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{source.id} must return a JSON array of objects")
    return data


def decode(payload: bytes) -> str:
    return payload.decode("utf-8-sig")


def array(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def markdown_sections(text: str) -> Iterable[tuple[str, str, list[Token]]]:
    tokens = MARKDOWN.parse(text)
    category = ""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == "heading_open" and token.tag == "h2":
            category = heading_text(tokens, index)
            index += 3
            continue
        if token.type != "heading_open" or token.tag != "h3":
            index += 1
            continue
        title = heading_text(tokens, index)
        end = index + 3
        while end < len(tokens):
            candidate = tokens[end]
            if candidate.type == "heading_open" and candidate.tag in {"h2", "h3"}:
                break
            end += 1
        yield title, category, tokens[index + 3 : end]
        index = end


def heading_text(tokens: list[Token], index: int) -> str:
    if index + 1 >= len(tokens) or tokens[index + 1].type != "inline":
        return ""
    return token_text(tokens[index + 1])


def token_text(token: Token) -> str:
    if not token.children:
        return inline(token.content)
    parts = []
    for child in token.children:
        if child.type in {"text", "code_inline", "image"}:
            parts.append(child.content)
        elif child.type in {"softbreak", "hardbreak"}:
            parts.append(" ")
    return inline("".join(parts))


def prompt_fence(tokens: list[Token]) -> str:
    marker_seen = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == "heading_open" and token.tag == "h4":
            marker_seen = "提示词" in heading_text(tokens, index)
            index += 3
            continue
        if token.type == "inline" and "提示词" in token_text(token):
            marker_seen = True
        elif marker_seen and token.type == "fence":
            return token.content.strip()
        index += 1
    return ""


def labeled_code(tokens: list[Token], label: str) -> str:
    for index, token in enumerate(tokens):
        if token.type != "inline" or label not in token_text(token):
            continue
        for child in token.children or []:
            if child.type == "code_inline" and child.content.strip():
                return child.content.strip()
        opening = token.content.find("`", token.content.find(label) + len(label))
        if opening < 0:
            continue
        parts = [token.content[opening + 1 :]]
        for candidate in tokens[index + 1 :]:
            if candidate.type != "inline":
                continue
            closing = candidate.content.find("`")
            if closing >= 0:
                parts.append(candidate.content[:closing])
                return "\n\n".join(parts).strip()
            parts.append(candidate.content)
    return ""


def token_links(token: Token) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    href = ""
    label: list[str] = []
    for child in token.children or []:
        if child.type == "link_open":
            href = child.attrGet("href") or ""
            label = []
        elif child.type == "link_close" and href:
            result.append((inline("".join(label)), href))
            href = ""
        elif href and child.type in {"text", "code_inline", "image"}:
            label.append(child.content)
    return result


def labeled_link(tokens: list[Token], label: str) -> tuple[str, str]:
    for token in tokens:
        if token.type != "inline" or label not in token_text(token):
            continue
        links = token_links(token)
        if links:
            return links[0]
    return "", ""


def extract_images(source: Source, tokens: list[Token]) -> list[str]:
    candidates: list[str] = []
    for token in tokens:
        if token.type == "inline":
            for child in token.children or []:
                if child.type == "image":
                    candidates.append(child.attrGet("src") or "")
                elif child.type == "html_inline":
                    candidates.extend(html_images(child.content))
        elif token.type == "html_block":
            candidates.extend(html_images(token.content))
    return unique(
        resolved
        for candidate in candidates
        if (resolved := absolute_url(source.url, candidate)) and not decorative_image(resolved)
    )


def html_images(value: str) -> list[str]:
    return [image.get("src", "") for image in BeautifulSoup(value, "html.parser").find_all("img")]


def decorative_image(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.hostname in {"img.shields.io", "awesome.re"}
        or "badge.svg" in parsed.path.lower()
        or "/actions/workflows/" in parsed.path.lower()
    )


def first_paragraph(tokens: list[Token], *, exclude: tuple[str, ...]) -> str:
    for token in tokens:
        if token.type != "inline":
            continue
        text = token_text(token)
        if text and not any(marker in text for marker in exclude) and not extract_inline_images(token):
            return text
    return ""


def extract_inline_images(token: Token) -> bool:
    return any(
        child.type == "image" or (child.type == "html_inline" and "<img" in child.content.lower())
        for child in token.children or []
    )


def paragraph_after_heading(tokens: list[Token], label: str) -> str:
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == "heading_open" and token.tag == "h4" and label in heading_text(tokens, index):
            for candidate in tokens[index + 3 :]:
                if candidate.type == "heading_open":
                    return ""
                if candidate.type == "inline":
                    return token_text(candidate)
            return ""
        index += 1
    return ""


def published_date(tokens: list[Token]) -> str:
    for token in tokens:
        if token.type != "inline":
            continue
        match = re.search(r"发布时间[:：]\s*(\d{4})年(\d{1,2})月(\d{1,2})日", token_text(token))
        if match:
            year, month, day = map(int, match.groups())
            return f"{year:04d}-{month:02d}-{day:02d}"
    return ""


def clean_category(value: str) -> str:
    return re.sub(r"^[^\w]+", "", inline(value), flags=re.UNICODE)


PARSERS: dict[str, Callable[[Source, bytes], list[dict[str, Any]]]] = {
    "banana-json": parse_banana_json,
    "davidwu-json": parse_davidwu_json,
    "awesome-gpt-image-markdown": parse_awesome_gpt_image,
    "awesome-gpt4o-markdown": parse_awesome_gpt4o,
    "youmind-markdown": parse_youmind,
}
