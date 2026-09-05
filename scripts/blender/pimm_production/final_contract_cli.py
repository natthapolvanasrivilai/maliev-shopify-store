"""Create immutable native-final contracts without mutating approved render code."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping, Sequence

from .approval_manifest import (
    _canonical_component,
    _create_new_json,
    _lexically_within,
    _load_approval,
    _mapping,
    _reject_reparse_ancestors,
    canonical_absolute_path,
    validate_approval,
)
from .blender_final_render import _contract_errors, authorize_final_render


def _prepare_destination_parent(destination: Path) -> None:
    """Create the contract directory, then reject any reparse-point substitution."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    _reject_reparse_ancestors(destination.parent, "final contract destination")


def final_contract_payload(
    approval: Mapping[str, object], release_id: str, samples: int = 256
) -> dict[str, object]:
    """Build one exact native-final contract from an approved proof decision."""

    evidence = _mapping(approval.get("evidence"), "approval evidence")
    scene = _mapping(evidence.get("scene"), "approval scene evidence")
    roots = _mapping(approval.get("authority_roots"), "approval authority roots")
    payload: dict[str, object] = {
        "schema": "pimm-final-render-contract/v1",
        "release_id": release_id,
        "shot_id": approval.get("shot_id"),
        "generation_id": approval.get("proof_generation_id"),
        "authority_roots": approval.get("authority_roots"),
        "evidence": approval.get("evidence"),
        "inputs": approval.get("inputs"),
        "render_settings": approval.get("render_settings"),
        "samples": samples,
        "output_root": f"renders/final/{release_id}",
        "deliverables": ["exr", "png", "webp"],
        "asset_root": roots.get("asset"),
        "scene_path": scene.get("path"),
    }
    errors = _contract_errors(approval, payload)
    if errors:
        raise ValueError("invalid generated final contract: " + "; ".join(errors))
    return payload


def create_final_contract(
    approval_path: Path, release_id: str, samples: int = 256
) -> Path:
    """Validate an approval and immutably publish its native-final contract."""

    approval_path = canonical_absolute_path(str(approval_path), "approval path")
    approval, roots = _load_approval(approval_path)
    errors = validate_approval(approval_path, {})
    if errors:
        raise ValueError("approval is not current: " + "; ".join(errors))
    payload = final_contract_payload(approval, release_id, samples)
    shot_id = _canonical_component(str(approval.get("shot_id")), "shot_id")
    destination = (
        roots["asset"]
        / "renders"
        / "final-contracts"
        / release_id
        / f"{shot_id}--contract-r01.json"
    )
    _lexically_within(destination, roots["asset"], "final contract destination")
    _prepare_destination_parent(destination)
    _create_new_json(destination, payload)
    authorize_final_render(approval_path, destination)
    return destination


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--samples", type=int, default=256)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    print(
        create_final_contract(
            arguments.approval, arguments.release_id, arguments.samples
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
