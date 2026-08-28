import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const manifestPath = join(root, 'assets', 'pimm-unified-render-assets.v1.json');
const expectedLineage = new Map([
  ['pimm-machine-30g-hero-front.webp', {
    dimensions: [1800, 2200], machine: '30G', shot: 'hero-front',
    proof_id: 'proof-20260828T130126Z-09aebd4', release_id: 'release-2026-08-28-r21',
    shot_id: 'pimm-30g--hero--front',
    scene_sha256: '09AEBD4D6DA5B482B7B1281C7CE2A4043C4D9F168ECD5EE01FE04C11A5585263',
    sha256: 'B48A7F6DD06CF193BD276DE7F96A3E165EA15EB7EB193C8E1FF18C505C033169',
    native_source: {
      path: 'renders/final/release-2026-08-28-r21/pimm-30g--hero--front/pimm-30g--hero--front--transparent.webp',
      sha256: '0D9E47149CE31E8D9EEEF9F897D97B47BD135A91539C1701ABB79520A9D4F8BD',
    },
  }],
  ['pimm-machine-30g-overview-three-quarter.webp', {
    dimensions: [2400, 1800], machine: '30G', shot: 'overview-three-quarter',
    proof_id: 'proof-20260826T230700Z-3464e7e', release_id: 'release-2026-08-27-r15',
    shot_id: 'pimm-30g--overview--three-quarter',
    scene_sha256: '3464E7EF56DFEA64D1247D5293CF81E41CD782BD296D1357FD9958B8F7915E58',
    sha256: '266E8ACD1C509CD036C6E846ED7A69FBB22A01B753AF54E1A7BD3CF933079AE2',
    native_source: {
      path: 'renders/final/release-2026-08-27-r15/pimm-30g--overview--three-quarter/pimm-30g--overview--three-quarter--transparent.webp',
      sha256: 'D31B1202D91C1D0B8C19E641BB8BAD21D3BF15513040EBBAD0C70A3093133EA3',
    },
  }],
  ['pimm-machine-30g-engineering-controls.webp', {
    dimensions: [2400, 1800], machine: '30G', shot: 'engineering-controls',
    proof_id: 'proof-20260826T230701Z-33d25d3', release_id: 'release-2026-08-27-r16',
    shot_id: 'pimm-30g--engineering--controls',
    scene_sha256: '33D25D3E0A736F2E121A7165855B0CEA80B60BB4F95804ED0DB30296C95A6D58',
    sha256: '74A47A59028A83BDE2F4FF8541CD9F2BF4D7F0BFEC592C1A4E16B7C54E907633',
    native_source: {
      path: 'renders/final/release-2026-08-27-r16/pimm-30g--engineering--controls/pimm-30g--engineering--controls--transparent.webp',
      sha256: 'BAF4052C78E8B4A54EC9A634ADD3909B19B16EC9FAD6F962C022110D21A55B06',
    },
  }],
  ['pimm-machine-30g-tooling-front-detail.webp', {
    dimensions: [2400, 1800], machine: '30G', shot: 'tooling-front-detail',
    proof_id: 'proof-20260827T024726Z-35c918c', release_id: 'release-2026-08-27-r17',
    shot_id: 'pimm-30g--tooling--front-detail',
    scene_sha256: '35C918C40497272ED877D62582129D305FDECD474F006E122EC17798623562C3',
    sha256: '46EB32B932BF0C1C5B12FD6DCBCF0C260FA17C1E07ABC64BC96EF22533AA78B0',
    native_source: {
      path: 'renders/final/release-2026-08-27-r17/pimm-30g--tooling--front-detail/pimm-30g--tooling--front-detail--transparent.webp',
      sha256: '77B18759BF7F219E92D468579215A0D79586BC0580869B7FF182633D36E17300',
    },
  }],
  ['pimm-machine-50g-hero-front.webp', {
    dimensions: [1800, 2200], machine: '50G', shot: 'hero-front',
    proof_id: 'proof-20260828T130126Z-13d7d14', release_id: 'release-2026-08-28-r22',
    shot_id: 'pimm-50g--hero--front',
    scene_sha256: '13D7D14BF41BFE3EA3161E63BB71642C8DC962A9B4BAA2159E4559E819791495',
    sha256: '02B50CEC0ED052CDDD7E0B02D1CB028E4ED4662CB06821557BE637CE6EC75530',
    native_source: {
      path: 'renders/final/release-2026-08-28-r22/pimm-50g--hero--front/pimm-50g--hero--front--transparent.webp',
      sha256: '0A4A76089A19AD821504BDDF7D2CD450277093BE35A72ACD400E56D937828C92',
    },
  }],
  ['pimm-machine-50g-overview-three-quarter.webp', {
    dimensions: [2400, 1800], machine: '50G', shot: 'overview-three-quarter',
    proof_id: 'proof-20260826T230703Z-b2b9edf', release_id: 'release-2026-08-27-r18',
    shot_id: 'pimm-50g--overview--three-quarter',
    scene_sha256: 'B2B9EDF3FB1906DD4C43B75455610068EC7666F26F2DE45DD83B881966609B24',
    sha256: 'D79BE1CDEC7601D4620B65E5DA78CE745C990469A57F9B61AA49B0052E700D8C',
    native_source: {
      path: 'renders/final/release-2026-08-27-r18/pimm-50g--overview--three-quarter/pimm-50g--overview--three-quarter--transparent.webp',
      sha256: '852A9D7048F4477D2F9783E2297E5CF5A48C82594AC6F94698D88A8D564CED90',
    },
  }],
  ['pimm-machine-50g-engineering-controls.webp', {
    dimensions: [2400, 1800], machine: '50G', shot: 'engineering-controls',
    proof_id: 'proof-20260826T230704Z-52a6358', release_id: 'release-2026-08-27-r19',
    shot_id: 'pimm-50g--engineering--controls',
    scene_sha256: '52A6358F015BDC9AA8872357C0E9BD96EF107BA0DD729BC5B4F7DA93C950A95F',
    sha256: '4E9FB6CA7262C555C3AD9E745C76848B6B59803E650F7127D71431762D943651',
    native_source: {
      path: 'renders/final/release-2026-08-27-r19/pimm-50g--engineering--controls/pimm-50g--engineering--controls--transparent.webp',
      sha256: '6156EFE6A367DE0D2B74EFE938DC2B1E50A2F85E53B5238D205EE520FA8BCAEA',
    },
  }],
  ['pimm-machine-50g-tooling-front-detail.webp', {
    dimensions: [2400, 1800], machine: '50G', shot: 'tooling-front-detail',
    proof_id: 'proof-20260827T024727Z-1db04e0', release_id: 'release-2026-08-27-r20',
    shot_id: 'pimm-50g--tooling--front-detail',
    scene_sha256: '1DB04E0229DFDC64C94AB6A8ED1D06711D169B5BEE43C1780B2B7D12A6C8333A',
    sha256: '3B08417EA78E68C720873BF7E7F45634D85C77BED068E88EFC455309CF6DB589',
    native_source: {
      path: 'renders/final/release-2026-08-27-r20/pimm-50g--tooling--front-detail/pimm-50g--tooling--front-detail--transparent.webp',
      sha256: '319A6901CCAB6DD8C85140844B7D50DD3DFC8970536F366C346F66A52D85B58D',
    },
  }],
]);

