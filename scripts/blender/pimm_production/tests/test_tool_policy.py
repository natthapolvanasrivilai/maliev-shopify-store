"""Contract tests for the free, local PIMM production tool lock."""

from __future__ import annotations

from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace
import unittest

from scripts.blender.pimm_production.blender_session_preflight import (
    APPROVED_PREFLIGHT_PATH,
    inspect_open_session,
    main as run_preflight,
    validate_invocation,
)
from scripts.blender.pimm_production.tool_policy import (
    LOCK_SCHEMA,
    PRODUCTION_VENV_ROOT,
    validate_tool_lock,
)


class ToolPolicyTests(unittest.TestCase):
    def _valid_lock_payload(self):
        return {
            "schema": LOCK_SCHEMA,
            "tools": [
                {
                    "id": "blender",
                    "version": "5.2.0",
                    "license": "GPL-3.0-or-later",
                    "execution": "local",
                    "path": r"D:\Blender 5.2\blender.exe",
                    "sha256": "A" * 64,
                },
                {
                    "id": "blender-mcp",
                    "version": "a" * 40,
                    "license": "GPL-3.0-or-later",
                    "execution": "local",
                    "path": r"C:\Users\natth\blender_mcp",
                    "sha256": "B" * 64,
                },
                {
                    "id": "python",
                    "version": "3.11.9",
                    "license": "PSF-2.0",
                    "execution": "local",
                    "path": str(PRODUCTION_VENV_ROOT / "Scripts" / "python.exe"),
                    "sha256": "C" * 64,
                },
                {
                    "id": "pillow",
                    "version": "12.2.0",
                    "license": "MIT-CMU",
                    "execution": "local",
                    "path": str(PRODUCTION_VENV_ROOT / "Lib" / "site-packages" / "PIL" / "__init__.py"),
                    "sha256": "D" * 64,
                },
            ],
            "license_evidence": {
                "blender-mcp": {"path": r"C:\Users\natth\blender_mcp\LICENSE", "sha256": "E" * 64}
            },
            "asset_provenance": {
                "pinned_hdri": {
                    "path": "assets/hdri/studio_kontrast_04_4k.exr",
                    "sha256": "9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06",
                    "license": "CC0-1.0",
                }
            },
        }

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
        payload = self._valid_lock_payload()

        self.assertEqual(validate_tool_lock(payload), [])

    def test_lock_binds_the_pinned_hdri_as_local_cc0_provenance(self):
        """Catches a lock that lets the campaign HDRI hash drift outside local provenance."""

        payload = self._valid_lock_payload()
        self.assertEqual(validate_tool_lock(payload), [])

    def test_lock_rejects_partial_schema_missing_checksum_and_network_endpoint(self):
        payload = self._valid_lock_payload()
        payload["schema"] = "pimm-free-tools-lock/v0"
        payload["tools"] = payload["tools"][:-1]
        payload["tools"][0]["sha256"] = "not-a-hash"
        payload["tools"][0]["endpoint"] = "http://127.0.0.1:8000"

        errors = "\n".join(validate_tool_lock(payload))

        self.assertIn("unsupported schema", errors)
        self.assertIn("required tool IDs", errors)
        self.assertIn("invalid sha256", errors)
        self.assertIn("network-bearing field", errors)

    def test_lock_rejects_every_cross_assigned_tool_license(self):
        expected_licenses = {
            "blender": "GPL-3.0-or-later",
            "blender-mcp": "GPL-3.0-or-later",
            "python": "PSF-2.0",
            "pillow": "MIT-CMU",
        }

        for tool_id, expected_license in expected_licenses.items():
            for wrong_license in sorted(set(expected_licenses.values()) - {expected_license}):
                with self.subTest(tool_id=tool_id, wrong_license=wrong_license):
                    payload = deepcopy(self._valid_lock_payload())
                    next(tool for tool in payload["tools"] if tool["id"] == tool_id)[
                        "license"
                    ] = wrong_license

                    self.assertIn(
                        f"{tool_id}: expected license {expected_license}",
                        validate_tool_lock(payload),
                    )

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

    def test_blender_script_entrypoint_returns_normally(self):
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
                selected_objects=[SimpleNamespace(name="Frame")],
            ),
            data=SimpleNamespace(
                filepath=r"M:\masters\PIMM-50G-MASTER.blend",
                is_dirty=True,
                libraries=[SimpleNamespace(filepath="//PIMM-MATERIAL-LIBRARY.blend")],
            ),
        )
        script = Path(__file__).resolve().parents[1] / "blender_session_preflight.py"
        previous_bpy = sys.modules.get("bpy")
        previous_argv = sys.argv
        sys.modules["bpy"] = bpy
        sys.argv = [
            "blender",
            "-b",
            "factory-startup.blend",
            "--python-exit-code",
            "1",
            "-P",
            str(APPROVED_PREFLIGHT_PATH),
        ]
        stdout = StringIO()

        try:
            try:
                with redirect_stdout(stdout):
                    runpy.run_path(str(script), run_name="__main__")
            except SystemExit as error:
                self.fail(f"Blender script entrypoint raised SystemExit({error.code!r})")
        finally:
            if previous_bpy is None:
                del sys.modules["bpy"]
            else:
                sys.modules["bpy"] = previous_bpy
            sys.argv = previous_argv

        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "active_object": "Frame",
                "dirty": True,
                "filepath": r"M:\masters\PIMM-50G-MASTER.blend",
                "length_unit": "MILLIMETERS",
                "libraries": ["//PIMM-MATERIAL-LIBRARY.blend"],
                "scale_length": 0.001,
                "scene": "PIMM-50G",
                "selected_objects": ["Frame"],
                "unit_system": "METRIC",
                "view_layer": "ViewLayer",
            },
        )

    def test_preflight_rejects_render_and_save_flags_before_the_delimiter(self):
        with self.assertRaisesRegex(SystemExit, "mutation flags"):
            run_preflight(
                [
                    "blender",
                    "-b",
                    r"M:\masters\PIMM-50G-MASTER.blend",
                    "-f",
                    "1",
                    "--save-as-mainfile=unsafe.blend",
                    "-P",
                    "blender_session_preflight.py",
                ]
            )

    def test_preflight_permits_only_the_exact_checked_in_python_script(self):
        approved_command = [
            "blender",
            "-b",
            r"M:\masters\PIMM-50G-MASTER.blend",
            "--python-exit-code",
            "1",
            "-P",
            str(APPROVED_PREFLIGHT_PATH),
        ]
        self.assertEqual(validate_invocation(approved_command), [])

        aliases_and_bypasses = [
            (["blender", "-P", "arbitrary.py"], "approved checked-in script"),
            (["blender", "-P"], "missing script path"),
            (
                ["blender", "-P", str(APPROVED_PREFLIGHT_PATH), "-P", str(APPROVED_PREFLIGHT_PATH)],
                "exactly one -P",
            ),
            (
                [
                    "blender",
                    "-P",
                    str(APPROVED_PREFLIGHT_PATH.parent) + r"\.\blender_session_preflight.py",
                ],
                "canonical",
            ),
            (["blender", "--python-expr", "print('unsafe')"], "mutation flags"),
        ]
        for command, expected_error in aliases_and_bypasses:
            with self.subTest(command=command):
                self.assertIn(expected_error, "\n".join(validate_invocation(command)))

    def test_preflight_rejects_a_cli_invocation_without_the_checked_in_script(self):
        errors = validate_invocation(["blender", "-b"])

        self.assertIn("exactly one -P", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
