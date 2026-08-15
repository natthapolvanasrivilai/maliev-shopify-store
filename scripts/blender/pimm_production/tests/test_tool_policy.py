"""Contract tests for the free, local PIMM production tool lock."""

from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest

from scripts.blender.pimm_production.blender_session_preflight import inspect_open_session
from scripts.blender.pimm_production.tool_policy import validate_tool_lock


class ToolPolicyTests(unittest.TestCase):
    def test_tool_policy_script_runs_from_the_repository_root(self):
        repository_root = Path(__file__).resolve().parents[4]

        result = subprocess.run(
            ["python", "scripts/blender/pimm_production/tool_policy.py"],
            cwd=repository_root,
            capture_output=True,
            encoding="utf-8",
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"schema": "pimm-free-tools-lock/v1"', result.stdout)

    def test_paid_or_cloud_tool_is_rejected(self):
        payload = {
            "tools": [
                {
                    "id": "cloud-enhancer",
                    "license": "commercial",
                    "execution": "cloud",
                }
            ]
        }

        self.assertRegex("\n".join(validate_tool_lock(payload)), "paid or cloud tool")

    def test_allowed_local_tools_require_version_and_license(self):
        payload = {
            "tools": [
                {
                    "id": "blender",
                    "version": "5.2.0",
                    "license": "GPL-3.0-or-later",
                    "execution": "local",
                    "path": r"D:\Blender 5.2\blender.exe",
                }
            ]
        }

        self.assertEqual(validate_tool_lock(payload), [])

    def test_lock_rejects_missing_identity_and_unapproved_path(self):
        payload = {
            "tools": [
                {
                    "id": "blender",
                    "version": "",
                    "license": "",
                    "execution": "local",
                    "path": r"C:\Temp\blender.exe",
                }
            ]
        }

        errors = "\n".join(validate_tool_lock(payload))
        self.assertIn("missing version", errors)
        self.assertIn("missing license", errors)
        self.assertIn("outside approved local tool roots", errors)

    def test_open_session_inspection_only_reads_blender_state(self):
        selected = [SimpleNamespace(name="Clamp"), SimpleNamespace(name="Frame")]
        bpy = SimpleNamespace(
            context=SimpleNamespace(
                scene=SimpleNamespace(
                    name="PIMM-50G",
                    unit_settings=SimpleNamespace(
                        system="METRIC", length_unit="MILLIMETERS", scale_length=0.001
                    ),
                ),
                view_layer=SimpleNamespace(
                    name="ViewLayer",
                    objects=SimpleNamespace(active=SimpleNamespace(name="Frame")),
                ),
                selected_objects=selected,
            ),
            data=SimpleNamespace(
                filepath=r"M:\masters\PIMM-50G-MASTER.blend",
                is_dirty=True,
                libraries=[SimpleNamespace(filepath="//PIMM-MATERIAL-LIBRARY.blend")],
            ),
        )

        self.assertEqual(
            inspect_open_session(bpy),
            {
                "filepath": r"M:\masters\PIMM-50G-MASTER.blend",
                "dirty": True,
                "scene": "PIMM-50G",
                "view_layer": "ViewLayer",
                "unit_system": "METRIC",
                "length_unit": "MILLIMETERS",
                "scale_length": 0.001,
                "selected_objects": ["Clamp", "Frame"],
                "active_object": "Frame",
                "libraries": ["//PIMM-MATERIAL-LIBRARY.blend"],
            },
        )


if __name__ == "__main__":
    unittest.main()
