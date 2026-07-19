"""Helpers for loading, dumping, and streaming JSON and JSONL data with pydantic_core."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, TextIO

from pydantic_core import from_json, to_json


def json_load_path(filepath: Path) -> Any:
    """Load a JSON file into a Python object.

    Args:
        filepath: Path to a UTF-8 encoded JSON file.

    Returns:
        Parsed Python object produced by pydantic_core.from_json().
    """
    return from_json(filepath.read_text(encoding="utf-8"))


def json_loads(json_string: str | bytes) -> Any:
    """Parse a JSON text or byte payload into a Python object.

    Args:
        json_string: JSON document encoded as text or bytes.

    Returns:
        Parsed Python object produced by pydantic_core.from_json().
    """
    return from_json(json_string)


def json_dumps(
    obj: Any, indent: int | None = None, encoding: str = "utf-8", **kwargs: Any
) -> str:
    """Serialize a Python object to JSON text.

    Args:
        obj: Python object to serialize.
        indent: Optional indentation level passed to pydantic_core.to_json().
        encoding: Text encoding used to decode the serialized JSON bytes.
        **kwargs: Additional keyword arguments forwarded to
            pydantic_core.to_json().

    Returns:
        JSON document as a string.
    """
    return to_json(obj, indent=indent, **kwargs).decode(encoding)


def json_dump_bytes(obj: Any, indent: int | None = None, **kwargs: Any) -> bytes:
    """Serialize a Python object to JSON bytes.

    Args:
        obj: Python object to serialize.
        indent: Optional indentation level passed to pydantic_core.to_json().
        **kwargs: Additional keyword arguments forwarded to
            pydantic_core.to_json().

    Returns:
        JSON document as bytes.
    """
    return to_json(obj, indent=indent, **kwargs)


def json_dumps_path(
    obj: Any,
    *,
    filepath: Path,
    overwrite: bool = False,
    encoding: str = "utf-8",
    indent: int | None = None,
    **kwargs: Any,
) -> int:
    """Dump a Python object to a JSON file.

    Uses pydantic_core.to_json() to serialize the object and writes a trailing
    newline after the JSON document.

    Args:
        obj: The Python object to dump.
        filepath: The path to the JSON file.
        overwrite: Whether to overwrite the file if it exists.
        encoding: The encoding to use when writing the file.
        indent: The indentation level for the JSON file.
        **kwargs: Additional keyword arguments passed to `json_dumps`.

    Returns:
        The number of characters written to the file, including the trailing
        newline.

    Raises:
        FileExistsError: If the file already exists and `overwrite` is False.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    if overwrite:
        mode = "w"
    else:
        mode = "x"
    with filepath.open(mode, encoding=encoding) as f:
        counter = 0
        counter += f.write(json_dumps(obj, indent=indent, **kwargs))
        counter += f.write("\n")
        return counter


def jsonl_loads(jsonl_string: str) -> Iterator[Any]:
    """Yield Python objects parsed lazily from non-empty JSONL text lines."""
    for line in jsonl_string.splitlines():
        if line.strip():
            yield from_json(line)


def jsonl_loads_indexed(jsonl_string: str) -> Iterator[tuple[int, Any]]:
    """Yield line-number and object pairs from non-empty JSONL text lines.

    Line numbers correspond to the original input line positions, including
    blank lines.
    """
    for line_number, line in enumerate(jsonl_string.splitlines(), start=1):
        if line.strip():
            yield line_number, from_json(line)


def jsonl_load_bytes(jsonl_bytes: bytes) -> Iterator[Any]:
    """Yield Python objects parsed lazily from non-empty JSONL byte lines."""
    for line in jsonl_bytes.splitlines():
        if line.strip():
            yield from_json(line)


def jsonl_load_bytes_indexed(jsonl_bytes: bytes) -> Iterator[tuple[int, Any]]:
    """Yield line-number and object pairs from non-empty JSONL byte lines.

    Line numbers correspond to the original input line positions, including
    blank lines.
    """
    for line_number, line in enumerate(jsonl_bytes.splitlines(), start=1):
        if line.strip():
            yield line_number, from_json(line)


def jsonl_load_path(filepath: Path) -> Iterator[Any]:
    """Yield Python objects parsed lazily from non-empty lines in a JSONL file."""
    with filepath.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield from_json(line)


def jsonl_load_path_indexed(filepath: Path) -> Iterator[tuple[int, Any]]:
    """Yield line-number and object pairs parsed from a JSONL file.

    Line numbers correspond to the original file line positions, including
    blank lines.
    """
    with filepath.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if line.strip():
                yield line_number, from_json(line)


def jsonl_dump_path(
    objs: Iterator[Any],
    *,
    filepath: Path,
    encoding: str = "utf-8",
    overwrite: bool = False,
    append: bool = False,
    **kwargs: Any,
) -> int:
    """Write JSONL output from an iterator of Python objects.

    Serializes one object per line without materializing the full output in
    memory.

    Args:
        objs: Iterator of Python objects to serialize as JSONL.
        filepath: The path to the JSONL file.
        encoding: The encoding to use when writing the file.
        overwrite: Whether to overwrite the file if it exists.
        append: Whether to append to the file if it exists.
        **kwargs: Additional keyword arguments passed to `json_dumps`.

    Returns:
        Number of characters written to the file, including newline
        separators.

    Raises:
        ValueError: If `indent` is provided or if `overwrite` and `append` are
            both True.
        FileExistsError: If the file already exists and neither overwrite nor
            append permits writing.
    """
    if "indent" in kwargs:
        raise ValueError("indent is not supported for JSONL files.")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and append:
        raise ValueError("overwrite and append are mutually exclusive.")
    if append:
        mode = "a"
    elif overwrite:
        mode = "w"
    else:
        mode = "x"

    def write_objs(f: TextIO) -> int:
        counter = 0
        for obj in objs:
            counter += f.write(json_dumps(obj, **kwargs))
            counter += f.write("\n")
        return counter

    with filepath.open(mode, encoding=encoding) as f:
        return write_objs(f)


def jsonl_dumps(objs: Iterator[Any], encoding: str = "utf-8", **kwargs: Any) -> str:
    """Serialize an iterator of objects to a JSONL string.

    Args:
        objs: Iterator of Python objects to serialize as JSONL.
        encoding: Text encoding used when converting each JSON document.
        **kwargs: Additional keyword arguments forwarded to json_dumps().

    Returns:
        JSONL document with one serialized object per line.

    Raises:
        ValueError: If `indent` is provided, because JSONL output must remain
            one JSON value per line.
    """
    if "indent" in kwargs:
        raise ValueError("indent is not supported for JSONL files.")
    return "\n".join(json_dumps(obj, encoding=encoding, **kwargs) for obj in objs)


def jsonl_dump_bytes(objs: Iterator[Any], **kwargs: Any) -> bytes:
    """Serialize an iterator of objects to JSONL bytes.

    Args:
        objs: Iterator of Python objects to serialize as JSONL.
        **kwargs: Additional keyword arguments forwarded to json_dump_bytes().

    Returns:
        JSONL document as bytes with one serialized object per line.

    Raises:
        ValueError: If `indent` is provided, because JSONL output must remain
            one JSON value per line.
    """
    if "indent" in kwargs:
        raise ValueError("indent is not supported for JSONL files.")
    jsonl_bytes = b"\n".join(json_dump_bytes(obj, **kwargs) for obj in objs)
    return jsonl_bytes
