import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.blender.pimm_production import export_bento_motion_release as release
from scripts.blender.pimm_production.io_contract import sha256_file


class MotionReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.assets = self.root / 'assets'
        self.assets.mkdir()
        self.output = self.root / 'native'
        self.orbit_dir = self.output / 'controls-orbit'
        self.orbit_dir.mkdir(parents=True)
        self.enterContext(patch.object(release, 'REPO_ROOT', self.root))
        self.enterContext(patch.object(release, 'OUTPUT', self.output))
        approval = self.root / 'approval.json'
        approval.write_text('{}')
        assets = []
        for shot in ('capacity', 'controls', 'tooling', 'configuration'):
            path = self.assets / f'{shot}.webp'
            path.write_bytes(b'approved-still-' + shot.encode())
            assets.append({'shot': shot, 'filename': path.name, 'sha256': sha256_file(path),
                           'approval': approval.name, 'approval_sha256': sha256_file(approval),
                           'native_sha256': 'first-frame', 'scene_sha256': 'scene'})
        self.stills = {'generation': 'bento-20260903-r11-stills', 'assets': assets}
        (self.assets / 'pimm-bento-r11-stills.v1.json').write_text(json.dumps(self.stills))
        self.orbit = {'scene_sha256': 'scene', 'approval_sha256': sha256_file(approval),
                      'size': [2400, 1200], 'frames': [{'native_sha256': 'first-frame'}]}
        self.enterContext(patch.object(release, 'final_for', return_value=self.orbit))
        manifest = self.orbit_dir / 'final.json'
        manifest.write_text(json.dumps(self.orbit))
        self.video = self.orbit_dir / 'pimm-bento-20260903-r10-30g-controls-orbit.mp4'
        self.video.write_bytes(b'complete-encoded-video')
        self.receipt = {'filename': self.video.name, 'path': str(self.video), 'sha256': sha256_file(self.video),
                        'native_manifest': str(manifest), 'native_manifest_sha256': sha256_file(manifest),
                        'approval_sha256': self.orbit['approval_sha256'], 'scene_sha256': 'scene',
                        'size': [2400, 1200], 'frames': 192, 'fps': 24, 'duration_ms': 8000}
        self.write_receipt()

    def write_receipt(self):
        self.video.with_suffix('.json').write_text(json.dumps(self.receipt))

    def test_complete_release_preserves_all_white_studio_stills(self):
        release.export()
        result = json.loads((self.assets / 'pimm-bento-r11-motion.v1.json').read_text())
        self.assertEqual(result['assets'], self.stills['assets'])
        self.assertEqual((self.assets / self.video.name).read_bytes(), self.video.read_bytes())
        self.assertEqual(result['animation']['frames'], 192)

    def test_partial_video_cannot_publish(self):
        self.receipt['frames'] = 128
        self.write_receipt()
        with self.assertRaises(ValueError):
            release.export()
        self.assertFalse((self.assets / self.video.name).exists())

    def test_poster_mismatch_cannot_publish(self):
        self.orbit['frames'][0]['native_sha256'] = 'other-frame'
        with self.assertRaises(AssertionError):
            release.export()

    def test_existing_release_is_never_overwritten(self):
        existing = self.assets / 'pimm-bento-r11-motion.v1.json'
        existing.write_text('keep')
        with self.assertRaises(FileExistsError):
            release.export()
        self.assertEqual(existing.read_text(), 'keep')
        self.assertFalse((self.assets / self.video.name).exists())

    def test_changed_encoded_bytes_cannot_publish(self):
        self.video.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            release.export()


if __name__ == '__main__':
    unittest.main()
