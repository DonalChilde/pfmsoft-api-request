"""Write text files while creating parent directories and enforcing overwrite policy."""

from pathlib import Path


def save_text_file(
    *,
    text: str,
    output_directory: Path,
    file_name: str,
    overwrite: bool = False,
    encoding: str = "utf-8",
) -> Path:
    """Write text to a file in the target output directory.

    Args:
        text: Text content to write.
        output_directory: Directory that should contain the output file.
        file_name: Name of the output file to create.
        overwrite: If true, replace an existing file. If false, raise an error
            when the target file already exists.
        encoding: Text encoding to use when writing the file.

    Returns:
        Path object for the written file.

    Raises:
        FileExistsError: If the target file exists and overwrite is false.
        OSError: If the parent directory cannot be created or the file cannot
            be written.

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
