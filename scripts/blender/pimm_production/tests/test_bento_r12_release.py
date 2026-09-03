import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PIL import Image

from scripts.blender.pimm_production import export_bento_r12_release as release
from scripts.blender.pimm_production import blender_bento_white_detail_final as detail
from scripts.blender.pimm_production.io_contract import sha256_file


class DetailReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.assets = self.root / 'assets'
        self.assets.mkdir()
        self.output = self.root / 'native'
        directory = self.output / 'configuration'
        directory.mkdir(parents=True)
        self.approval = self.root / 'approval.json'
        self.approval.write_text('{}')
        self.enterContext(patch.object(release, 'REPO_ROOT', self.root))
        self.enterContext(patch.object(detail, 'OUTPUT', self.output))
        self.enterContext(patch.object(detail, 'APPROVAL', self.approval))
        records = []
        for shot in ('capacity', 'controls', 'tooling', 'configuration'):
            path = self.assets / (shot + '.webp')
            path.write_bytes(b'original-' + shot.encode())
            records.append({'shot': shot, 'filename': path.name, 'sha256': sha256_file(path),
                            'approval': self.approval.name, 'approval_sha256': sha256_file(self.approval)})
        video = self.assets / 'complete.mp4'
        video.write_bytes(b'approved-native-video')
        self.source = {'generation': 'bento-20260903-r11-motion', 'assets': records,
                       'animation': {'filename': video.name, 'sha256': sha256_file(video)}}
        (self.assets / 'pimm-bento-r11-motion.v1.json').write_text(json.dumps(self.source))
        self.contract = {'generation': 'bento-20260903-r12-white-detail', 'native_size': [16, 8],
                         'scene_sha256': 'scene', 'master_sha256': 'master'}
        self.enterContext(patch.object(detail, 'detail_contract', return_value=self.contract))
        native = directory / 'frame-0001.png'
        Image.new('RGB', (16, 8), (150, 160, 170)).save(native)
        self.receipt = {'generation': self.contract['generation'], 'shot': 'configuration',
                        'size': [16, 8], 'master_sha256': 'master', 'scene_sha256': 'scene',
                        'approval_sha256': sha256_file(self.approval),
                        'frames': [{'frame': 1, 'native_path': str(native), 'native_sha256': sha256_file(native),
                                    'scene_sha256': 'scene', 'approval_sha256': sha256_file(self.approval)}]}
        (directory / 'final.json').write_text(json.dumps(self.receipt))

    def test_new_configuration_preserves_other_stills_and_animation(self):
        release.export()
        result = json.loads((self.assets / 'pimm-bento-r12-assets.v1.json').read_text())
        self.assertEqual(result['assets'][:3], self.source['assets'][:3])
        self.assertEqual(result['animation'], self.source['animation'])
        item = result['assets'][3]
        self.assertEqual(item['generation'], self.contract['generation'])
        with Image.open(item['native_path']) as original, Image.open(self.assets / item['filename']) as encoded:
            self.assertEqual(original.convert('RGB').tobytes(), encoded.convert('RGB').tobytes())

    def test_prior_animation_hash_is_enforced(self):
        (self.assets / 'complete.mp4').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            release.export()

    def test_immutable_manifest_blocks_all_new_writes(self):
        (self.assets / 'pimm-bento-r12-assets.v1.json').write_text('keep')
        with self.assertRaises(FileExistsError):
            release.export()
        self.assertFalse((self.assets / 'pimm-bento-20260903-r12-30g-configuration.webp').exists())

    def test_exact_native_dimensions_are_required(self):
        self.contract['native_size'] = [2400, 1200]
        with self.assertRaises(ValueError):
            release.export()

    def test_approval_change_during_export_cannot_publish_manifest(self):
        original_save = Image.Image.save
        def change_approval(image, *args, **kwargs):
            original_save(image, *args, **kwargs)
            self.approval.write_text('{"changed": true}')
        with patch.object(Image.Image, 'save', change_approval):
            with self.assertRaises(ValueError):
                release.export()
        self.assertFalse((self.assets / 'pimm-bento-r12-assets.v1.json').exists())


if __name__ == '__main__':
    unittest.main()
