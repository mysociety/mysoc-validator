import sys
from typing import Any


def get_namespace_annotations(namespace: dict[str, Any]) -> dict[str, Any]:
    """Get class annotations from a namespace passed to a metaclass."""
    if "__annotations__" in namespace:
        return namespace["__annotations__"]

    if sys.version_info >= (3, 14):
        from annotationlib import (
            Format,
            call_annotate_function,
            get_annotate_from_class_namespace,
        )

        annotate = get_annotate_from_class_namespace(namespace)
        if annotate is not None:
            return call_annotate_function(annotate, Format.FORWARDREF)

    return {}
