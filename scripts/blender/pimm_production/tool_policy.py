"""Discover and lock the approved local PIMM production tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import subprocess
import sys
from typing import Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.blender.pimm_production.io_contract import atomic_write_json, sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within


BLENDER_EXECUTABLE = Path(r"D:\Blender 5.2\blender.exe")
BLENDER_MCP_ROOT = Path(r"C:\Users\natth\blender_mcp")
PRODUCTION_VENV_ROOT = ASSET_ROOT / "tools" / "pimm-render-py311"
LOCK_PATH = ASSET_ROOT / "manifests" / "free-tools-lock.json"
LOCK_SCHEMA = "pimm-free-tools-lock/v1"
REQUIRED_TOOL_IDS = frozenset({"blender", "blender-mcp", "python", "pillow"})
TOOL_LICENSES = {
    "blender": "GPL-3.0-or-later",
    "blender-mcp": "GPL-3.0-or-later",
    "python": "PSF-2.0",
    "pillow": "MIT-CMU",
}
LOCK_FIELDS = frozenset({"schema", "tools", "license_evidence", "asset_provenance"})
TOOL_FIELDS = frozenset({"id", "version", "license", "execution", "path", "sha256"})
LICENSE_EVIDENCE_FIELDS = frozenset({"path", "sha256"})
ASSET_PROVENANCE_FIELDS = frozenset({"path", "sha256", "license"})
PINNED_HDRI_RELATIVE_PATH = "assets/hdri/studio_kontrast_04_4k.exr"
PINNED_HDRI_SHA256 = "9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06"
NETWORK_FIELD_TOKENS = ("endpoint", "url", "uri", "remote", "network", "host", "port")
SHA256_PATTERN = re.compile(r"^[A-Fa-f0-9]{64}$")
TOOL_ROOTS = {
    "blender": BLENDER_EXECUTABLE.parent,
    "blender-mcp": BLENDER_MCP_ROOT,
    "python": PRODUCTION_VENV_ROOT,
    "pillow": PRODUCTION_VENV_ROOT,
}


@dataclass(frozen=True)
class ToolRecord:
    """An auditable, locally executable production dependency."""

    id: str
    version: str
    license: str
    path: str
    sha256: str | None


def _run_text(arguments: list[str], *, cwd: Path | None = None) -> str:
    return subprocess.run(
        arguments,
        cwd=cwd,
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    ).stdout.strip()


def _first_blender_mcp_license_evidence() -> Path:
    """Find a project license file, falling back to the add-on SPDX manifest."""

    candidates = sorted(
        path
        for path in BLENDER_MCP_ROOT.rglob("LICENSE*")
        if ".venv" not in path.parts and "site-packages" not in path.parts
    )
    if candidates:
        return candidates[0]
    return BLENDER_MCP_ROOT / "addon" / "blender_mcp_addon" / "blender_manifest.toml"


def _blender_version() -> str:
    match = re.search(r"^Blender\s+([^\s]+)", _run_text([str(BLENDER_EXECUTABLE), "--version"]))
    if not match:
        raise ValueError("could not parse Blender version")
    return match.group(1)


def _venv_python() -> Path:
    python_name = "python.exe" if sys.platform == "win32" else "python"
    return PRODUCTION_VENV_ROOT / "Scripts" / python_name


def discover_free_tools() -> list[ToolRecord]:
    """Return current immutable evidence for every approved local tool."""

    venv_python = _venv_python()
    python_version = _run_text([str(venv_python), "--version"]).removeprefix("Python ")
    pillow_version = _run_text(
        [str(venv_python), "-c", "from importlib.metadata import version; print(version('Pillow'))"]
    )
    pillow_license = _run_text(
        [
            str(venv_python),
            "-c",
            "from importlib.metadata import metadata; print(metadata('Pillow')['License-Expression'])",
        ]
    )
    pillow_path = Path(
        _run_text(
            [str(venv_python), "-c", "import PIL; print(PIL.__file__)"],
        )
    )
    mcp_license_path = _first_blender_mcp_license_evidence()

    return [
        ToolRecord(
            id="blender",
            version=_blender_version(),
            license="GPL-3.0-or-later",
            path=str(BLENDER_EXECUTABLE),
            sha256=sha256_file(BLENDER_EXECUTABLE),
        ),
        ToolRecord(
            id="blender-mcp",
            version=_run_text(["git", "rev-parse", "HEAD"], cwd=BLENDER_MCP_ROOT),
            license="GPL-3.0-or-later",
            path=str(BLENDER_MCP_ROOT),
            sha256=sha256_file(mcp_license_path),
        ),
        ToolRecord(
            id="python",
            version=python_version,
            license="PSF-2.0",
            path=str(venv_python),
            sha256=sha256_file(venv_python),
        ),
        ToolRecord(
            id="pillow",
            version=pillow_version,
            license=pillow_license,
            path=str(pillow_path),
            sha256=sha256_file(pillow_path),
        ),
    ]


def _network_field_errors(value: object, location: str = "lock") -> list[str]:
    """Reject URL, endpoint, and other network-bearing lock fields recursively."""

    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_location = f"{location}.{key_text}"
            if any(token in key_text.lower() for token in NETWORK_FIELD_TOKENS):
                errors.append(f"network-bearing field is prohibited: {child_location}")
            errors.extend(_network_field_errors(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_network_field_errors(child, f"{location}[{index}]"))
    elif isinstance(value, str) and re.search(r"(?:https?|wss?)://", value, re.IGNORECASE):
        errors.append(f"network-bearing value is prohibited: {location}")
    return errors


def _path_is_within_or_equal(path: str, root: Path) -> bool:
    try:
        if Path(path).resolve() != root.resolve():
            require_within(Path(path), root)
    except ValueError:
        return False
    return True


def validate_tool_lock(payload: Mapping[str, object]) -> list[str]:
    """Return policy violations without probing, writing, or mutating tools."""

    errors: list[str] = _network_field_errors(payload)
    if payload.get("schema") != LOCK_SCHEMA:
        errors.append(f"unsupported schema: {payload.get('schema')!r}")
    unexpected_lock_fields = set(payload).difference(LOCK_FIELDS)
    if unexpected_lock_fields:
        errors.append(f"unexpected lock fields: {', '.join(sorted(unexpected_lock_fields))}")

    tools = payload.get("tools")
    if not isinstance(tools, list):
        return [*errors, "tools must be a list"]

    observed_ids: list[str] = []
    for item in tools:
        if not isinstance(item, Mapping):
            errors.append("tool record must be an object")
            continue
        tool_id = item.get("id")
        if not isinstance(tool_id, str) or not tool_id:
            errors.append("tool record missing id")
            continue
        observed_ids.append(tool_id)
        unexpected_tool_fields = set(item).difference(TOOL_FIELDS)
        missing_tool_fields = TOOL_FIELDS.difference(item)
        if unexpected_tool_fields:
            errors.append(f"{tool_id}: unexpected fields: {', '.join(sorted(unexpected_tool_fields))}")
        if missing_tool_fields:
            errors.append(f"{tool_id}: missing fields: {', '.join(sorted(missing_tool_fields))}")
        if tool_id not in REQUIRED_TOOL_IDS:
            errors.append(f"unknown tool id: {tool_id}")
        version_value = item.get("version")
        if not isinstance(version_value, str) or not version_value.strip():
            errors.append(f"{tool_id}: missing version")
        license_value = item.get("license")
        if not isinstance(license_value, str) or not license_value.strip():
            errors.append(f"{tool_id}: missing license")
        elif tool_id in TOOL_LICENSES and license_value != TOOL_LICENSES[tool_id]:
            errors.append(f"{tool_id}: expected license {TOOL_LICENSES[tool_id]}")
        if item.get("execution") != "local":
            errors.append(f"{tool_id}: paid or cloud tool execution is prohibited")
        path_value = item.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            errors.append(f"{tool_id}: missing path")
        elif tool_id in TOOL_ROOTS:
            if not _path_is_within_or_equal(path_value, TOOL_ROOTS[tool_id]):
                errors.append(f"{tool_id}: path outside approved local tool roots")
        sha256_value = item.get("sha256")
        if not isinstance(sha256_value, str) or not SHA256_PATTERN.fullmatch(sha256_value):
            errors.append(f"{tool_id}: invalid sha256")
    if set(observed_ids) != REQUIRED_TOOL_IDS or len(observed_ids) != len(REQUIRED_TOOL_IDS):
        errors.append("tools must contain exact required tool IDs")
    if len(observed_ids) != len(set(observed_ids)):
        errors.append("duplicate tool id")
    license_evidence = payload.get("license_evidence")
    if not isinstance(license_evidence, Mapping):
        errors.append("license_evidence must be an object")
    elif set(license_evidence) != {"blender-mcp"}:
        errors.append("license_evidence must contain only blender-mcp")
    else:
        evidence = license_evidence["blender-mcp"]
        if not isinstance(evidence, Mapping):
            errors.append("blender-mcp license evidence must be an object")
        else:
            if set(evidence) != LICENSE_EVIDENCE_FIELDS:
                errors.append("blender-mcp license evidence must contain only path and sha256")
            evidence_path = evidence.get("path")
            if not isinstance(evidence_path, str) or not _path_is_within_or_equal(
                evidence_path, BLENDER_MCP_ROOT
            ):
                errors.append("blender-mcp license evidence path outside approved local tool roots")
            evidence_hash = evidence.get("sha256")
            if not isinstance(evidence_hash, str) or not SHA256_PATTERN.fullmatch(evidence_hash):
                errors.append("blender-mcp license evidence invalid sha256")
    asset_provenance = payload.get("asset_provenance")
    if not isinstance(asset_provenance, Mapping) or set(asset_provenance) != {"pinned_hdri"}:
        errors.append("asset_provenance must contain only pinned_hdri")
    else:
        hdri = asset_provenance["pinned_hdri"]
        if not isinstance(hdri, Mapping) or set(hdri) != ASSET_PROVENANCE_FIELDS:
            errors.append("pinned_hdri provenance must contain only path, sha256, and license")
        else:
            if hdri.get("path") != PINNED_HDRI_RELATIVE_PATH:
                errors.append("pinned_hdri provenance path must equal the governed HDRI")
            if hdri.get("sha256") != PINNED_HDRI_SHA256:
                errors.append("pinned_hdri provenance sha256 must equal the governed HDRI hash")
            if hdri.get("license") != "CC0-1.0":
                errors.append("pinned_hdri provenance license must equal CC0-1.0")
    return errors


def free_tool_lock_payload() -> dict[str, object]:
    """Build a JSON-serializable lock with reproducible provenance hashes."""

    records = discover_free_tools()
    license_path = _first_blender_mcp_license_evidence()
    payload: dict[str, object] = {
        "schema": LOCK_SCHEMA,
        "tools": [{**asdict(record), "execution": "local"} for record in records],
        "license_evidence": {
            "blender-mcp": {"path": str(license_path), "sha256": sha256_file(license_path)}
        },
        "asset_provenance": {
            "pinned_hdri": {
                "path": PINNED_HDRI_RELATIVE_PATH,
                "sha256": PINNED_HDRI_SHA256,
                "license": "CC0-1.0",
            }
        },
    }
    errors = validate_tool_lock(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return payload


def write_free_tool_lock() -> dict[str, object]:
    """Atomically write the sole approved external tool manifest."""

    destination = require_within(LOCK_PATH, ASSET_ROOT)
    payload = free_tool_lock_payload()
    atomic_write_json(destination, payload)
    return payload


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Inspect or write the PIMM free-tool lock.")
    parser.add_argument("--write-lock", action="store_true")
    arguments = parser.parse_args()
    payload = write_free_tool_lock() if arguments.write_lock else free_tool_lock_payload()
    print(json.dumps(payload, indent=2, sort_keys=True))
