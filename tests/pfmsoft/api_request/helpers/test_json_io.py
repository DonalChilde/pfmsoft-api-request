"""Tests for JSON and JSONL helper functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from pfmsoft.api_request.helpers.json_io import (
    json_dump_bytes,
    json_dumps,
    json_dumps_path,
    json_load_path,
    json_loads,
    jsonl_dump_bytes,
    jsonl_dump_path,
    jsonl_dumps,
    jsonl_load_bytes,
    jsonl_load_bytes_indexed,
    jsonl_load_path,
    jsonl_load_path_indexed,
    jsonl_loads,
    jsonl_loads_indexed,
)


def test_json_loads_and_dumps_roundtrip() -> None:
    """json_dumps/json_loads should round-trip simple objects."""
    payload = {"alpha": 1, "beta": [1, 2, 3]}

    json_text = json_dumps(payload, indent=2)
    assert json_loads(json_text) == payload
    assert json_loads(json_dump_bytes(payload)) == payload


def test_json_dumps_path_respects_overwrite_and_adds_trailing_newline(
    tmp_path: Path,
) -> None:
    """File writer should include a trailing newline and enforce overwrite mode."""
    file_path = tmp_path / "nested" / "payload.json"

    char_count = json_dumps_path({"ok": True}, filepath=file_path)
    written_text = file_path.read_text(encoding="utf-8")

    assert written_text.endswith("\n")
    assert char_count == len(written_text)
    assert json_load_path(file_path) == {"ok": True}

    with pytest.raises(FileExistsError):
        json_dumps_path({"ok": False}, filepath=file_path)

    json_dumps_path({"ok": False}, filepath=file_path, overwrite=True)
    assert json_load_path(file_path) == {"ok": False}


def test_jsonl_loaders_skip_blank_lines_and_preserve_indexes() -> None:
    """JSONL parsers should ignore blank lines while indexed variants keep line numbers."""
    jsonl = '{"a":1}\n\n  \n{"b":2}\n'
    jsonl_bytes = jsonl.encode("utf-8")

    assert list(jsonl_loads(jsonl)) == [{"a": 1}, {"b": 2}]
    assert list(jsonl_loads_indexed(jsonl)) == [(1, {"a": 1}), (4, {"b": 2})]
    assert list(jsonl_load_bytes(jsonl_bytes)) == [{"a": 1}, {"b": 2}]
    assert list(jsonl_load_bytes_indexed(jsonl_bytes)) == [
        (1, {"a": 1}),
        (4, {"b": 2}),
    ]


def test_jsonl_path_loaders_and_dumpers(tmp_path: Path) -> None:
    """Path-based JSONL helpers should write and read one object per line."""
    file_path = tmp_path / "items.jsonl"

    chars_written = jsonl_dump_path(
        iter([{"i": 1}, {"i": 2}]),
        filepath=file_path,
    )

    text = file_path.read_text(encoding="utf-8")
    assert chars_written == len(text)
    assert list(jsonl_load_path(file_path)) == [{"i": 1}, {"i": 2}]
    assert list(jsonl_load_path_indexed(file_path)) == [
        (1, {"i": 1}),
        (2, {"i": 2}),
    ]

    jsonl_dump_path(iter([{"i": 3}]), filepath=file_path, append=True)
    assert list(jsonl_load_path(file_path)) == [{"i": 1}, {"i": 2}, {"i": 3}]


def test_jsonl_dump_path_overwrite_mode_replaces_existing_file(tmp_path: Path) -> None:
    """Overwrite mode should truncate existing file and write new JSONL content."""
    file_path = tmp_path / "overwrite.jsonl"
    file_path.write_text('{"old":1}\n', encoding="utf-8")

    jsonl_dump_path(iter([{"new": 2}]), filepath=file_path, overwrite=True)

    assert file_path.read_text(encoding="utf-8") == '{"new":2}\n'


def test_jsonl_path_loaders_skip_blank_lines(tmp_path: Path) -> None:
    """Path-based JSONL loaders should ignore blank lines and preserve indexes."""
    file_path = tmp_path / "with-blanks.jsonl"
    file_path.write_text('{"a":1}\n\n  \n{"b":2}\n', encoding="utf-8")

    assert list(jsonl_load_path(file_path)) == [{"a": 1}, {"b": 2}]
    assert list(jsonl_load_path_indexed(file_path)) == [
        (1, {"a": 1}),
        (4, {"b": 2}),
    ]


def test_jsonl_dump_variants_reject_indent() -> None:
    """JSONL serializers should reject indentation to preserve one-value-per-line."""
    with pytest.raises(ValueError, match="indent is not supported"):
        jsonl_dump_path(iter([{"a": 1}]), filepath=Path("ignored.jsonl"), indent=2)

    with pytest.raises(ValueError, match="indent is not supported"):
        jsonl_dumps(iter([{"a": 1}]), indent=2)

    with pytest.raises(ValueError, match="indent is not supported"):
        jsonl_dump_bytes(iter([{"a": 1}]), indent=2)


def test_jsonl_dump_path_rejects_overwrite_and_append_together(
    tmp_path: Path,
) -> None:
    """Mutually exclusive write modes should fail with a clear error."""
    file_path = tmp_path / "items.jsonl"

    with pytest.raises(ValueError, match="mutually exclusive"):
        jsonl_dump_path(
            iter([{"a": 1}]),
            filepath=file_path,
            overwrite=True,
            append=True,
        )


def test_jsonl_dumps_and_dump_bytes_emit_expected_content() -> None:
    """In-memory JSONL dumps should place one JSON object per line."""
    objects = [{"a": 1}, {"b": 2}]

    assert jsonl_dumps(iter(objects)) == '{"a":1}\n{"b":2}'
    assert jsonl_dump_bytes(iter(objects)) == b'{"a":1}\n{"b":2}'
