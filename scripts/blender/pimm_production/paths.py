"""Canonical PIMM production paths and safe child-path validation."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ASSET_ROOT = Path(r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders")
ARCHIVE_ROOT = Path(
    r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-archive\pending-delete"
)
DOC_ROOT = REPO_ROOT / "docs" / "pimm-blender-governance"

_UNRESOLVED_VARIABLE = re.compile(r"(?:%[^%]+%|\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*)")


def require_within(path: Path, root: Path) -> Path:
    """Return a resolved strict descendant of *root* or raise ``ValueError``."""

    raw_path = str(path)
    raw_root = str(root)
    if _UNRESOLVED_VARIABLE.search(raw_path) or _UNRESOLVED_VARIABLE.search(raw_root):
        raise ValueError("unresolved environment variable in path")

    resolved = Path(path).resolve()
    resolved_root = Path(root).resolve()
    if resolved == Path(resolved.anchor):
        raise ValueError(f"drive root is not an allowed destination: {resolved}")
    if resolved == resolved_root:
        raise ValueError(f"root itself is not an allowed destination: {resolved}")
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(
            f"destination is outside expected root: {resolved} not within {resolved_root}"
        ) from error
    return resolved
