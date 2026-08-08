import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const read = (path) => readFileSync(join(root, path), 'utf8');

test('alpha videos replace their poster layer while playing', () => {
  const liquid = read('snippets/maliev-pimm-30g-chapter.liquid');
  const css = read('assets/maliev-pimm-30g.css');
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');
  const script = read('assets/maliev-pimm-30g.js');

  assert.doesNotMatch(liquid, /<video\b[^>]*\bposter=/);
  assert.match(css, /\.pimm30-stage__layer\.has-active-video \.pimm30-stage__poster/);
  assert.match(keynoteCss, /\.is-hero-pending[\s\S]*?\.pimm30-stage__poster[\s\S]*?visibility:\s*visible\s*!important/);
  assert.match(script, /video\.play\(\)\s*\.then\(\(\) => \{[\s\S]*?classList\.add\('has-active-video'\)/);
  assert.doesNotMatch(script, /classList\.add\('has-active-video'\);\s*video\.play\(\)/);
  assert.match(script, /classList\.add\('has-active-video'\)/);
  assert.match(script, /classList\.remove\('has-active-video'\)/);
});

test('transparent presentation media is never hard-cropped by the stage', () => {
  const css = read('assets/maliev-pimm-30g.css');
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');

  assert.doesNotMatch(css, /object-fit:\s*cover/);
  assert.doesNotMatch(css, /clip-path:\s*inset\(/);
  assert.match(
    keynoteCss,
    /\.pimm30-story\s+\.pimm30-stage\s+>\s*\.pimm30-stage__layer\[data-pimm30-layer=['"]pimm30-overview['"]\][\s\S]*?inset:\s*0\s*!important/
  );
  assert.match(keynoteCss, /\.pimm30-chapter--hero \.pimm30-scroll-cue[\s\S]*?position:\s*absolute\s*!important/);
  assert.match(keynoteCss, /\.pimm30-chapter--hero \.pimm30-scroll-cue[\s\S]*?left:\s*50%\s*!important/);
  assert.match(keynoteCss, /\.pimm30-chapter--hero \.pimm30-scroll-cue[\s\S]*?transform:\s*translateX\(-50%\)\s*!important/);
  assert.match(keynoteCss, /data-active-chapter=['"]pimm30-overview['"][\s\S]*?\.pimm30-scroll-cue[\s\S]*?position:\s*fixed\s*!important/);
  assert.match(keynoteCss, /@media \(max-width: 539px\), \(orientation: portrait\)[\s\S]*?\.pimm30-stage__poster[\s\S]*?mask-image:\s*linear-gradient\(to right/);
});

test('hero art direction keeps wide media on landscape screens', () => {
  const liquid = read('snippets/maliev-pimm-30g-chapter.liquid');
  const section = read('sections/maliev-pimm-30g-story.liquid');
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');
  const script = read('assets/maliev-pimm-30g.js');

  assert.match(section, /<\/div>\s*\{%- if role == 'overview' -%\}[\s\S]*?class="pimm30-scroll-cue"/);
  assert.match(liquid, /assign stage_poster_url = desktop_poster_url[\s\S]*?if stage_poster_url == blank[\s\S]*?assign stage_poster_url = mobile_poster_url/);
  assert.doesNotMatch(liquid, /when 'overview',[\s\S]*?assign stage_poster_url = mobile_poster_url/);
  assert.match(keynoteCss, /@media \(min-width: 540px\) and \(orientation: landscape\)[\s\S]*?\.pimm30-stage__video--desktop[\s\S]*?display: block !important[\s\S]*?\.pimm30-stage__video--mobile[\s\S]*?display: none !important/);
  assert.match(script, /matchMedia\('\(max-width: 539px\), \(orientation: portrait\)'\)/);
  assert.doesNotMatch(script, /PORTRAIT_STAGE_ROLES/);
});

test('configuration media supports pointer and keyboard scrubbing', () => {
  const liquid = read('snippets/maliev-pimm-30g-chapter.liquid');
  const css = read('assets/maliev-pimm-30g.css');
  const script = read('assets/maliev-pimm-30g.js');

  assert.match(liquid, /data-pimm30-turntable/);
  assert.match(liquid, /tabindex="-1"/);
  assert.match(css, /touch-action: pan-y/);
  assert.match(css, /\.pimm30-story__chapters\s*{[\s\S]*?pointer-events: none/);
  assert.match(css, /\.pimm30-chapter__content\s*{[\s\S]*?pointer-events: auto/);
  assert.match(script, /addEventListener\('pointermove'/);
  assert.match(script, /layer\.tabIndex = active \? 0 : -1/);
  assert.match(script, /ArrowLeft/);
  assert.match(script, /video\.currentTime = nextTime/);
});

test('configuration dragging reverses horizontal pointer travel while coalescing animation-frame seeks', () => {
  const script = read('assets/maliev-pimm-30g.js');

  assert.match(script, /const rotationStartTime = 65 \/ 24/);
  assert.match(script, /const rotationEndTime = 101 \/ 24/);
  assert.match(script, /dragStartProgress - \(point\.clientX - dragStartX\) \* progressPerPixel\(\)/);
  assert.match(script, /scrubFrame = window\.requestAnimationFrame\(applyScrub\)/);
  assert.match(script, /URL\.createObjectURL\(blob\)/);
  assert.match(script, /fetch\(sourceUrl, \{ cache: 'force-cache' \}\)/);
  assert.doesNotMatch(script, /const wrapTime/);
  assert.doesNotMatch(script, /const deltaX = event\.clientX - lastX/);
});

test('configuration turntable makes every rendered angle directly seekable', () => {
  const output = execFileSync(
    'ffprobe',
    [
      '-v', 'error',
      '-select_streams', 'v:0',
      '-show_entries', 'frame=key_frame',
      '-of', 'csv=p=0',
      join(root, 'assets', 'pimm30-configuration-turntable-desktop.webm'),
    ],
    { encoding: 'utf8' }
  );
  const keyframeFlags = output.trim().split(/\s+/);

  assert.equal(keyframeFlags.length, 168);
  assert.ok(keyframeFlags.every((flag) => flag === '1'));
});

test('capacity animations retain every native Blender frame', () => {
  for (const asset of ['pimm30-capacity-three-cube-desktop.webm', 'pimm30-capacity-three-cube-mobile.webm']) {
    const output = execFileSync(
      'ffprobe',
      [
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=avg_frame_rate:stream_tags=alpha_mode',
        '-of', 'json',
        join(root, 'assets', asset),
      ],
      { encoding: 'utf8' }
    );
    const stream = JSON.parse(output).streams[0];
    assert.equal(stream.avg_frame_rate, '24/1');
    assert.equal(stream.tags.ALPHA_MODE, '1');
  }
});

test('capacity chapter uses the approved three-cube media only', () => {
  const template = read('templates/product.injection-molding-machine.json');

  assert.match(template, /pimm30-capacity-three-cube-desktop\.webm/);
  assert.match(template, /pimm30-capacity-three-cube-mobile\.webm/);
  assert.doesNotMatch(template, /pimm30-capacity-scale-(?:desktop|mobile)\.webm/);
});
