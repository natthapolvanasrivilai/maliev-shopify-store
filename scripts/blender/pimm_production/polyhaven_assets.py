"""Fail-closed acquisition of the approved public Poly Haven editorial assets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import ntpath
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import tempfile
from typing import Mapping
import unicodedata
from urllib.error import HTTPError
from urllib.parse import unquote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid
import zipfile


API_HOST = "api.polyhaven.com"
DOWNLOAD_HOST = "dl.polyhaven.org"
POLYHAVEN_HOST = "polyhaven.com"
LICENSE = "CC0-1.0"
PUBLIC_CLIENT_USER_AGENT = "MALIEV-PIMM-Editorial-Provenance/1.0 (+https://www.maliev.com/)"
ASSET_DIRECTORY = PurePosixPath("assets/external/polyhaven")
MANIFEST_RELATIVE_PATH = PurePosixPath("manifests/external-assets-v1.json")


@dataclass(frozen=True)
class PolyHavenAssetSpec:
    """An exact, public, approved Poly Haven variant and its permitted use."""

    asset_id: str
    kind: str
    resolution: str
    format: str
    intended_shot_ids: tuple[str, ...]
    source_url: str
    license: str = LICENSE


APPROVED_POLYHAVEN = {
    "university_workshop": PolyHavenAssetSpec(
        "university_workshop", "hdris", "4k", "exr",
        ("pimm-50g--concept-modern-workshop",),
        "https://polyhaven.com/a/university_workshop",
    ),
    "tool_cart": PolyHavenAssetSpec(
        "tool_cart", "models", "1k", "blend",
        ("pimm-50g--concept-modern-workshop",),
        "https://polyhaven.com/a/tool_cart",
    ),
    "metal_toolbox": PolyHavenAssetSpec(
        "metal_toolbox", "models", "1k", "blend",
        (
            "pimm-50g--concept-modern-workshop",
            "pimm-30g--concept-process-still-life",
        ),
        "https://polyhaven.com/a/metal_toolbox",
    ),
}


@dataclass(frozen=True)
class DownloadDependency:
    """An include file that accompanies a model's direct Blend download."""

    relative_path: PurePosixPath
    url: str
    md5: str
    size: int


@dataclass(frozen=True)
class ResolvedDownload:
    """Checksummed direct public download data selected from the files API."""

    spec: PolyHavenAssetSpec
    url: str
    md5: str
    size: int
    local_filename: str
    includes: tuple[DownloadDependency, ...]


@dataclass(frozen=True)
class DownloadedAsset:
    """A verified root asset that can be recorded in the external manifest."""

    resolved: ResolvedDownload
    destination: Path
    sha256: str
    created: bool


@dataclass(frozen=True)
class _StagedFile:
    """A verified temporary download awaiting an all-or-nothing commit."""

    temporary_path: Path
    destination: Path
    sha256: str


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def _api_url(asset_id: str) -> str:
    return f"https://{API_HOST}/files/{asset_id}"


def _open_no_redirect(url: str, allowed_host: str):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != allowed_host or parsed.username or parsed.password:
        raise ValueError(f"public download URL must be HTTPS on {allowed_host}")
    try:
        request = Request(url, headers={"User-Agent": PUBLIC_CLIENT_USER_AGENT})
        response = build_opener(_NoRedirect()).open(request, timeout=60)
    except HTTPError as error:
        if 300 <= error.code < 400:
            raise ValueError("public download redirect is not permitted") from error
        raise
    status = getattr(response, "status", 200)
    final_url = response.geturl()
    final = urlparse(final_url)
    if status < 200 or status >= 300 or final.scheme != "https" or final.hostname != allowed_host or final_url != url:
        response.close()
        raise ValueError("public download redirect or non-success response is not permitted")
    return response


def _safe_relative_path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("download path must be a nonempty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts or not path.name:
        raise ValueError("download path must not traverse outside the asset package")
    return path


def _safe_filename(value: object) -> str:
    """Require one decoded filename component that is safe on POSIX and Windows."""

    if not isinstance(value, str) or not value or value in {".", ".."}:
        raise ValueError("download URL must contain one safe filename component")
    if any(character in value for character in ("/", "\\", "<", ">", ":", '"', "|", "?", "*")) or value[-1] in {".", " "} or any(
        unicodedata.category(character) == "Cc" for character in value
    ):
        raise ValueError("download URL must contain one safe filename component")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.name != value
        or windows.name != value
        or windows.drive
        or windows.root
        or posix.is_absolute()
        or windows.is_absolute()
        or ntpath.isreserved(value)
    ):
        raise ValueError("download URL must contain one safe filename component")
    return value


