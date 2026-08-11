import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from prompt_registry.models import Source, make_prompt


ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_validator() -> Draft202012Validator:
    schema = load_json(ROOT / "schema" / "prompt.schema.json")
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_checked_in_registry_matches_prompt_schema() -> None:
    records = load_json(DIST / "prompts.json")
    validator = prompt_validator()

    for index, record in enumerate(records):
        errors = sorted(validator.iter_errors(record), key=lambda error: list(error.path))
        assert not errors, f"dist/prompts.json[{index}]: {errors[0].message}"

    ids = [record["id"] for record in records]
    assert len(ids) == len(set(ids))
    assert all(record["id"].startswith(f'{record["sourceId"]}:') for record in records)


def test_manifest_describes_the_checked_in_payloads() -> None:
    manifest = load_json(DIST / "manifest.json")
    combined_records = load_json(DIST / manifest["promptsPath"])
    source_records = []

    assert manifest["schemaVersion"] == 1

    for source in manifest["sources"]:
        payload_path = DIST / source["path"]
        payload = payload_path.read_bytes()
        records = json.loads(payload)

        assert hashlib.sha256(payload).hexdigest() == source["sha256"]
        assert len(records) == source["count"]
        assert all(record["sourceId"] == source["id"] for record in records)
        source_records.extend(records)

    assert combined_records == source_records
    assert len(combined_records) == manifest["total"]


def test_make_prompt_applies_the_documented_normalization() -> None:
    source = Source(
        id="example-source",
        name="Example Source",
        adapter="example",
        url="https://example.com/data/prompts.json",
        homepage="https://example.com/",
        minimum_items=1,
    )

    record = make_prompt(
        source,
        raw_id="  record\t  7  ",
        title="  Editorial\n product   portrait ",
        prompt="\r\nLine one   \r\n\r\nLine two\t\r\n",
        description="\r\nA description.  \r\n",
        cover_url="javascript:alert(1)",
        reference_image_urls=("../images/ref.jpg", "../images/ref.jpg", ""),
        tags=(" Fine   Art ", "Fine Art", " portrait ", ""),
        image_size=" 1024 x 1536 ",
        image_count="2",
    )

    digest = hashlib.sha256("record 7".encode()).hexdigest()[:16]
    assert record == {
        "id": f"example-source:{digest}",
        "sourceId": "example-source",
        "title": "Editorial product portrait",
        "prompt": "Line one\n\nLine two",
        "description": "A description.",
        "coverUrl": "https://example.com/images/ref.jpg",
        "referenceImageUrls": ["https://example.com/images/ref.jpg"],
        "tags": ["Fine Art", "portrait"],
        "author": "",
        "sourceUrl": "https://example.com/",
        "createdAt": "",
        "imageMode": "",
        "imageModel": "",
        "imageSize": "1024 x 1536",
        "imageCount": 2,
    }


def test_make_prompt_uses_the_documented_fallback_identity() -> None:
    source = Source(
        id="example-source",
        name="Example Source",
        adapter="example",
        url="https://example.com/prompts.json",
        homepage="https://example.com/",
        minimum_items=1,
    )

    record = make_prompt(
        source,
        title="Example title",
        prompt="Example prompt",
        source_url="https://example.com/prompts/1",
    )

    identity = "https://example.com/prompts/1\nExample title\nExample prompt"
    digest = hashlib.sha256(identity.encode()).hexdigest()[:16]
    assert record is not None
    assert record["id"] == f"example-source:{digest}"
