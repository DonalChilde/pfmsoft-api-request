"""Helper functions for exporting data to csv files."""

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def write_dicts_to_csv(
    dicts: Iterable[dict[str, Any]], file_path: Path, overwrite: bool = False
) -> int:
    """Write an iterable of dictionaries to a csv file.

    If there are no dictionaries to write, an empty file will be created.

    Args:
        dicts: An iterable of dictionaries to write to the csv file. The keys of the dictionaries are used as the header of the csv file, and are gotten from the first dictionary in the iterable.
        file_path: The path to the csv file to write to.
        overwrite: Whether to overwrite the file if it already exists.

    Returns:
        The number of rows written to the csv file.
    """
    if file_path.exists() and not overwrite:
        raise FileExistsError(
            f"File {file_path} already exists and overwrite is set to False."
        )
    if file_path.is_dir():
        raise IsADirectoryError(f"File path {file_path} is a directory.")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    dicts = iter(dicts)
    row_count = 0
    try:
        first_dict = next(dicts)
    except StopIteration:
        # No dictionaries to write, create an empty file
        file_path.touch()
        return row_count

    fieldnames = list(first_dict.keys())
    with file_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(first_dict)
        row_count += 1
        for d in dicts:
            writer.writerow(d)
            row_count += 1
    return row_count
