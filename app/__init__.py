"""Application package initialization helpers."""
from __future__ import annotations

import inspect
from typing import ForwardRef


def _patch_forward_ref_recursive_guard() -> None:
    """Ensure ForwardRef._evaluate handles Python 3.12 signature changes.

    Pydantic v1 sigue invocando ``ForwardRef._evaluate`` sin el argumento keyword
    ``recursive_guard`` introducido en Python 3.11+. Esta función añade un wrapper
    que proporciona un valor por defecto para mantener compatibilidad hacia atrás
    cuando esa firma extendida está presente.
    """

    signature = inspect.signature(ForwardRef._evaluate)
    parameters = signature.parameters
    if "recursive_guard" not in parameters:
        return

    original = ForwardRef._evaluate

    def _evaluate(
        self,  # type: ignore[override]
        globalns,
        localns,
        type_params=None,
        *,
        recursive_guard=None,
    ):
        if recursive_guard is None:
            recursive_guard = set()
        return original(self, globalns, localns, type_params, recursive_guard=recursive_guard)

    ForwardRef._evaluate = _evaluate  # type: ignore[assignment]


_patch_forward_ref_recursive_guard()

