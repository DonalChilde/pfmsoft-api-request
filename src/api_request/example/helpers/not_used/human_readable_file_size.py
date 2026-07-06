"""Helpers for converting file sizes to human-readable formats."""

from pathlib import Path


def file_size(file_path: Path, decimal_places: int = 2) -> str:
    """Get the size of a file in a human-readable string format.

    Args:
        file_path (Path): The path to the file.
        decimal_places (int): The number of decimal places to include in the output.

    Returns:
        str: A human-readable string representation of the file size.
    """
    if not file_path.is_file():
        raise ValueError(f"The path {file_path} is not a valid file.")

    size = file_path.stat().st_size
    return human_readable_file_size(size, decimal_places)


def human_readable_file_size(size: int, decimal_places: int = 2) -> str:
    """Convert a file size in bytes to a human-readable string format.

    Args:
        size (int): The file size in bytes.
        decimal_places (int): The number of decimal places to include in the output.

    Returns:
        str: A human-readable string representation of the file size.
    """
    if size < 0:
        raise ValueError("Size must be a non-negative integer")
    size_float = float(size)

    units = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    index = 0

    while size_float >= 1024 and index < len(units) - 1:
        size_float /= 1024.0
        index += 1

    return f"{size_float:.{decimal_places}f} {units[index]}"
