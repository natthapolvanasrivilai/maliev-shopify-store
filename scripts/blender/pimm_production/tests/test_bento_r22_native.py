import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from scripts.blender.pimm_production import blender_bento_r22_native as native
from scripts.blender.pimm_production.io_contract import sha256_file


class NativeMotionTests(unittest.TestCase):
    def test_all_pose_paths_are_unique_and_preserve_seven_pitch_rows(self):
        root = Path('final')
        paths = [native.frame_path(root, 'configuration', index) for index in range(1, 841)]
        self.assertEqual(len(set(paths)), 840)
        self.assertEqual(paths[0], root / 'configuration/row-00/frame-0001.png')
        self.assertEqual(paths[-1], root / 'configuration/row-06/frame-0120.png')
        self.assertEqual(native.frame_path(root, 'capacity', 192), root / 'capacity/frame-0192.png')

    def test_invalid_shot_and_indices_fail_closed(self):
        for shot, frame in [('other', 1), ('capacity', 193), ('tooling', 0), ('configuration', 841), ('capacity', True)]:
            with self.assertRaises(ValueError):
                native.frame_path(Path('final'), shot, frame)

    def test_native_receipt_pins_authority_dimensions_and_both_image_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'frame-0001.png'
            output.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 8 + struct.pack('>II', 1600, 2200))
            exr = output.with_suffix('.exr')
            exr.write_bytes(b'\x76\x2f\x31\x01native float fixture')
            authority = {'approval_sha256': 'approved'}
            record = {'index': 1, 'path': str(output), 'sha256': sha256_file(output),
                      'exr_path': str(exr), 'exr_sha256': sha256_file(exr), 'authority': authority}
            native.validate_frame(record, output, [1600, 2200], authority, 1)
            for size, expected, index in [([400, 550], authority, 1), ([1600, 2200], {}, 1), ([1600, 2200], authority, 2)]:
                with self.assertRaises(ValueError):
                    native.validate_frame(record, output, size, expected, index)
            exr.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                native.validate_frame(record, output, [1600, 2200], authority, 1)

    def test_unapproved_or_partial_scope_never_reads_render_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            approval = Path(directory) / 'approval.json'
            for data in [{'decision': 'pending', 'shots': list(native.SHOTS)}, {'decision': 'approved', 'shots': ['capacity']}]:
                approval.write_text(json.dumps(data))
                with patch.object(native, 'APPROVAL', approval):
                    with self.assertRaisesRegex(ValueError, 'owner approval'):
                        native.approved_review()


if __name__ == '__main__':
    unittest.main()
