"""Small deterministic file-I/O primitives for production contracts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Mapping


def sha256_file(path: Path) -> str:
    """Return the uppercase SHA-256 digest of a file without loading it all."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    """Atomically replace *path* with deterministic, UTF-8 JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def atomic_copy_text(source: Path, destination: Path) -> None:
    """Atomically copy canonical UTF-8 bytes using a sibling temporary file."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(source.read_bytes())
    os.replace(temporary, destination)
