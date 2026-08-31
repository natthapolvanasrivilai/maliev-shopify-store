"""Contract tests for recorded PIMM external production assets."""

from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.blender.pimm_production.external_asset_manifest import (
    scope_external_assets_to_campaign,
    validate_external_assets,
)


CAMPAIGN_SHOTS = {
    "pimm-50g--workshop--wide",
    "pimm-50g--workshop--portrait",
}


def _manifest() -> dict[str, object]:
    return {
        "schema": "maliev.pimm-external-assets/v1",
        "assets": [
            {
                "source_url": "https://assets.example.invalid/a/industrial_crate",
                "asset_version_id": "industrial-crate-1.0",
                "license": "CC0-1.0",
                "local_relative_path": "assets/props/industrial-crate.blend",
                "sha256": "a" * 64,
                "intended_shot_ids": ["pimm-50g--workshop--wide"],
                "machine_master_modified": False,
            }
        ],
    }


class ExternalAssetManifestTests(unittest.TestCase):
    def test_scoping_ignores_legacy_campaign_ids_but_preserves_shared_assets(self):
        manifest = _manifest()
        manifest["assets"][0]["intended_shot_ids"] = [
            "legacy-editorial-shot",
            "pimm-50g--concept-modern-workshop",
        ]

        scoped = scope_external_assets_to_campaign(
            manifest, {"pimm-50g--concept-modern-workshop"}
        )

        self.assertEqual(
            scoped["assets"][0]["intended_shot_ids"],
            ["pimm-50g--concept-modern-workshop"],
        )
    def test_accepts_an_explicitly_empty_asset_list(self) -> None:
        """Catches a validator that forces decorative third-party props into workshop proofs."""

        errors = validate_external_assets(
            {"schema": "maliev.pimm-external-assets/v1", "assets": []},
            CAMPAIGN_SHOTS,
        )

        self.assertEqual(errors, [])

    def test_accepts_complete_public_cc0_asset_provenance(self) -> None:
        """Catches a provenance gate that rejects a complete, scoped public CC0 record."""

        self.assertEqual(validate_external_assets(_manifest(), CAMPAIGN_SHOTS), [])

    def test_accepts_polyhaven_editorial_provenance_only_for_its_concept_shots(self) -> None:
        manifest = _manifest()
        asset = manifest["assets"][0]
        assert isinstance(asset, dict)
        asset.update(
            {
                "source_url": "https://polyhaven.com/a/metal_toolbox",
                "asset_version_id": "metal_toolbox:1k:blend:e0ea9770745ba209029fecc482e27d53",
                "local_relative_path": "assets/external/polyhaven/metal_toolbox/metal_toolbox_1k.blend",
                "intended_shot_ids": ["pimm-50g--concept-modern-workshop"],
            }
        )

        self.assertEqual(
            validate_external_assets(manifest, {"pimm-50g--concept-modern-workshop"}),
            [],
        )

    def test_rejects_polyhaven_provenance_that_does_not_bind_page_version_and_path(self) -> None:
        manifest = _manifest()
        asset = manifest["assets"][0]
        assert isinstance(asset, dict)
        asset.update(
            {
                "source_url": "https://polyhaven.com/a/metal_toolbox",
                "asset_version_id": "tool_cart:models:1k:blend:3861700017732faa0f596ee072647726",
                "local_relative_path": "assets/external/polyhaven/tool_cart/tool_cart_1k.blend",
                "intended_shot_ids": ["pimm-50g--concept-modern-workshop"],
            }
        )

        errors = validate_external_assets(manifest, {"pimm-50g--concept-modern-workshop"})

        self.assertIn("assets[0] Poly Haven asset_version_id must begin with its source asset ID", errors)
        self.assertIn("assets[0] Poly Haven local_relative_path must remain in its source asset folder", errors)

    def test_collects_incomplete_account_gated_and_uncontracted_asset_errors(self) -> None:
        """Catches a fail-open manifest parser that accepts unauditable or scoped-wrong assets."""

        manifest = deepcopy(_manifest())
        asset = manifest["assets"][0]
        assert isinstance(asset, dict)
        asset.pop("license")
        asset["source_url"] = "https://assets.example.invalid/login/private-prop"
        asset["intended_shot_ids"] = ["pimm-30g--uncontracted--view"]

        errors = validate_external_assets(manifest, CAMPAIGN_SHOTS)

        joined = "\n".join(errors)
        self.assertIn("assets[0] missing fields: license", joined)
        self.assertIn("assets[0] source_url must not require account access", joined)
        self.assertIn("assets[0] intended_shot_ids contains uncontracted shot", joined)

    def test_rejects_account_gating_in_hostname_and_query(self) -> None:
        """Catches account gates hidden outside a literal URL path segment."""

        for source_url in (
            "https://login.example.com/download",
            "https://assets.example.com/download?auth=required",
        ):
            with self.subTest(source_url=source_url):
                manifest = _manifest()
                asset = manifest["assets"][0]
                assert isinstance(asset, dict)
                asset["source_url"] = source_url

                self.assertIn(
                    "assets[0] source_url must not require account access",
                    validate_external_assets(manifest, CAMPAIGN_SHOTS),
                )

    def test_rejects_wrong_license_master_mutation_and_unsafe_local_path(self) -> None:
        """Catches records that could alter the masters or hide asset bytes outside the asset root."""

        manifest = _manifest()
        asset = manifest["assets"][0]
        assert isinstance(asset, dict)
        asset["license"] = "CC-BY-4.0"
        asset["machine_master_modified"] = True
        asset["local_relative_path"] = "../masters/PIMM-50G-MASTER.blend"

        errors = validate_external_assets(manifest, CAMPAIGN_SHOTS)

        joined = "\n".join(errors)
        self.assertIn("assets[0] license must equal CC0-1.0", joined)
        self.assertIn("assets[0] machine_master_modified must be false", joined)
        self.assertIn("assets[0] local_relative_path must be a safe relative asset path", joined)


if __name__ == "__main__":
    unittest.main()
