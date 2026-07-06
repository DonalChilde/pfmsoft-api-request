"""Write text files with explicit overwrite semantics."""

from pathlib import Path


def save_text_file(
    *,
    text: str,
    output_directory: Path,
    file_name: str,
    overwrite: bool = False,
    encoding: str = "utf-8",
) -> Path:
    """Write text to ``output_directory / file_name``.

    Args:
        text: Text content to write.
        output_directory: Directory to write the file into.
        file_name: Output file name.
        overwrite: If true, replace existing file contents. If false, fail when
            the file already exists.
        encoding: File encoding to use.

    Returns:
        Path to the written file.

    Raises:
        FileExistsError: If the target file exists and ``overwrite`` is false.

    Notes:
        Parent directories are created automatically when missing.
    """
    output_file = output_directory / file_name
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if overwrite:
        mode = "w"
    else:
        mode = "x"
    with output_file.open(mode, encoding=encoding) as f:
        f.write(text)
    return output_file
