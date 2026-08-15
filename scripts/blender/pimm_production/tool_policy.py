"""Discover and lock the approved local PIMM production tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.metadata import metadata, version
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
REQUIRED_TOOL_IDS = frozenset({"blender", "blender-mcp", "python", "pillow"})
APPROVED_LICENSES = frozenset({"GPL-3.0-or-later", "PSF-2.0", "MIT-CMU"})
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


def validate_tool_lock(payload: Mapping[str, object]) -> list[str]:
    """Return policy violations without probing, writing, or mutating tools."""

    tools = payload.get("tools")
    if not isinstance(tools, list):
        return ["tools must be a list"]

    errors: list[str] = []
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
        if tool_id not in REQUIRED_TOOL_IDS:
            errors.append(f"unknown tool id: {tool_id}")
        version_value = item.get("version")
        if not isinstance(version_value, str) or not version_value.strip():
            errors.append(f"{tool_id}: missing version")
        license_value = item.get("license")
        if not isinstance(license_value, str) or not license_value.strip():
            errors.append(f"{tool_id}: missing license")
        elif license_value not in APPROVED_LICENSES:
            errors.append(f"{tool_id}: unknown commercial license")
        if item.get("execution") != "local":
            errors.append(f"{tool_id}: paid or cloud tool execution is prohibited")
        path_value = item.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            errors.append(f"{tool_id}: missing path")
        elif tool_id in TOOL_ROOTS:
            try:
                if Path(path_value).resolve() != TOOL_ROOTS[tool_id].resolve():
                    require_within(Path(path_value), TOOL_ROOTS[tool_id])
            except ValueError:
                errors.append(f"{tool_id}: path outside approved local tool roots")
    if len(observed_ids) != len(set(observed_ids)):
        errors.append("duplicate tool id")
    return errors


def free_tool_lock_payload() -> dict[str, object]:
    """Build a JSON-serializable lock with reproducible provenance hashes."""

    records = discover_free_tools()
    errors = validate_tool_lock(
        {"tools": [{**asdict(record), "execution": "local"} for record in records]}
    )
    if errors:
        raise ValueError("; ".join(errors))
    license_path = _first_blender_mcp_license_evidence()
    return {
        "schema": "pimm-free-tools-lock/v1",
        "tools": [{**asdict(record), "execution": "local"} for record in records],
        "license_evidence": {
            "blender-mcp": {"path": str(license_path), "sha256": sha256_file(license_path)}
        },
    }


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
