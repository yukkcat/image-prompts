import pytest

from prompt_registry.models import Source
from prompt_registry.parsers import (
    parse_awesome_gpt4o,
    parse_awesome_gpt_image,
    parse_banana_json,
    parse_freestylefly_json,
    parse_source,
    parse_youmind,
)


def source(adapter: str, *, model: str = "") -> Source:
    return Source(
        id="test-source",
        name="Test",
        adapter=adapter,
        url="https://raw.githubusercontent.com/example/repo/main/README.md",
        homepage="https://github.com/example/repo",
        minimum_items=1,
        model=model,
    )


def test_banana_json_maps_reference_data() -> None:
    payload = b'''[
      {
        "title": "Poster",
        "prompt": "Create a poster",
        "preview": "https://example.com/cover.png",
        "reference_image_urls": ["https://example.com/ref.png"],
        "author": "Author",
        "category": "Work",
        "sub_category": "Poster",
        "created": "2026-01-01",
        "mode": "generate"
      }
    ]'''
    item = parse_banana_json(source("banana-json"), payload)[0]
    assert item["title"] == "Poster"
    assert item["referenceImageUrls"] == ["https://example.com/ref.png"]
    assert item["tags"] == ["Work", "Poster", "Author"]


def test_freestylefly_json_maps_case_data() -> None:
    payload = b'''{
      "cases": [
        {
          "id": 7,
          "title": "Architecture",
          "image": "/images/case7.jpg",
          "sourceLabel": "Alice",
          "sourceUrl": "",
          "prompt": "Create an architectural rendering.",
          "category": "Architecture & Spaces",
          "styles": ["3D"],
          "scenes": ["Commerce"],
          "featured": true,
          "githubUrl": "https://github.com/example/repo/blob/main/gallery.md#case-7"
        }
      ]
    }'''
    item = parse_freestylefly_json(
        Source(
            id="test-source",
            name="Test",
            adapter="freestylefly-json",
            url="https://raw.githubusercontent.com/example/repo/main/data/cases.json",
            homepage="https://github.com/example/repo",
            minimum_items=1,
            model="gpt-image-2",
        ),
        payload,
    )[0]
    image_url = "https://raw.githubusercontent.com/example/repo/main/data/images/case7.jpg"
    assert item["coverUrl"] == image_url
    assert item["referenceImageUrls"] == [image_url]
    assert item["sourceUrl"] == "https://github.com/example/repo/blob/main/gallery.md#case-7"
    assert item["author"] == "Alice"
    assert item["tags"] == [
        "gpt-image-2",
        "Architecture & Spaces",
        "3D",
        "Commerce",
        "featured",
    ]
    assert item["imageModel"] == "gpt-image-2"


def test_parse_source_rejects_results_below_minimum_items() -> None:
    configured_source = Source(
        id="test-source",
        name="Test",
        adapter="freestylefly-json",
        url="https://raw.githubusercontent.com/example/repo/main/data/cases.json",
        homepage="https://github.com/example/repo",
        minimum_items=2,
        model="gpt-image-2",
    )
    payload = b'''{
      "cases": [
        {"id": 1, "title": "Only case", "prompt": "Create an image."}
      ]
    }'''

    with pytest.raises(ValueError, match="produced 1 items; expected at least 2"):
        parse_source(configured_source, payload)


def test_awesome_markdown_uses_fenced_prompt_and_images() -> None:
    payload = """
## Photography
### Night scene
<img src="images/night.png">

**Prompt:**
```text
Create a realistic night scene.
```
**Source:** [Alice](https://example.com/post)
""".replace("Prompt", "提示词").replace("Source", "来源").encode()
    item = parse_awesome_gpt_image(source("awesome-gpt-image-markdown"), payload)[0]
    assert item["prompt"] == "Create a realistic night scene."
    assert item["coverUrl"].endswith("/main/images/night.png")
    assert item["author"] == "Alice"


def test_awesome_markdown_does_not_use_image_alt_text_as_description() -> None:
    payload = """
### Product image

![A generated product](images/product.png)

The actual description.

- **模型:** gpt4o
- **提示词文本:** `Create a product image.`
""".encode()
    item = parse_awesome_gpt4o(source("awesome-gpt4o-markdown"), payload)[0]
    assert item["description"] == "The actual description."


def test_awesome_markdown_keeps_prompts_that_share_a_source_url() -> None:
    payload = """
### First
**提示词:**
```
Create the first image.
```
**来源:** [Alice](https://example.com/post)

### Second
**提示词:**
```
Create the second image.
```
**来源:** [Alice](https://example.com/post)
""".encode()
    items = parse_awesome_gpt_image(source("awesome-gpt-image-markdown"), payload)
    assert len(items) == 2
    assert items[0]["id"] != items[1]["id"]


def test_gpt4o_markdown_reads_prompt_spanning_paragraphs() -> None:
    payload = """
### Product card

- **提示词文本:** `Create a product card with

several clearly separated sections.`
""".encode()
    item = parse_awesome_gpt4o(source("awesome-gpt4o-markdown"), payload)[0]
    assert item["prompt"] == "Create a product card with\n\nseveral clearly separated sections."


def test_gpt4o_markdown_uses_inline_code_prompt() -> None:
    payload = """
### Product card

A short description.

- **Model:** gpt4o
- **Prompt text:** `Create a clean product card.`
- **Example:** <img src="https://example.com/card.png">
- **Author:** [Bob](https://example.com/bob)
""".replace("Model", "模型").replace("Prompt text", "提示词文本").replace("Example", "示例图片").replace("Author", "作者").encode()
    item = parse_awesome_gpt4o(source("awesome-gpt4o-markdown"), payload)[0]
    assert item["prompt"] == "Create a clean product card."
    assert item["description"] == "A short description."
    assert item["imageModel"] == "gpt4o"


def test_youmind_markdown_reads_description_date_and_prompt() -> None:
    payload = """
### No. 7: Education - Diagram

#### Description
A useful diagram.

#### Prompt
```
Create a detailed diagram.
```

#### Images
<img src="https://example.com/diagram.png">

#### Details
- **Author:** [Carol](https://example.com/carol)
- **Source:** [Post](https://example.com/post)
- **Published:** 2026年4月19日
""".replace("Description", "描述").replace("Prompt", "提示词").replace("Images", "生成图片").replace("Details", "详情").replace("Author", "作者").replace("Source", "来源").replace("Published", "发布时间").encode()
    item = parse_youmind(source("youmind-markdown", model="gpt-image-2"), payload)[0]
    assert item["title"] == "Education - Diagram"
    assert item["description"] == "A useful diagram."
    assert item["createdAt"] == "2026-04-19"
    assert item["sourceUrl"] == "https://example.com/post"
    assert item["tags"] == ["gpt-image-2", "Education", "Carol"]


def test_youmind_keeps_different_prompts_with_the_same_number() -> None:
    payload = """
### No. 1: First
#### 提示词
```
Create the first image.
```

### No. 1: Second
#### 提示词
```
Create the second image.
```
""".encode()
    items = parse_youmind(source("youmind-markdown", model="gpt-image-2"), payload)
    assert len(items) == 2
    assert items[0]["id"] != items[1]["id"]