const expectedRolePolicy = new Map([
  ['hero-front', { dimensions: [1800, 2200], alpha: true, orientation: 'portrait' }],
  ['overview-three-quarter', { dimensions: [2400, 1800], alpha: true, orientation: 'landscape' }],
  ['engineering-controls', { dimensions: [2400, 1800], alpha: true, orientation: 'landscape' }],
  ['tooling-front-detail', { dimensions: [2400, 1800], alpha: true, orientation: 'landscape' }],
]);

const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();
const clone = (value) => JSON.parse(JSON.stringify(value));
const sortedKeys = (value) => Object.keys(value).sort();
const readUint24LE = (bytes, offset) => bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16);

const webpMetadata = (bytes) => {
  assert.equal(bytes.subarray(0, 4).toString('ascii'), 'RIFF', 'asset is not RIFF');
  assert.equal(bytes.subarray(8, 12).toString('ascii'), 'WEBP', 'asset is not WebP');
  for (let offset = 12; offset + 8 <= bytes.length;) {
    const type = bytes.subarray(offset, offset + 4).toString('ascii');
    const length = bytes.readUInt32LE(offset + 4);
    const data = offset + 8;
    if (type === 'VP8X') {
      return {
        alpha: (bytes[data] & 0x10) !== 0,
        dimensions: [readUint24LE(bytes, data + 4) + 1, readUint24LE(bytes, data + 7) + 1],
      };
    }
    if (type === 'VP8L') {
      assert.equal(bytes[data], 0x2f, 'invalid VP8L signature');
      return {
        alpha: true,
        dimensions: [
          1 + bytes[data + 1] + ((bytes[data + 2] & 0x3f) << 8),
          1 + (bytes[data + 2] >> 6) + (bytes[data + 3] << 2) + ((bytes[data + 4] & 0x0f) << 10),
        ],
      };
    }
    if (type === 'VP8 ') {
      assert.equal(bytes.subarray(data + 3, data + 6).toString('hex'), '9d012a', 'invalid VP8 signature');
      return {
        alpha: false,
        dimensions: [bytes.readUInt16LE(data + 6) & 0x3fff, bytes.readUInt16LE(data + 8) & 0x3fff],
      };
    }
    offset = data + length + (length % 2);
  }
  assert.fail('WebP has no supported image chunk');
};

