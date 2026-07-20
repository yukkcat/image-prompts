import sys

import pytest

from prompt_registry import sync


def test_failed_fetch_preserves_existing_output(monkeypatch, tmp_path) -> None:
    output = tmp_path / "dist"
    output.mkdir()
    manifest = output / "manifest.json"
    manifest.write_text('{"registryHash":"existing"}\n', encoding="utf-8")

    def fail(_sources):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(sync, "fetch_all", fail)
    monkeypatch.setattr(sys, "argv", ["prompt_registry", "--output", str(output)])

    with pytest.raises(RuntimeError, match="upstream unavailable"):
        sync.main()

    assert manifest.read_text(encoding="utf-8") == '{"registryHash":"existing"}\n'
