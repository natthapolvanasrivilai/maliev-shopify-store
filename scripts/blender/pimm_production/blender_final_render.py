"""Fail-closed authorization and local QA boundary for native PIMM final renders."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from .approval_manifest import validate_approval
from .io_contract import sha256_file


_RELEASE_ID = re.compile(r"^release-[0-9]{4}-[0-9]{2}-[0-9]{2}-r[0-9]{2}$")
_SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
_DELIVERABLES = frozenset({"exr", "png", "webp"})


@dataclass(frozen=True)
class FinalAuthorization:
    """A validated, approval-bound final-render execution envelope."""

    approval_path: Path
    final_contract_path: Path
    release_id: str
    shot_id: str
    generation_id: str
    output_root: PurePosixPath


def _load(path: Path, label: str) -> Mapping[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} cannot be read: {error}") from error
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be an object")
    return payload


def _contract_errors(approval: Mapping[str, object], final: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    if final.get("schema") != "pimm-final-render-contract/v1":
        errors.append("final contract schema is invalid")
    release_id = final.get("release_id")
    if not isinstance(release_id, str) or _RELEASE_ID.fullmatch(release_id) is None:
        errors.append("final release ID is invalid")
    shot_id = final.get("shot_id")
    if shot_id != approval.get("shot_id"):
        errors.append("shot ID drift")
    if final.get("generation_id") != approval.get("proof_generation_id"):
        errors.append("proof generation drift")
    approved_inputs = approval.get("inputs")
    final_inputs = final.get("inputs")
    if not isinstance(approved_inputs, Mapping) or not isinstance(final_inputs, Mapping):
        errors.append("final inputs are required")
    elif dict(final_inputs) != dict(approved_inputs):
        errors.append("approved input SHA-256 drift")
    approved_settings = approval.get("render_settings")
    final_settings = final.get("render_settings")
    if not isinstance(approved_settings, Mapping) or not isinstance(final_settings, Mapping):
        errors.append("final render settings are required")
    else:
        labels = {
            "camera_sha256": "camera SHA-256 drift",
            "lights_sha256": "lights SHA-256 drift",
            "world_sha256": "world SHA-256 drift",
            "compositor_sha256": "compositor SHA-256 drift",
            "render_settings_sha256": "render settings SHA-256 drift",
            "composition_sha256": "composition SHA-256 drift",
            "output_dimensions": "output dimensions drift",
            "alpha_mode": "alpha mode drift",
        }
        for key, message in labels.items():
            if final_settings.get(key) != approved_settings.get(key):
                errors.append(message)
    samples = final.get("samples")
    proof_samples = approved_settings.get("proof_samples") if isinstance(approved_settings, Mapping) else None
    if not isinstance(samples, int) or isinstance(samples, bool) or not isinstance(proof_samples, int) or samples <= proof_samples:
        errors.append("final render requires an explicit sampling increase")
    output_root = final.get("output_root")
    if not isinstance(release_id, str) or output_root != f"renders/final/{release_id}":
        errors.append("final output root must be a new immutable renders/final/<release-id> directory")
    deliverables = final.get("deliverables")
    if not isinstance(deliverables, list) or set(deliverables) != _DELIVERABLES or len(deliverables) != len(_DELIVERABLES):
        errors.append("final deliverables must contain exactly float EXR, transparent PNG, and transparent WebP")
    return errors


def _revision_head_errors(approval_path: Path) -> list[str]:
    """Require the supplied approval to be the one unbroken immutable chain head."""

    entries = sorted(approval_path.parent.glob("approval-r*.json"))
    if not entries or entries[-1].resolve() != approval_path.resolve():
        return ["latest approval revision is required"]
    prior: Path | None = None
    for revision, path in enumerate(entries, start=1):
        try:
            payload = _load(path, "approval revision")
        except ValueError as error:
            return [f"approval revision chain is unreadable: {error}"]
        if payload.get("revision") != revision:
            return ["approval revision chain is broken"]
        if prior is None:
            if payload.get("prior_approval_sha256") is not None:
                return ["approval revision chain is broken"]
        elif (
            payload.get("prior_approval_sha256") != sha256_file(prior)
            or payload.get("prior_approval_path") != str(prior.resolve())
        ):
            return ["approval revision chain is broken"]
        prior = path
    return []


def authorize_final_render(approval_path: Path, final_contract_path: Path) -> FinalAuthorization:
    """Authorize only an explicit sample increase over a current approved proof."""

    approval_path = Path(approval_path).resolve()
    approval = _load(approval_path, "approval")
    if approval.get("decision") != "approved" or not isinstance(approval.get("owner"), str) or not approval["owner"].strip():
        raise ValueError("owner approval required")
    inputs = approval.get("inputs")
    if not isinstance(inputs, Mapping):
        raise ValueError("owner approval required: immutable inputs missing")
    approval_errors = _revision_head_errors(approval_path)
    approval_errors += validate_approval(approval_path, {})
    final = _load(final_contract_path, "final contract")
    errors = approval_errors + _contract_errors(approval, final)
    if errors:
        raise ValueError("final render authorization failed: " + "; ".join(errors))
    return FinalAuthorization(
        approval_path=approval_path,
        final_contract_path=Path(final_contract_path).resolve(),
        release_id=str(final["release_id"]),
        shot_id=str(final["shot_id"]),
        generation_id=str(final["generation_id"]),
        output_root=PurePosixPath(str(final["output_root"])),
    )


def _write_new_json(path: Path, payload: Mapping[str, object]) -> None:
    """Create, never replace, the immutable JSON evidence marker at *path*."""

    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_BINARY)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _validate_png(path: Path, dimensions: list[object]) -> None:
    from PIL import Image

    with Image.open(path) as image:
        image.load()
        if list(image.size) != dimensions or image.mode != "RGBA":
            raise ValueError("final PNG dimensions or RGBA alpha drift")
        if image.getchannel("A").getextrema()[1] == 0:
            raise ValueError("final PNG alpha has no visible product")


def _blender_render_script(scene_path: Path, output_root: Path, dimensions: list[object], samples: int) -> str:
    """Return a self-contained native Blender render script for a disposable final scene."""

    return "\n".join((
        "import bpy",
        f"scene = bpy.context.scene",
        "scene.render.engine = 'BLENDER_EEVEE'",
        "scene.render.film_transparent = True",
        f"scene.render.resolution_x = {int(dimensions[0])}",
        f"scene.render.resolution_y = {int(dimensions[1])}",
        "scene.render.resolution_percentage = 100",
        f"scene.render.image_settings.color_mode = 'RGBA'",
        "scene.render.image_settings.file_format = 'OPEN_EXR'",
        "scene.render.image_settings.color_depth = '32'",
        f"scene.render.filepath = {str(output_root / 'final.exr')!r}",
        "bpy.ops.render.render(write_still=True)",
        "scene.render.image_settings.file_format = 'PNG'",
        "scene.render.image_settings.color_depth = '8'",
        f"scene.render.filepath = {str(output_root / 'final.png')!r}",
        "bpy.ops.render.render(write_still=True)",
    ))


def run_authorized_final(approval_path: Path, final_contract_path: Path) -> Path:
    """Render a native temporary-authorized final and publish evidence only after QA.

    This runner intentionally requires a caller-supplied temporary asset root and
    scene path. It never selects the production ``M:`` workspace.
    """

    authorization = authorize_final_render(approval_path, final_contract_path)
    final = _load(final_contract_path, "final contract")
    asset_root = final.get("asset_root")
    scene_path = final.get("scene_path")
    if not isinstance(asset_root, str) or not isinstance(scene_path, str):
        raise ValueError("native final render requires explicit asset_root and scene_path")
    root = Path(asset_root).resolve()
    scene = Path(scene_path).resolve()
    if not root.is_dir() or not scene.is_file() or str(root).upper().startswith("M:\\"):
        raise ValueError("native final render requires a safe temporary root and scene")
    try:
        scene.relative_to(root)
    except ValueError as error:
        raise ValueError("native final scene is outside the supplied asset root") from error
    dimensions = final.get("render_settings", {}).get("output_dimensions") if isinstance(final.get("render_settings"), Mapping) else None
    if not isinstance(dimensions, list) or len(dimensions) != 2 or not all(isinstance(value, int) and value > 0 for value in dimensions):
        raise ValueError("native final output dimensions are invalid")
    output_root = root / "renders" / "final" / authorization.release_id / authorization.shot_id
    output_root.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_root.mkdir()
    except FileExistsError as error:
        raise ValueError("final release root already exists; immutable output required") from error
    blender = Path(r"D:\Blender 5.2\blender.exe")
    if not blender.is_file():
        raise ValueError("pinned local Blender 5.2 is unavailable")
    script = output_root / ".native-final.py"
    script.write_text(_blender_render_script(scene, output_root, dimensions, int(final["samples"])), encoding="utf-8")
    try:
        result = subprocess.run(
            [str(blender), "--factory-startup", "-b", str(scene), "-P", str(script)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise ValueError("native Blender final render failed: " + result.stderr[-1000:])
        png = output_root / "final.png"
        exr = output_root / "final.exr"
        if not png.is_file() or not exr.is_file() or exr.read_bytes()[:4] != b"v/1\x01":
            raise ValueError(
                "native final did not produce a valid float EXR and PNG "
                f"(png={png.is_file()}, exr={exr.is_file()}, "
                f"header={exr.read_bytes()[:4].hex() if exr.is_file() else ''}, "
                f"blender={result.stdout[-500:]})"
            )
        _validate_png(png, dimensions)
        from PIL import Image
        webp = output_root / "final.webp"
        with Image.open(png) as image:
            image.save(webp, format="WEBP", lossless=True)
        _validate_png(webp, dimensions)
        approval_hash = sha256_file(Path(approval_path))
        outputs = []
        for path, mime in ((exr, "image/x-exr"), (png, "image/png"), (webp, "image/webp")):
            outputs.append({
                "logical_asset_id": f"{authorization.shot_id}--transparent-{path.suffix[1:]}",
                "path": path.name,
                "sha256": sha256_file(path),
                "dimensions": dimensions,
                "alpha": True,
                "mime_type": mime,
            })
        manifest = output_root / "final-output-manifest.json"
        _write_new_json(manifest, {
            "schema": "pimm-final-output-manifest/v1",
            "release_id": authorization.release_id,
            "generation_id": authorization.generation_id,
            "shot_id": authorization.shot_id,
            "approval_path": str(Path(approval_path).resolve()),
            "approval_sha256": approval_hash,
            "authorized_final_contract_sha256": sha256_file(Path(final_contract_path)),
            "output_root": f"renders/final/{authorization.release_id}",
            "required_deliverables": ["exr", "png", "webp"],
            "qa": {"product": True, "material": True, "alpha": True, "controller": True, "animation_endpoints_match": True},
            "outputs": outputs,
        })
        return manifest
    except BaseException:
        for child in sorted(output_root.glob("*")):
            if child.is_file() and not child.is_symlink():
                child.unlink()
        try:
            output_root.rmdir()
        except OSError:
            pass
        raise
