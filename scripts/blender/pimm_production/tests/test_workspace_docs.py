"""Behavioral tests for canonical PIMM workspace documentation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.blender.pimm_production.io_contract import atomic_write_json, sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
from scripts.blender.pimm_production.workspace_docs import (
    canonical_workspace_docs,
    install_workspace_docs,
    verify_workspace_docs,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
DOC_ROOT = REPO_ROOT / "docs" / "pimm-blender-governance"


class WorkspaceDocsTests(unittest.TestCase):
    def test_workspace_docs_define_free_tool_and_render_gates(self):
        agents = (DOC_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Paid add-ons, subscriptions, and cloud AI are prohibited", agents)
        self.assertIn("BlenderMCP defaults to read-only inspection", agents)
        self.assertIn("30G", agents)
        self.assertIn("300/300", agents)
        self.assertIn("50G", agents)
        self.assertIn("350/350", agents)
        self.assertIn("native-resolution rendering requires owner approval", agents)

    def test_workspace_docs_define_static_and_future_animation_ownership(self):
        agents = (DOC_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("`scenes/stills/`", agents)
        self.assertIn("`scenes/animations/`", agents)
        self.assertIn("`rigs/`", agents)
        self.assertIn("one shot per `.blend`", agents)
        self.assertIn("Animation remains blocked", agents)
        self.assertIn("setpoint, measured value, or both", agents)
        self.assertIn("Storefront derivatives", agents)

    def test_install_copies_each_canonical_document_with_a_matching_hash(self):
        with TemporaryDirectory() as root:
            workspace_root = Path(root)
            installed = install_workspace_docs(REPO_ROOT, workspace_root)
            expected = canonical_workspace_docs(REPO_ROOT)

            self.assertEqual(len(installed), len(expected))
            self.assertEqual(verify_workspace_docs(REPO_ROOT, workspace_root), [])
            for source, destination in expected.items():
                copied = workspace_root / destination.relative_to(ASSET_ROOT)
                self.assertEqual(sha256_file(source), sha256_file(copied))

    def test_verify_workspace_docs_rejects_drift(self):
        with TemporaryDirectory() as root:
            workspace_root = Path(root)
            destination = workspace_root / "AGENTS.md"
            destination.write_text("stale", encoding="utf-8")

            errors = verify_workspace_docs(REPO_ROOT, workspace_root)

            self.assertRegex("\n".join(errors), "AGENTS.md SHA-256 drift")

    def test_atomic_write_json_replaces_complete_json_payload(self):
        with TemporaryDirectory() as root:
            destination = Path(root) / "manifest.json"
            destination.write_text('{"old": true}\n', encoding="utf-8")

            atomic_write_json(destination, {"machine": "30G", "values": [300, 300]})

            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8")),
                {"machine": "30G", "values": [300, 300]},
            )
            self.assertFalse(destination.with_suffix(".json.tmp").exists())

    def test_sha256_file_matches_the_standard_digest(self):
        with TemporaryDirectory() as root:
            sample = Path(root) / "sample.txt"
            sample.write_bytes(b"PIMM governance\n")

            self.assertEqual(
                sha256_file(sample),
                hashlib.sha256(b"PIMM governance\n").hexdigest().upper(),
            )

    def test_path_guard_rejects_workspace_root_and_outside_destination(self):
        with self.assertRaises(ValueError):
            require_within(ASSET_ROOT, ASSET_ROOT)
        with self.assertRaises(ValueError):
            require_within(ASSET_ROOT.parent, ASSET_ROOT)


if __name__ == "__main__":
    unittest.main()
