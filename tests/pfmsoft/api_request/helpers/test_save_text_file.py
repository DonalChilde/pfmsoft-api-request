"""Tests for save_text_file helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from pfmsoft.api_request.helpers.save_text_file import save_text_file


def test_save_text_file_creates_parent_and_writes_content(tmp_path: Path) -> None:
    """Helper should create missing parent directories and write provided text."""
    output_directory = tmp_path / "nested" / "output"

    output_path = save_text_file(
        text="hello",
        output_directory=output_directory,
        file_name="result.txt",
    )

    assert output_path == output_directory / "result.txt"
    assert output_path.read_text(encoding="utf-8") == "hello"


def test_save_text_file_respects_overwrite_policy(tmp_path: Path) -> None:
    """Helper should fail on existing files unless overwrite is enabled."""
    output_directory = tmp_path / "output"
    save_text_file(text="v1", output_directory=output_directory, file_name="result.txt")

    with pytest.raises(FileExistsError):
        save_text_file(
            text="v2", output_directory=output_directory, file_name="result.txt"
        )

    save_text_file(
        text="v2",
        output_directory=output_directory,
        file_name="result.txt",
        overwrite=True,
    )
    assert (output_directory / "result.txt").read_text(encoding="utf-8") == "v2"


def test_save_text_file_uses_requested_encoding(tmp_path: Path) -> None:
    """Helper should pass through explicit text encoding parameter."""
    output_path = save_text_file(
        text="cafe",
        output_directory=tmp_path,
        file_name="encoded.txt",
        encoding="utf-8",
    )

    assert output_path.read_text(encoding="utf-8") == "cafe"