const validateLineage = (manifest, { checkFiles = false } = {}) => {
  assert.deepEqual(sortedKeys(manifest), ['assets', 'schema']);
  assert.equal(manifest.schema, 'maliev.pimm-unified-render-assets/v1');
  assert.ok(Array.isArray(manifest.assets));
  assert.equal(manifest.assets.length, 8);

  const names = new Set();
  const sourcePaths = new Set();
  const roles = new Set();
  for (const entry of manifest.assets) {
    assert.deepEqual(sortedKeys(entry), [
      'dimensions', 'machine', 'name', 'native_source', 'proof_id',
      'release_id', 'scene_sha256', 'sha256', 'shot', 'shot_id',
    ]);
    assert.deepEqual(sortedKeys(entry.native_source), ['path', 'sha256']);
    assert.ok(!names.has(entry.name), `duplicate asset ${entry.name}`);
    assert.ok(!sourcePaths.has(entry.native_source.path), `duplicate source ${entry.native_source.path}`);
    assert.ok(!roles.has(`${entry.machine}/${entry.shot}`), `duplicate role ${entry.machine}/${entry.shot}`);
    names.add(entry.name);
    sourcePaths.add(entry.native_source.path);
    roles.add(`${entry.machine}/${entry.shot}`);

    assert.ok(['30G', '50G'].includes(entry.machine), `invalid machine ${entry.machine}`);
    assert.ok(['hero-front', 'overview-three-quarter', 'engineering-controls', 'tooling-front-detail'].includes(entry.shot), `invalid shot ${entry.shot}`);
    assert.match(entry.proof_id, /^proof-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{7}$/);
    assert.match(entry.release_id, /^release-[0-9]{4}-[0-9]{2}-[0-9]{2}-r[0-9]{2}$/);
    assert.match(entry.scene_sha256, /^[0-9A-F]{64}$/);
    assert.match(entry.sha256, /^[0-9A-F]{64}$/);
    assert.match(entry.native_source.sha256, /^[0-9A-F]{64}$/);
    assert.match(entry.native_source.path, /^renders\/final\/release-[^/]+\/pimm-[^/]+\/pimm-[^/]+--transparent\.webp$/);

    const expected = expectedLineage.get(entry.name);
    assert.ok(expected, `unexpected asset ${entry.name}`);
    assert.deepEqual(entry, { name: entry.name, ...expected });

    if (checkFiles) {
      const path = join(root, 'assets', entry.name);
      const bytes = readFileSync(path);
      assert.ok(statSync(path).size > 20_000, `${entry.name} is unexpectedly small`);
      assert.equal(sha256(bytes), entry.sha256, `${entry.name} hash drifted`);
      const metadata = webpMetadata(bytes);
      assert.deepEqual(metadata.dimensions, entry.dimensions, `${entry.name} dimensions drifted`);
      assert.equal(metadata.alpha, true, `${entry.name} lost its alpha channel`);
    }
  }
  assert.deepEqual([...names].sort(), [...expectedLineage.keys()].sort());
};

const fixtureManifest = () => ({
  schema: 'maliev.pimm-unified-render-assets/v1',
  assets: [...expectedLineage].map(([name, entry]) => ({ name, ...clone(entry) })),
});

