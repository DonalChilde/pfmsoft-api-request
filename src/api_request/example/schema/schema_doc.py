"""Generate human readable schema documentation.

Generates a human readable markdown document from an ESI schema, grouping operations by
tag and including relevant information about each operation such as its path, method,
description, parameters, request body, and response schema. The generated documentation
is intended to be easily readable and navigable for developers working with the ESI schema.

If your editor supports navigation by header, you can use the generated documentation to
quickly jump to the section for a specific tag or operation.
"""

import json
from pathlib import Path
from typing import Any, TypedDict

from whenever import Instant
from yaml import safe_dump

from esi_link.schema.models import EsiSchema, SchemaOperation


class OperationDoc(TypedDict):
    operation_id: str
    path: str
    method: str
    description: str
    authorization_required: bool
    tags: list[str]
    path_and_query_parameters: list[dict[str, Any]]
    request_body: dict[str, Any]
    response_schema: dict[str, Any]
    summary: str | None
    x_values: list[dict[str, Any]]


def doc_dict_from_operation(operation: SchemaOperation) -> OperationDoc:
    """Convert a SchemaOperation to an OperationDoc dictionary.

    Args:
        operation: The SchemaOperation to convert.

    Returns:
        An OperationDoc dictionary containing the relevant information from the SchemaOperation.
    """
    return OperationDoc(
        operation_id=operation.operation_id,
        path=operation.path,
        method=operation.method,
        description=operation.description.replace("\n", " "),
        authorization_required=operation.is_authentication_required,
        tags=operation.tags or [],
        path_and_query_parameters=operation.path_and_query_parameters,
        request_body=operation.request_body or {},
        response_schema=operation.responses,
        summary=operation.summary,
        x_values=operation.x_values,
    )


def doc_dict_by_tag(
    operations: dict[str, SchemaOperation],
) -> dict[str, list[OperationDoc]]:
    """Group SchemaOperations by tag and convert them to OperationDoc dictionaries.

    Args:
        operations: A dictionary mapping operation IDs to SchemaOperations.

    Returns:
        A dictionary mapping tags to lists of OperationDoc dictionaries.
    """
    doc_by_tag: dict[str, list[OperationDoc]] = {}
    for operation in operations.values():
        for tag in operation.tags or []:
            if tag not in doc_by_tag:
                doc_by_tag[tag] = []
            doc_by_tag[tag].append(doc_dict_from_operation(operation))
    # sort by tag and then by operation_id
    doc_by_tag = {
        tag: sorted(operation_ids, key=lambda x: x["operation_id"])
        for tag, operation_ids in sorted(doc_by_tag.items())
    }
    return doc_by_tag


def generate_operation_doc(operation: SchemaOperation) -> str:
    """Generate human readable documentation for an ESI schema operation.

    Args:
        operation: The ESI schema operation to generate documentation for.

    Returns:
        A string containing the generated documentation.
    """
    return safe_dump(doc_dict_from_operation(operation), sort_keys=False, indent=2)


def generate_esi_schema_doc(schema: EsiSchema, download_date: Instant | None) -> str:
    """Generate human readable documentation for an ESI schema.

    Generates ESI Schema documentation in markdown format, grouping operations by tag.


    Args:
        schema: The ESI schema to generate documentation for.
        download_date: The date the schema was downloaded, if available.

    Returns:
        A string containing the generated documentation.
    """
    operations = schema.operations
    operation_id_by_tag = doc_dict_by_tag(operations)
    doc = f"""\n# ESI Schema Documentation

Version
: {schema.version}  
Download Date
: {download_date.format_iso() if download_date else "Unknown"}  

## Operations  


"""
    tag_string: list[str] = []
    for tag, operation_docs in operation_id_by_tag.items():
        tag_string.append("\n")
        tag_string.append(f"### {tag}  ")
        tag_string.append(f"\n")
        for operation_doc in operation_docs:
            tag_string.append("\n")
            tag_string.append(f"#### {operation_doc['operation_id']}  ")
            tag_string.append("\n")
            tag_string.append(f"```yaml")
            tag_string.append(safe_dump(operation_doc, sort_keys=False, indent=2))
            tag_string.append("```")
    doc += "\n".join(tag_string)
    return doc


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate human readable schema documentation."
    )
    parser.add_argument(
        "schema_file",
        type=Path,
        help="The path to the raw schema file to generate documentation for.",
    )
    parser.add_argument(
        "output_directory",
        type=Path,
        help="The path to the output directory to write the generated documentation to.",
    )
    parser.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        help="Whether to overwrite existing files.",
    )
    args = parser.parse_args()
    with open(args.schema_file) as f:
        schema = json.load(f)
    esi_schema = EsiSchema.from_raw_schema(schema)
    doc = generate_esi_schema_doc(esi_schema, download_date=Instant.now())
    output_file = args.output_directory / "schema_doc.md"
    if output_file.exists() and not args.overwrite:
        print(
            f"Output file {output_file} already exists and overwrite is not enabled. Skipping generation."
        )
        raise FileExistsError(
            f"Output file {output_file} already exists and overwrite is not enabled."
        )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        f.write(doc)
    print(f"Generated schema documentation written to {output_file}")
