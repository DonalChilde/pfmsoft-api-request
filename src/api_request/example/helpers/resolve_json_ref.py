"""Resolve internal json references."""

# pyright: standard
from typing import Any


def resolve_internal_refs(parent: dict[str, Any], child: Any) -> Any:
    """Recursively resolve internal JSON references ($ref) in a child object.

    Using the provided parent object as the reference root.

    Args:
        parent (Dict[str, Any]): The full parent JSON object.
        child (Any): The child subsection to resolve.

    Returns:
        Any: The child object with all internal references resolved.

    Example:
        >>> parent = {
        ...     "components": {
        ...         "schemas": {"A": {"type": "object"}, "B": {"$ref": "#/components/schemas/A"}}
        ...     }
        ... }
        >>> child = parent["components"]["schemas"]["B"]
        >>> resolve_internal_refs(parent, child)
        {'type': 'object'}
    """

    def _resolve(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_path = obj["$ref"]
                if not ref_path.startswith("#/"):
                    raise ValueError(f"Only internal refs supported, got: {ref_path}")
                # Split and traverse the parent object
                parts = ref_path.lstrip("#/").split("/")
                ref_obj = parent
                for part in parts:
                    ref_obj = ref_obj[part]
                # Recursively resolve the referenced object
                return _resolve(ref_obj)
            else:
                # Recursively resolve all dict values
                return {k: _resolve(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_resolve(item) for item in obj]
        else:
            return obj

    return _resolve(child)
