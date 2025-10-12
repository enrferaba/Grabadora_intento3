"""Application package initialization helpers."""
from __future__ import annotations

import importlib.util
import inspect
import sys
import sysconfig
from pathlib import Path
from typing import ForwardRef


def _ensure_stdlib_queue_module() -> None:
    """Force the standard library ``queue`` module to be importable.

    Algunos entornos Windows han dejado carpetas llamadas ``queue/`` en la raíz
    del proyecto (heredadas de otros repositorios o de tareas previas). Cuando
    eso sucede, el import resolver de Python antepone esa carpeta al módulo de
    la librería estándar y ``anyio`` termina lanzando ``ImportError`` al intentar
    cargar ``queue.Queue``. Este helper importa explícitamente la versión de la
    librería estándar y la registra en ``sys.modules`` si detecta que la que está
    disponible pertenece al proyecto.
    """

    module = sys.modules.get("queue")
    stdlib_path = sysconfig.get_path("stdlib")
    if not stdlib_path:
        return

    stdlib_queue = Path(stdlib_path) / "queue.py"
    if not stdlib_queue.exists():
        return

    if module is not None:
        module_file = getattr(module, "__file__", "")
        try:
            if module_file and Path(module_file).resolve().samefile(stdlib_queue):
                return
        except FileNotFoundError:
            pass
        # Si ``queue`` ya existe pero apunta al proyecto local, sobrescribimos.

    spec = importlib.util.spec_from_file_location("queue", stdlib_queue)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[arg-type]
        sys.modules["queue"] = module


def _patch_forward_ref_recursive_guard() -> None:
    """Ensure ForwardRef._evaluate handles Python 3.12 signature changes.

    Pydantic v1 sigue invocando ``ForwardRef._evaluate`` sin el argumento keyword
    ``recursive_guard`` introducido en Python 3.11+. Esta función añade un wrapper
    que proporciona un valor por defecto para mantener compatibilidad hacia atrás
    cuando esa firma extendida está presente.
    """

    original = ForwardRef._evaluate
    signature = inspect.signature(original)
    parameters = signature.parameters
    if "recursive_guard" not in parameters:
        return

    def _evaluate(*args, **kwargs):  # type: ignore[override]
        bound = signature.bind_partial(*args, **kwargs)

        recursive_guard = bound.arguments.get("recursive_guard")
        if recursive_guard is None:
            recursive_guard = set()
            bound.arguments["recursive_guard"] = recursive_guard

        return original(*bound.args, **bound.kwargs)

    ForwardRef._evaluate = _evaluate  # type: ignore[assignment]

_ensure_stdlib_queue_module()
_patch_forward_ref_recursive_guard()

