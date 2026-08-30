"""Tests for fail-closed public Poly Haven acquisition."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import io
from pathlib import Path, PurePosixPath
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts.blender.pimm_production import polyhaven_assets


APPROVED_POLYHAVEN = {
    "university_workshop": {"kind": "hdris", "resolution": "4k", "format": "exr"},
    "tool_cart": {"kind": "models", "resolution": "1k", "format": "blend"},
    "metal_toolbox": {"kind": "models", "resolution": "1k", "format": "blend"},
}


class _Response(io.BytesIO):
    def __init__(self, payload: bytes, url: str) -> None:
        super().__init__(payload)
        self.status = 200
        self._url = url

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _metadata(spec: polyhaven_assets.PolyHavenAssetSpec, *, md5: str) -> dict[str, object]:
    item = {
        "url": f"https://dl.polyhaven.org/file/ph-assets/{spec.asset_id}_{spec.resolution}.{spec.format}",
        "md5": md5,
        "size": 3,
    }
    if spec.kind == "hdris":
        return {"hdri": {spec.resolution: {spec.format: item}}}
    return {spec.format: {spec.resolution: {spec.format: item}}}


class PolyHavenAssetTests(unittest.TestCase):
    def test_approved_specs_are_exactly_the_three_authorized_assets(self) -> None:
        actual = {
            asset_id: {"kind": spec.kind, "resolution": spec.resolution, "format": spec.format}
            for asset_id, spec in polyhaven_assets.APPROVED_POLYHAVEN.items()
        }

        self.assertEqual(actual, APPROVED_POLYHAVEN)

    def test_resolve_public_download_selects_only_the_declared_variant(self) -> None:
        spec = polyhaven_assets.APPROVED_POLYHAVEN["university_workshop"]
        digest = hashlib.md5(b"abc").hexdigest()
        with patch.object(polyhaven_assets, "_open_no_redirect", return_value=_Response(
            polyhaven_assets.json.dumps(_metadata(spec, md5=digest)).encode("utf-8"),
            polyhaven_assets._api_url(spec.asset_id),
        )):
            resolved = polyhaven_assets.resolve_public_download(spec)

        self.assertEqual(resolved.url, "https://dl.polyhaven.org/file/ph-assets/university_workshop_4k.exr")
        self.assertEqual(resolved.md5, digest)
        self.assertEqual(resolved.local_filename, "university_workshop_4k.exr")

    def test_resolve_rejects_redirects_missing_checksums_and_non_cc0_specs(self) -> None:
        spec = polyhaven_assets.APPROVED_POLYHAVEN["tool_cart"]
        metadata = _metadata(spec, md5=hashlib.md5(b"abc").hexdigest())
        model = metadata["blend"]["1k"]["blend"]  # type: ignore[index]
        assert isinstance(model, dict)
        model.pop("md5")
        with patch.object(polyhaven_assets, "_open_no_redirect", return_value=_Response(
            polyhaven_assets.json.dumps(metadata).encode("utf-8"),
            polyhaven_assets._api_url(spec.asset_id),
        )):
            with self.assertRaisesRegex(ValueError, "checksum"):
                polyhaven_assets.resolve_public_download(spec)
        with self.assertRaisesRegex(ValueError, "CC0-1.0"):
            polyhaven_assets.resolve_public_download(replace(spec, license="CC-BY-4.0"))
        with patch.object(polyhaven_assets, "_open_no_redirect", return_value=_Response(
            b"{}", "https://evil.example.invalid/files/tool_cart"
        )):
            with self.assertRaisesRegex(ValueError, "redirect"):
                polyhaven_assets.resolve_public_download(spec)

    def test_resolve_rejects_an_encoded_primary_filename_that_is_not_a_safe_component(self) -> None:
        spec = polyhaven_assets.APPROVED_POLYHAVEN["university_workshop"]
        metadata = _metadata(spec, md5=hashlib.md5(b"abc").hexdigest())
        item = metadata["hdri"]["4k"]["exr"]  # type: ignore[index]
        assert isinstance(item, dict)
        item["url"] = "https://dl.polyhaven.org/file/ph-assets/..%5cescape.exr"
        with patch.object(polyhaven_assets, "_open_no_redirect", return_value=_Response(
            polyhaven_assets.json.dumps(metadata).encode("utf-8"),
            polyhaven_assets._api_url(spec.asset_id),
        )):
            with self.assertRaisesRegex(ValueError, "safe filename"):
                polyhaven_assets.resolve_public_download(spec)

    def test_public_requests_identify_the_provenance_client(self) -> None:
        captured: list[object] = []

        class _Opener:
            def open(self, request: object, timeout: int) -> _Response:
                captured.append(request)
                return _Response(b"{}", str(request.full_url))  # type: ignore[attr-defined]

        with patch.object(polyhaven_assets, "build_opener", return_value=_Opener()):
            with polyhaven_assets._open_no_redirect(polyhaven_assets._api_url("tool_cart"), polyhaven_assets.API_HOST):
                pass

        self.assertEqual(captured[0].get_header("User-agent"), polyhaven_assets.PUBLIC_CLIENT_USER_AGENT)  # type: ignore[attr-defined]

    def test_download_hashes_bytes_and_refuses_existing_destination(self) -> None:
        spec = polyhaven_assets.APPROVED_POLYHAVEN["university_workshop"]
        payload = b"asset bytes"
        resolved = polyhaven_assets.ResolvedDownload(
            spec=spec,
            url="https://dl.polyhaven.org/file/ph-assets/university_workshop_4k.exr",
            md5=hashlib.md5(payload).hexdigest(),
            size=len(payload),
            local_filename="university_workshop_4k.exr",
            includes=(),
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / resolved.local_filename
            with patch.object(polyhaven_assets, "resolve_public_download", return_value=resolved), patch.object(
                polyhaven_assets, "_open_no_redirect", return_value=_Response(payload, resolved.url)
            ):
                result = polyhaven_assets.download_asset_once(spec, destination)
            self.assertTrue(result.created)
            self.assertEqual(result.sha256, hashlib.sha256(payload).hexdigest().upper())
            self.assertEqual(destination.read_bytes(), payload)
            with self.assertRaises(FileExistsError):
                polyhaven_assets.download_asset_once(spec, destination)

    def test_download_rejects_archive_traversal_before_writing_a_destination(self) -> None:
        spec = polyhaven_assets.APPROVED_POLYHAVEN["university_workshop"]
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("../escape.exr", b"bad")
        payload = archive.getvalue()
        resolved = polyhaven_assets.ResolvedDownload(
            spec=spec,
            url="https://dl.polyhaven.org/file/ph-assets/university_workshop_4k.exr",
            md5=hashlib.md5(payload).hexdigest(),
            size=len(payload),
            local_filename="university_workshop_4k.exr",
            includes=(),
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / resolved.local_filename
            with patch.object(polyhaven_assets, "resolve_public_download", return_value=resolved), patch.object(
                polyhaven_assets, "_open_no_redirect", return_value=_Response(payload, resolved.url)
            ):
                with self.assertRaisesRegex(ValueError, "archive member"):
                    polyhaven_assets.download_asset_once(spec, destination)
            self.assertFalse(destination.exists())

    def test_download_rolls_back_primary_when_a_later_dependency_commit_fails(self) -> None:
        spec = polyhaven_assets.APPROVED_POLYHAVEN["tool_cart"]
        root_payload = b"root"
        dependency_payload = b"dependency"
        resolved = polyhaven_assets.ResolvedDownload(
            spec=spec,
            url="https://dl.polyhaven.org/file/ph-assets/tool_cart_1k.blend",
            md5=hashlib.md5(root_payload).hexdigest(),
            size=len(root_payload),
            local_filename="tool_cart_1k.blend",
            includes=(polyhaven_assets.DownloadDependency(
                PurePosixPath("textures/tool_cart_diff_1k.jpg"),
                "https://dl.polyhaven.org/file/ph-assets/tool_cart_diff_1k.jpg",
                hashlib.md5(dependency_payload).hexdigest(),
                len(dependency_payload),
            ),),
        )
        payloads = {resolved.url: root_payload, resolved.includes[0].url: dependency_payload}
        original_commit = polyhaven_assets._commit_temp
        commits = 0

        def fail_second_commit(temp: Path, destination: Path) -> None:
            nonlocal commits
            commits += 1
            if commits == 2:
                raise OSError("induced later dependency commit failure")
            original_commit(temp, destination)

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / resolved.local_filename
            with patch.object(polyhaven_assets, "resolve_public_download", return_value=resolved), patch.object(
                polyhaven_assets, "_open_no_redirect", side_effect=lambda url, host: _Response(payloads[url], url)
            ), patch.object(polyhaven_assets, "_commit_temp", side_effect=fail_second_commit):
                with self.assertRaisesRegex(OSError, "induced later dependency"):
                    polyhaven_assets.download_asset_once(spec, destination)
            self.assertFalse(destination.exists())
            self.assertFalse((destination.parent / "textures").exists())

    def test_batch_rolls_back_new_files_and_manifest_bytes_when_manifest_update_fails(self) -> None:
        first = polyhaven_assets.APPROVED_POLYHAVEN["university_workshop"]
        second = polyhaven_assets.APPROVED_POLYHAVEN["tool_cart"]
        first_payload = b"first"
        second_payload = b"second"
        first_resolved = polyhaven_assets.ResolvedDownload(
            first, "https://dl.polyhaven.org/file/ph-assets/university_workshop_4k.exr",
            hashlib.md5(first_payload).hexdigest(), len(first_payload), "university_workshop_4k.exr", (),
        )
        second_resolved = polyhaven_assets.ResolvedDownload(
            second, "https://dl.polyhaven.org/file/ph-assets/tool_cart_1k.blend",
            hashlib.md5(second_payload).hexdigest(), len(second_payload), "tool_cart_1k.blend", (),
        )
        resolutions = {first.asset_id: first_resolved, second.asset_id: second_resolved}
        payloads = {first_resolved.url: first_payload, second_resolved.url: second_payload}
        with tempfile.TemporaryDirectory() as directory:
            asset_root = Path(directory)
            manifest = asset_root / "manifests" / "external-assets-v1.json"
            manifest.parent.mkdir()
            before = b'{\n  "schema": "maliev.pimm-external-assets/v1",\n  "assets": []\n}\n'
            manifest.write_bytes(before)

            def mutate_manifest_then_fail(root: Path, records: list[dict[str, object]]) -> Path:
                manifest.write_bytes(b"mutated during induced failure")
                raise OSError("induced manifest update failure")

            with patch.object(polyhaven_assets, "resolve_public_download", side_effect=lambda spec: resolutions[spec.asset_id]), patch.object(
                polyhaven_assets, "_open_no_redirect", side_effect=lambda url, host: _Response(payloads[url], url)
            ), patch.object(polyhaven_assets, "update_external_manifest", side_effect=mutate_manifest_then_fail):
                with self.assertRaisesRegex(OSError, "induced manifest update"):
                    polyhaven_assets.acquire_approved_assets(asset_root, [first.asset_id, second.asset_id])
            self.assertEqual(manifest.read_bytes(), before)
            self.assertFalse((asset_root / "assets").exists())


if __name__ == "__main__":
    unittest.main()