test('committed lineage binds the exact eight portable WebP assets', () => {
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  validateLineage(manifest, { checkFiles: true });
});

test('released roles remain eligible for their responsive presentation slots', () => {
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  for (const entry of manifest.assets) {
    const policy = expectedRolePolicy.get(entry.shot);
    assert.ok(policy, `missing role policy for ${entry.shot}`);
    assert.deepEqual(entry.dimensions, policy.dimensions, `${entry.name} no longer fits ${entry.shot}`);
    assert.equal(
      entry.dimensions[0] > entry.dimensions[1],
      policy.orientation === 'landscape',
      `${entry.name} orientation drifted`,
    );
    assert.equal(
      webpMetadata(readFileSync(join(root, 'assets', entry.name))).alpha,
      policy.alpha,
      `${entry.name} alpha policy drifted`,
    );
  }
});

test('lineage validation rejects identity and authority mutations', () => {
  const mutations = [
    ['asset hash', (value) => { value.assets[0].sha256 = 'F'.repeat(64); }],
    ['dimensions', (value) => { value.assets[0].dimensions = [1, 1]; }],
    ['proof', (value) => { value.assets[0].proof_id = 'proof-20260825T030400Z-deadbee'; }],
    ['release', (value) => { value.assets[0].release_id = 'release-2026-08-25-r99'; }],
    ['scene hash', (value) => { value.assets[0].scene_sha256 = 'F'.repeat(64); }],
    ['source hash', (value) => { value.assets[0].native_source.sha256 = 'F'.repeat(64); }],
    ['source path', (value) => { value.assets[0].native_source.path = 'renders/final/counterfeit.webp'; }],
    ['extra entry', (value) => { value.assets.push(clone(value.assets[0])); }],
    ['missing entry', (value) => { value.assets.pop(); }],
  ];
  for (const [name, mutate] of mutations) {
    const value = fixtureManifest();
    mutate(value);
    assert.throws(() => validateLineage(value), undefined, name);
  }
});

test('canonical hero scenes match released lineage when the Blender workspace is available', {
  skip: !process.env.PIMM_RENDER_CANONICAL_ROOT,
}, () => {
  const canonicalRoot = process.env.PIMM_RENDER_CANONICAL_ROOT;
  for (const [name, expected] of expectedLineage) {
    if (expected.shot !== 'hero-front') continue;
    const scenePath = join(canonicalRoot, 'scenes', 'stills', `${expected.shot_id}.blend`);
    assert.equal(
      sha256(readFileSync(scenePath)),
      expected.scene_sha256,
      `${name} points to a stale hero scene release`,
    );
  }
});

const probe = (path) => JSON.parse(execFileSync(
  'ffprobe',
  [
    '-v', 'error',
    '-select_streams', 'v:0',
    '-show_entries', 'stream=codec_name,width,height,pix_fmt',
    '-of', 'json',
    path,
  ],
  { encoding: 'utf8' },
)).streams[0];

const alphaRange = (path, width, height) => {
  const rgba = execFileSync(
    'ffmpeg',
    [
      '-hide_banner', '-loglevel', 'error',
      '-i', path,
      '-frames:v', '1',
      '-f', 'rawvideo',
      '-pix_fmt', 'rgba',
      'pipe:1',
    ],
    { maxBuffer: (width * height * 4) + 1024 },
  );
  let min = 255;
  let max = 0;
  for (let index = 3; index < rgba.length; index += 4) {
    min = Math.min(min, rgba[index]);
    max = Math.max(max, rgba[index]);
  }
  return { min, max };
};

test('local decoder verifies WebP pixels and alpha extrema', {
  skip: process.env.PIMM_RENDER_DECODER_CHECK !== '1',
}, () => {
  for (const [name, expected] of expectedLineage) {
    const path = join(root, 'assets', name);
    const metadata = probe(path);
    assert.equal(metadata.codec_name, 'webp', `${name} codec drifted`);
    assert.deepEqual([metadata.width, metadata.height], expected.dimensions, `${name} dimensions drifted`);
    const alpha = alphaRange(path, metadata.width, metadata.height);
    assert.ok(alpha.min < 255, `${name} lost transparent pixels`);
    assert.equal(alpha.max, 255, `${name} has no fully opaque subject pixels`);
  }
});
