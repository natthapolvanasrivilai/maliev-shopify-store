"""Fail-closed provenance validation for PIMM contextual production assets."""

from __future__ import annotations

from pathlib import PurePosixPath
import re
from typing import Mapping
from urllib.parse import parse_qsl, urlparse


EXTERNAL_ASSET_SCHEMA = "maliev.pimm-external-assets/v1"
_ROOT_FIELDS = frozenset({"schema", "assets"})
_ASSET_FIELDS = frozenset(
    {
        "source_url",
        "asset_version_id",
        "license",
        "local_relative_path",
        "sha256",
        "intended_shot_ids",
        "machine_master_modified",
    }
)
_SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
_ACCOUNT_GATED_SEGMENTS = frozenset({"account", "auth", "login", "oauth", "sso", "signin", "sign-in"})


def _safe_asset_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and len(path.parts) > 1
        and path.parts[0] == "assets"
        and bool(path.suffix)
    )


def _public_source_url(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return False
    segments = {segment.lower() for segment in parsed.path.split("/") if segment}
    hostname = {segment.lower() for segment in parsed.hostname.split(".") if segment} if parsed.hostname else set()
    query = {part.lower() for pair in parse_qsl(parsed.query, keep_blank_values=True) for part in pair}
    return not bool((segments | hostname | query) & _ACCOUNT_GATED_SEGMENTS)


def _polyhaven_asset_id(value: object) -> str | None:
    """Return the public Poly Haven page slug when the source has its canonical shape."""

    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.hostname != "polyhaven.com" or len(parts) != 2 or parts[0] != "a":
        return None
    return parts[1]


def validate_external_assets(
    manifest: object, campaign_shot_ids: object
) -> list[str]:
    """Return every provenance and campaign-scope error without reading assets or network."""

    errors: list[str] = []
    if not isinstance(manifest, Mapping):
        return ["external asset manifest root must be an object"]
    actual_root_fields = set(manifest)
    missing_root = sorted(_ROOT_FIELDS - actual_root_fields)
    extra_root = sorted(actual_root_fields - _ROOT_FIELDS)
    if missing_root:
        errors.append(f"external asset manifest missing fields: {', '.join(missing_root)}")
    if extra_root:
        errors.append(f"external asset manifest unexpected fields: {', '.join(extra_root)}")
    if manifest.get("schema") != EXTERNAL_ASSET_SCHEMA:
        errors.append(f"external asset manifest schema must equal {EXTERNAL_ASSET_SCHEMA}")

    raw_campaign_ids = campaign_shot_ids if isinstance(campaign_shot_ids, (set, frozenset, tuple, list)) else ()
    valid_shot_ids = {value for value in raw_campaign_ids if isinstance(value, str)}
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        return [*errors, "external asset manifest assets must be a list"]
    for index, asset in enumerate(assets):
        prefix = f"assets[{index}]"
        if not isinstance(asset, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        fields = set(asset)
        missing = sorted(_ASSET_FIELDS - fields)
        extra = sorted(fields - _ASSET_FIELDS)
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")
        if extra:
            errors.append(f"{prefix} unexpected fields: {', '.join(extra)}")
        if not _public_source_url(asset.get("source_url")):
            errors.append(f"{prefix} source_url must not require account access")
        version = asset.get("asset_version_id")
        if not isinstance(version, str) or not version.strip():
            errors.append(f"{prefix} asset_version_id must be a nonempty string")
        if asset.get("license") != "CC0-1.0":
            errors.append(f"{prefix} license must equal CC0-1.0")
        if not _safe_asset_path(asset.get("local_relative_path")):
            errors.append(f"{prefix} local_relative_path must be a safe relative asset path")
        polyhaven_id = _polyhaven_asset_id(asset.get("source_url"))
        if polyhaven_id is not None:
            if not isinstance(version, str) or not version.startswith(f"{polyhaven_id}:"):
                errors.append(f"{prefix} Poly Haven asset_version_id must begin with its source asset ID")
            local_path = asset.get("local_relative_path")
            expected_prefix = f"assets/external/polyhaven/{polyhaven_id}/"
            if not isinstance(local_path, str) or not local_path.startswith(expected_prefix):
                errors.append(f"{prefix} Poly Haven local_relative_path must remain in its source asset folder")
        if not isinstance(asset.get("sha256"), str) or _SHA256.fullmatch(asset["sha256"]) is None:
            errors.append(f"{prefix} sha256 must be 64 hexadecimal characters")
        intended = asset.get("intended_shot_ids")
        if not isinstance(intended, list) or not intended or not all(isinstance(value, str) for value in intended):
            errors.append(f"{prefix} intended_shot_ids must be a nonempty list of shot IDs")
        else:
            if len(intended) != len(set(intended)):
                errors.append(f"{prefix} intended_shot_ids must not contain duplicates")
            for shot_id in intended:
                if shot_id not in valid_shot_ids:
                    errors.append(f"{prefix} intended_shot_ids contains uncontracted shot: {shot_id}")
        if asset.get("machine_master_modified") is not False:
            errors.append(f"{prefix} machine_master_modified must be false")
    return errors