def _metadata_item(value: object, *, label: str) -> tuple[str, str, int, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} metadata must be an object")
    url = value.get("url")
    checksum = value.get("md5")
    size = value.get("size")
    if not isinstance(url, str) or not url:
        raise ValueError(f"{label} metadata must include a public URL")
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != DOWNLOAD_HOST
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} URL must be a direct public Poly Haven download")
    if not isinstance(checksum, str) or len(checksum) != 32 or any(c not in "0123456789abcdefABCDEF" for c in checksum):
        raise ValueError(f"{label} metadata must include an MD5 checksum")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError(f"{label} metadata must include a positive byte size")
    filename = _safe_filename(unquote(PurePosixPath(parsed.path).name))
    return url, checksum.lower(), size, filename


def _validate_spec(spec: PolyHavenAssetSpec) -> None:
    if spec.license != LICENSE:
        raise ValueError("approved public assets must use CC0-1.0")
    approved = APPROVED_POLYHAVEN.get(spec.asset_id)
    if approved != spec:
        raise ValueError("asset is not an exact approved Poly Haven variant")
    source = urlparse(spec.source_url)
    if source.scheme != "https" or source.hostname != POLYHAVEN_HOST or source.path != f"/a/{spec.asset_id}":
        raise ValueError("asset source page must be the exact public Poly Haven page")


def _select_metadata(payload: object, spec: PolyHavenAssetSpec) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("Poly Haven files API response must be an object")
    try:
        if spec.kind == "hdris":
            selected = payload["hdri"][spec.resolution][spec.format]
        else:
            selected = payload[spec.format][spec.resolution][spec.format]
    except (KeyError, TypeError):
        raise ValueError("Poly Haven files API did not provide the exact approved variant") from None
    if not isinstance(selected, Mapping):
        raise ValueError("Poly Haven files API variant metadata must be an object")
    return selected


def resolve_public_download(spec: PolyHavenAssetSpec) -> ResolvedDownload:
    """Resolve only the exact declared public asset variant from Poly Haven's files API."""

    _validate_spec(spec)
    requested = _api_url(spec.asset_id)
    with _open_no_redirect(requested, API_HOST) as response:
        final_url = response.geturl()
        if final_url != requested or urlparse(final_url).hostname != API_HOST:
            raise ValueError("Poly Haven API redirect is not permitted")
        try:
            payload = json.loads(response.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Poly Haven files API returned invalid JSON") from error
    selected = _select_metadata(payload, spec)
    url, checksum, size, filename = _metadata_item(selected, label="selected asset")
    expected_suffix = f".{spec.format}"
    if not filename.lower().endswith(expected_suffix):
        raise ValueError("Poly Haven files API selected a file with an unexpected format")
    raw_includes = selected.get("include", {})
    if not isinstance(raw_includes, Mapping):
        raise ValueError("selected asset include metadata must be an object")
    includes: list[DownloadDependency] = []
    for relative_name, include_metadata in sorted(raw_includes.items()):
        relative_path = _safe_relative_path(relative_name)
        include_url, include_md5, include_size, _ = _metadata_item(include_metadata, label=f"include {relative_path}")
        includes.append(DownloadDependency(relative_path, include_url, include_md5, include_size))
    return ResolvedDownload(spec, url, checksum, size, filename, tuple(includes))


def _validate_archive_members(path: Path) -> None:
    """Reject unsafe archive member paths before any archive extraction could occur."""

    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            try:
                _safe_relative_path(member.filename)
            except ValueError as error:
                raise ValueError(f"unsafe archive member: {member.filename}") from error


def _stream_to_temp(url: str, expected_md5: str, expected_size: int, directory: Path) -> tuple[Path, str]:
    directory.mkdir(parents=True, exist_ok=True)
    temp = directory / f".{uuid.uuid4().hex}.polyhaven-part"
    digest_md5 = hashlib.md5()
    digest_sha256 = hashlib.sha256()
    written = 0
    try:
        with _open_no_redirect(url, DOWNLOAD_HOST) as response, temp.open("xb") as target:
            if response.geturl() != url or urlparse(response.geturl()).hostname != DOWNLOAD_HOST:
                raise ValueError("public download redirect is not permitted")
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
                digest_md5.update(chunk)
                digest_sha256.update(chunk)
                written += len(chunk)
        if written != expected_size:
            raise ValueError(f"download byte size mismatch: expected {expected_size}, received {written}")
        if digest_md5.hexdigest().lower() != expected_md5.lower():
            raise ValueError("download checksum mismatch")
        if zipfile.is_zipfile(temp):
            _validate_archive_members(temp)
            raise ValueError("archive download is not permitted for a declared direct asset format")
        return temp, digest_sha256.hexdigest().upper()
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def _commit_temp(temp: Path, destination: Path) -> None:
    """Atomically move one staged file after its parent has been transactionally prepared."""

    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing destination: {destination}")
    try:
        os.rename(temp, destination)
    except FileExistsError as error:
        raise FileExistsError(f"refusing to overwrite existing destination: {destination}") from error


def _create_missing_directories(path: Path) -> list[Path]:
    """Create a directory chain and return precisely the directories this call created."""

    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir()
    return list(reversed(missing))


def _restore_manifest_bytes(manifest_path: Path, original: bytes) -> None:
    """Restore the exact pre-run manifest bytes with an atomic replacement."""

    temporary = manifest_path.with_name(f".{manifest_path.name}.{uuid.uuid4().hex}.rollback")
    try:
        with temporary.open("xb") as target:
            target.write(original)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)


