"""Install and hash-verify canonical PIMM governance documents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:
    from .io_contract import atomic_copy_text, sha256_file
    from .paths import ASSET_ROOT, DOC_ROOT, require_within
else:
    from io_contract import atomic_copy_text, sha256_file
    from paths import ASSET_ROOT, DOC_ROOT, require_within


ROOT_DOCUMENTS = ("AGENTS.md", "README.md")


def canonical_workspace_docs(repo_root: Path) -> dict[Path, Path]:
    """Map canonical repository documents to their exact external paths."""

    document_root = repo_root / "docs" / "pimm-blender-governance"
    mapping = {
        document_root / name: ASSET_ROOT / name for name in ROOT_DOCUMENTS
    }
    mapping.update(
        {
            source: ASSET_ROOT / "docs" / source.name
            for source in sorted(document_root.glob("*.md"))
            if source.name not in ROOT_DOCUMENTS
        }
    )
    return mapping


def _destination_in_workspace(destination: Path, workspace_root: Path) -> Path:
    relative = destination.relative_to(ASSET_ROOT)
    return require_within(workspace_root / relative, workspace_root)


def install_workspace_docs(repo_root: Path, workspace_root: Path) -> list[dict[str, object]]:
    """Atomically install only approved canonical docs beneath *workspace_root*."""

    installed: list[dict[str, object]] = []
    for source, canonical_destination in canonical_workspace_docs(repo_root).items():
        if not source.is_file():
            raise FileNotFoundError(f"canonical document is missing: {source}")
        destination = _destination_in_workspace(canonical_destination, workspace_root)
        atomic_copy_text(source, destination)
        source_hash = sha256_file(source)
        destination_hash = sha256_file(destination)
        installed.append(
            {
                "source": str(source.resolve()),
                "destination": str(destination),
                "source_sha256": source_hash,
                "destination_sha256": destination_hash,
            }
        )
    return installed


def verify_workspace_docs(repo_root: Path, workspace_root: Path) -> list[str]:
    """Return missing/drift diagnostics; an empty result means hash parity."""

    errors: list[str] = []
    for source, canonical_destination in canonical_workspace_docs(repo_root).items():
        destination = _destination_in_workspace(canonical_destination, workspace_root)
        if not source.is_file():
            errors.append(f"{source.name} canonical source missing: {source}")
        elif not destination.is_file():
            errors.append(f"{source.name} missing: {destination}")
        elif sha256_file(source) != sha256_file(destination):
            errors.append(f"{source.name} SHA-256 drift")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="verify without writing")
    group.add_argument("--install", action="store_true", help="atomically install docs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = DOC_ROOT.parents[1]
    if args.install:
        for record in install_workspace_docs(repo_root, ASSET_ROOT):
            print(
                "PIMM_WORKSPACE_DOC "
                f"source={record['source']} destination={record['destination']} "
                f"source_sha256={record['source_sha256']} "
                f"destination_sha256={record['destination_sha256']}"
            )
        return 0

    errors = verify_workspace_docs(repo_root, ASSET_ROOT)
    if errors:
        for error in errors:
            print(f"PIMM_WORKSPACE_DOC_ERROR {error}", file=sys.stderr)
        return 1
    print("PIMM_WORKSPACE_DOC_CHECK parity=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