class _AssetTransaction:
    """Stages public files and makes their governed state observable only on commit."""

    def __init__(self, staging_parent: Path) -> None:
        self._staging_parent_directories = _create_missing_directories(staging_parent)
        try:
            self.staging_directory = Path(tempfile.mkdtemp(prefix=".polyhaven-stage-", dir=staging_parent))
        except Exception:
            for directory in reversed(self._staging_parent_directories):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            raise
        self.staged: list[_StagedFile] = []
        self.committed: list[Path] = []
        self.created_directories: list[Path] = []

    def stage(self, items: list[tuple[Path, str, str, int]]) -> list[str]:
        sha256_values: list[str] = []
        for destination, url, checksum, size in items:
            temporary, sha256 = _stream_to_temp(url, checksum, size, self.staging_directory)
            self.staged.append(_StagedFile(temporary, destination, sha256))
            sha256_values.append(sha256)
        return sha256_values

    def commit(self) -> None:
        try:
            for staged in self.staged:
                self.created_directories.extend(_create_missing_directories(staged.destination.parent))
                try:
                    _commit_temp(staged.temporary_path, staged.destination)
                except Exception:
                    if staged.destination.exists():
                        self.committed.append(staged.destination)
                    raise
                self.committed.append(staged.destination)
        except Exception:
            self.rollback()
            raise

    def rollback(self) -> None:
        for staged in self.staged:
            staged.temporary_path.unlink(missing_ok=True)
        for path in reversed(self.committed):
            path.unlink(missing_ok=True)
        self.committed.clear()
        shutil.rmtree(self.staging_directory, ignore_errors=True)
        for directory in reversed(self.created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        self.created_directories.clear()
        for directory in reversed(self._staging_parent_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        self._staging_parent_directories.clear()

    def close(self) -> None:
        shutil.rmtree(self.staging_directory, ignore_errors=True)


def download_asset_once(spec: PolyHavenAssetSpec, destination: Path) -> DownloadedAsset:
    """Download a checksummed approved asset once without replacing any destination file."""

    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing destination: {destination}")
    resolved = resolve_public_download(spec)
    if destination.name != resolved.local_filename:
        raise ValueError("destination filename must equal the exact selected public filename")
    items = [(destination, resolved.url, resolved.md5, resolved.size)]
    items.extend((destination.parent / include.relative_path, include.url, include.md5, include.size) for include in resolved.includes)
    if any(path.exists() for path, _, _, _ in items):
        raise FileExistsError("refusing to overwrite an existing selected asset or dependency")
    transaction = _AssetTransaction(destination.parent)
    try:
        sha256_values = transaction.stage(items)
        transaction.commit()
        transaction.close()
        return DownloadedAsset(resolved, destination, sha256_values[0], True)
    except Exception:
        transaction.rollback()
        raise


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _validate_existing(path: Path, url: str, expected_md5: str, expected_size: int) -> str:
    if path.stat().st_size != expected_size:
        raise ValueError(f"existing destination size does not match public metadata: {path}")
    digest = hashlib.md5()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest().lower() != expected_md5.lower():
        raise ValueError(f"existing destination checksum does not match public metadata: {path}")
    return _sha256(path)


def _provenance_record(asset_root: Path, downloaded: DownloadedAsset) -> dict[str, object]:
    relative = downloaded.destination.resolve().relative_to(asset_root.resolve()).as_posix()
    spec = downloaded.resolved.spec
    return {
        "source_url": spec.source_url,
        "asset_version_id": (
            f"{spec.asset_id}:{spec.kind}:{spec.resolution}:{spec.format}:{downloaded.resolved.md5}"
        ),
        "license": spec.license,
        "local_relative_path": relative,
        "sha256": downloaded.sha256,
        "intended_shot_ids": list(spec.intended_shot_ids),
        "machine_master_modified": False,
    }


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key in external asset manifest: {key}")
        result[key] = value
    return result


def update_external_manifest(asset_root: Path, records: list[dict[str, object]]) -> Path:
    """Atomically append new provenance while preserving every unrelated manifest record."""

    manifest_path = asset_root / MANIFEST_RELATIVE_PATH
    payload = json.loads(manifest_path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(payload, dict) or set(payload) != {"schema", "assets"} or not isinstance(payload["assets"], list):
        raise ValueError("external asset manifest must contain only schema and assets")
    assets = payload["assets"]
    for record in records:
        local_path = record["local_relative_path"]
        matching = [asset for asset in assets if isinstance(asset, Mapping) and asset.get("local_relative_path") == local_path]
        if matching and any(asset != record for asset in matching):
            raise ValueError(f"existing external asset record conflicts with selected destination: {local_path}")
        if not matching:
            assets.append(record)
    temp_path = manifest_path.with_name(f".{manifest_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("x", encoding="utf-8", newline="\n") as target:
            json.dump(payload, target, indent=2, ensure_ascii=False)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp_path, manifest_path)
    finally:
        temp_path.unlink(missing_ok=True)
    return manifest_path


def _target_destination(asset_root: Path, resolved: ResolvedDownload) -> Path:
    return asset_root / Path(ASSET_DIRECTORY) / resolved.spec.asset_id / resolved.local_filename


def acquire_approved_assets(asset_root: Path, asset_ids: list[str]) -> tuple[list[DownloadedAsset], Path]:
    """Acquire exact approved variants and update their provenance manifest atomically."""

    if not asset_ids or len(asset_ids) != len(set(asset_ids)):
        raise ValueError("provide each approved asset ID exactly once")
    specs: list[PolyHavenAssetSpec] = []
    for asset_id in asset_ids:
        try:
            specs.append(APPROVED_POLYHAVEN[asset_id])
        except KeyError:
            raise ValueError(f"asset is not approved: {asset_id}") from None
    manifest_path = asset_root / MANIFEST_RELATIVE_PATH
    manifest_before = manifest_path.read_bytes()
    downloaded: list[DownloadedAsset] = []
    pending: list[tuple[ResolvedDownload, Path, list[tuple[Path, str, str, int]]]] = []
    for spec in specs:
        resolved = resolve_public_download(spec)
        destination = _target_destination(asset_root, resolved)
        dependencies = [(destination, resolved.url, resolved.md5, resolved.size)]
        dependencies.extend((destination.parent / item.relative_path, item.url, item.md5, item.size) for item in resolved.includes)
        exists = [path.exists() for path, _, _, _ in dependencies]
        if any(exists):
            if not all(exists):
                raise FileExistsError("selected asset package is only partially present; refusing to replace it")
            primary_sha256 = ""
            for index, (path, url, checksum, size) in enumerate(dependencies):
                sha256 = _validate_existing(path, url, checksum, size)
                if index == 0:
                    primary_sha256 = sha256
            downloaded.append(DownloadedAsset(resolved, destination, primary_sha256, False))
        else:
            pending.append((resolved, destination, dependencies))
    transaction = _AssetTransaction(asset_root / Path(ASSET_DIRECTORY))
    try:
        new_assets: list[DownloadedAsset] = []
        for resolved, destination, dependencies in pending:
            sha256_values = transaction.stage(dependencies)
            new_assets.append(DownloadedAsset(resolved, destination, sha256_values[0], True))
        transaction.commit()
        downloaded.extend(new_assets)
        manifest = update_external_manifest(asset_root, [_provenance_record(asset_root, item) for item in downloaded])
        transaction.close()
        return downloaded, manifest
    except Exception:
        transaction.rollback()
        if manifest_path.read_bytes() != manifest_before:
            _restore_manifest_bytes(manifest_path, manifest_before)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", required=True, type=Path)
    parser.add_argument("--asset-id", required=True, action="append", choices=sorted(APPROVED_POLYHAVEN))
    args = parser.parse_args(argv)
    downloaded, manifest = acquire_approved_assets(args.asset_root, args.asset_id)
    for item in downloaded:
        print(json.dumps({
            "asset_id": item.resolved.spec.asset_id,
            "status": "created" if item.created else "validated-existing",
            "path": str(item.destination),
            "sha256": item.sha256,
        }, sort_keys=True))
    print(json.dumps({"manifest": str(manifest), "records": len(downloaded)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
