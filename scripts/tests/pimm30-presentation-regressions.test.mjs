import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const read = (path) => readFileSync(join(root, path), 'utf8');

const alphaBounds = (path, seek = null, minVal = 8) => {
  const input = join(root, path);
  const decodeArgs = path.endsWith('.webm') ? ['-c:v', 'libvpx-vp9'] : [];
  const seekArgs = seek === null ? [] : ['-ss', String(seek)];
  const output = execFileSync(
    'ffmpeg',
    [
      '-hide_banner', '-loglevel', 'error',
      ...seekArgs, ...decodeArgs, '-i', input,
      '-vf', `alphaextract,bbox=min_val=${minVal},metadata=print:file=-`,
      '-frames:v', '1',
      '-f', 'null', '-'
    ],
    { encoding: 'utf8' },
  );
  return Object.fromEntries(
    [...output.matchAll(/lavfi\.bbox\.(x1|x2|y1|y2|w|h)=(\d+)/g)].map((match) => [match[1], Number(match[2])]),
  );
};

test('alpha videos replace their poster layer while playing', () => {
  const liquid = read('snippets/maliev-pimm-30g-chapter.liquid');
  const css = read('assets/maliev-pimm-30g.css');
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');
  const script = read('assets/maliev-pimm-30g.js');

  assert.doesNotMatch(liquid, /<video\b[^>]*\bposter=/);
  assert.match(css, /\.pimm30-stage__layer\.has-active-video \.pimm30-stage__poster/);
  assert.doesNotMatch(keynoteCss, /\.is-hero-pending[\s\S]*?\.pimm30-stage__poster[\s\S]*?visibility:\s*visible\s*!important/);
  assert.match(script, /video\.play\(\)\s*\.then\(\(\) => \{[\s\S]*?classList\.add\('has-active-video'\)/);
  assert.doesNotMatch(script, /classList\.add\('has-active-video'\);\s*video\.play\(\)/);
  assert.match(script, /classList\.add\('has-active-video'\)/);
  assert.match(script, /classList\.remove\('has-active-video'\)/);
});

test('transparent presentation media is never hard-cropped by the stage', () => {
  const css = read('assets/maliev-pimm-30g.css');
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');
  const noCropCss = read('assets/maliev-pimm-30g-no-crop.css');
  const section = read('sections/maliev-pimm-30g-story.liquid');

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
  assert.match(section, /maliev-pimm-30g-keynote\.css[\s\S]*?maliev-pimm-30g-no-crop\.css/);
  assert.doesNotMatch(noCropCss, /mask-image:\s*linear-gradient\(to right/);
});

test('hero art preserves alpha shadow clearance before CSS presentation scaling', () => {
  const template = read('templates/product.injection-molding-machine.json');

  assert.match(template, /pimm30-v13-hero-desktop-contained\.(?:webm|webp)/);
  assert.match(template, /pimm30-v13-hero-mobile-contained\.(?:webm|webp)/);

  const desktop = alphaBounds('assets/pimm30-v13-hero-desktop-contained.webp');
  const mobile = alphaBounds('assets/pimm30-v13-hero-mobile-contained.webp');
  const desktopFinalFrame = alphaBounds('assets/pimm30-v13-hero-desktop-contained.webm', 3.9);
  const mobileFinalFrame = alphaBounds('assets/pimm30-v13-hero-mobile-contained.webm', 3.9);
  const desktopSolid = alphaBounds('assets/pimm30-v13-hero-desktop-contained.webp', null, 200);
  const mobileSolid = alphaBounds('assets/pimm30-v13-hero-mobile-contained.webp', null, 200);
  assert.ok(desktop.x1 > 0 && desktop.x2 < 1919, `desktop alpha touches a side: ${JSON.stringify(desktop)}`);
  assert.ok(mobile.x1 > 0 && mobile.x2 < 1079, `mobile alpha touches a side: ${JSON.stringify(mobile)}`);
  assert.ok(desktopFinalFrame.x1 > 0 && desktopFinalFrame.x2 < 1919, `desktop video alpha touches a side: ${JSON.stringify(desktopFinalFrame)}`);
  assert.ok(mobileFinalFrame.x1 > 0 && mobileFinalFrame.x2 < 1079, `mobile video alpha touches a side: ${JSON.stringify(mobileFinalFrame)}`);
  assert.ok(desktop.w - desktopSolid.w > 80, 'desktop ground shadow was stripped from the alpha render');
  assert.ok(mobile.w - mobileSolid.w > 80, 'mobile ground shadow was stripped from the alpha render');
});

test('hero uses a continuous aspect-aware layout with no backdrop wash layer', () => {
  const noCropCss = read('assets/maliev-pimm-30g-no-crop.css');
  const template = read('templates/product.injection-molding-machine.json');
  const liquid = read('snippets/maliev-pimm-30g-chapter.liquid');
  const script = read('assets/maliev-pimm-30g.js');

  assert.match(template, /pimm30-v13-hero-desktop-contained\.(?:webm|webp)/);
  assert.match(template, /pimm30-v13-hero-mobile-contained\.(?:webm|webp)/);
  assert.match(liquid, /\(max-width: 539px\), \(max-aspect-ratio: 6\/5\)/);
  assert.match(script, /matchMedia\('\(max-width: 539px\), \(max-aspect-ratio: 6\/5\)'\)/);
  assert.match(noCropCss, /Hero fluid composition[\s\S]*?--pimm30-hero-media-height:[\s\S]*?100svh/);
  assert.match(noCropCss, /@media \(max-width: 539px\), \(max-aspect-ratio: 6\/5\)[\s\S]*?grid-template-columns:\s*repeat\(4, minmax\(0, 1fr\)\)/);
  assert.match(noCropCss, /@media \(min-width: 540px\) and \(min-aspect-ratio: 6\/5\)[\s\S]*?grid-template-columns:\s*var\(--pimm30-hero-copy-width\) minmax\(0, 1fr\)/);
  assert.match(noCropCss, /data-pimm30-layer='pimm30-overview'\]::after[\s\S]*?content:\s*none !important/);
  assert.doesNotMatch(noCropCss, /mask-image:\s*linear-gradient/);

  assert.match(noCropCss, /Wide desktop hero presence[\s\S]*?--pimm30-hero-wide-canvas-height:[\s\S]*?100svh[\s\S]*?1\.16/);

  // The supplied 1294 × 910 desktop reference should render the authored
  // machine alpha at configuration-slide scale while retaining its shadow.
  const referenceViewport = { width: 1294, height: 910 };
  const headerSpace = 72;
  const copyWidth = Math.min(928, Math.max(448, referenceViewport.width * 0.41));
  const canvasHeight = Math.min(
    referenceViewport.height - headerSpace - 16,
    (referenceViewport.width - copyWidth) * 1.16,
  );
  const authoredMachineHeight = 853;
  const renderedMachineHeight = canvasHeight * (authoredMachineHeight / 1080);
  assert.ok(renderedMachineHeight >= 640, `wide desktop machine is undersized: ${renderedMachineHeight}px`);

  for (const [path, maxX] of [
    ['assets/pimm30-v13-hero-desktop-contained.webp', 1919],
    ['assets/pimm30-v13-hero-mobile-contained.webp', 1079],
  ]) {
    const faint = alphaBounds(path, null, 8);
    const solid = alphaBounds(path, null, 200);
    assert.ok(faint.x1 > 0 && faint.x2 < maxX, `${path} touches a horizontal edge`);
    assert.ok(faint.w - solid.w > 80, `${path} no longer contains its authored ground shadow`);
  }
});

test('hero art direction keeps wide media on landscape screens', () => {
  const liquid = read('snippets/maliev-pimm-30g-chapter.liquid');
  const section = read('sections/maliev-pimm-30g-story.liquid');
  const noCropCss = read('assets/maliev-pimm-30g-no-crop.css');
  const script = read('assets/maliev-pimm-30g.js');

  assert.match(section, /<\/div>\s*\{%- if role == 'overview' -%\}[\s\S]*?class="pimm30-scroll-cue"/);
  assert.match(liquid, /assign stage_poster_url = desktop_poster_url[\s\S]*?if stage_poster_url == blank[\s\S]*?assign stage_poster_url = mobile_poster_url/);
  assert.doesNotMatch(liquid, /when 'overview',[\s\S]*?assign stage_poster_url = mobile_poster_url/);
  assert.match(noCropCss, /@media \(min-width: 540px\) and \(min-aspect-ratio: 6\/5\)/);
  assert.match(liquid, /media="\(max-width: 539px\), \(max-aspect-ratio: 6\/5\)"/);
  assert.match(script, /matchMedia\('\(max-width: 539px\), \(max-aspect-ratio: 6\/5\)'\)/);
  assert.doesNotMatch(script, /PORTRAIT_STAGE_ROLES/);
});

test('responsive keynote contract stacks narrow slides and contains transparent hero edges', () => {
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');

  // A width-only tablet query was the regression: 867x1032 was portrait but
  // still entered the desktop split.  Wide composition is orientation-aware
  // and starts only when the copy column can remain legible.
  assert.doesNotMatch(keynoteCss, /@media\s*\(min-width:\s*700px\),/);
  assert.match(
    keynoteCss,
    /@media \(max-width: 899px\), \(orientation: portrait\)[\s\S]*?--pimm30-copy-share:\s*100%[\s\S]*?--pimm30-media-height:\s*clamp\(20rem, 68svh, 50rem\)[\s\S]*?\.pimm30-stage__backdrop[\s\S]*?display:\s*none !important[\s\S]*?\.pimm30-chapter\s*\{[\s\S]*?display:\s*block !important/
  );
  assert.match(
    keynoteCss,
    /@media \(min-width: 900px\) and \(orientation: landscape\)[\s\S]*?--pimm30-copy-share:\s*40%[\s\S]*?grid-template-columns:\s*var\(--pimm30-copy-share\) minmax\(0, 1fr\) !important/
  );

  // The hero source is intentionally scaled for presence on wide screens;
  // mask the layer box so its broad transparent ground plane fades at the
  // media-column edges instead of ending in a hard left/right cut.
  assert.match(
    keynoteCss,
    /data-pimm30-layer=['"]pimm30-overview['"][\s\S]*?mask-image:\s*linear-gradient\(to right, transparent 0%, #000 12%, #000 88%, transparent 100%\) !important/
  );
  assert.match(
    keynoteCss,
    /@media \(min-width: 900px\) and \(orientation: landscape\)[\s\S]*?\.pimm30-stage__backdrop\s*\{[\s\S]*?align-items:\s*center !important[\s\S]*?inset:\s*50% 0 auto var\(--pimm30-copy-share\) !important[\s\S]*?justify-content:\s*center !important[\s\S]*?max-width:\s*calc\(100% - var\(--pimm30-copy-share\)\) !important[\s\S]*?text-align:\s*center !important/
  );
  assert.match(
    keynoteCss,
    /@media \(min-width: 900px\) and \(orientation: landscape\)[\s\S]*?--pimm30-desktop-hero-scale:\s*1\.7[\s\S]*?@media \(min-width: 900px\) and \(orientation: landscape\) and \(max-height: 699px\)[\s\S]*?--pimm30-desktop-hero-scale:\s*1\.18/
  );
  assert.match(
    keynoteCss,
    /@media \(orientation: landscape\)[\s\S]*?data-pimm30-layer=['"]pimm30-overview['"][\s\S]*?height:\s*auto !important[\s\S]*?max-height:\s*100% !important[\s\S]*?max-width:\s*100% !important[\s\S]*?transform:\s*scale\(var\(--pimm30-desktop-hero-scale\)\) !important[\s\S]*?width:\s*100% !important/
  );
  assert.match(
    keynoteCss,
    /@media \(min-width: 900px\) and \(orientation: landscape\)[\s\S]*?data-pimm30-layer=['"]pimm30-overview['"][\s\S]*?transform:\s*translateX\(-12\.5%\) scale\(var\(--pimm30-desktop-hero-scale\)\) !important/
  );
  assert.match(
    keynoteCss,
    /data-pimm30-layer=['"]pimm30-configuration['"][\s\S]*?mask-image:\s*linear-gradient\(to right, transparent 0%, #000 12%, #000 88%, transparent 100%\) !important/
  );
});

test('mobile hero expands its media lane while reserving a bottom feature, CTA, and scroll-cue stack', () => {
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');

  assert.match(
    keynoteCss,
    /@media \(max-width: 899px\), \(orientation: portrait\)[\s\S]*?--pimm30-mobile-model-space:\s*clamp\(8rem, 24vw, 11rem\)[\s\S]*?--pimm30-hero-media-height:\s*min\([\s\S]*?calc\(68svh - var\(--pimm30-mobile-model-space\)\)[\s\S]*?calc\(100svh - var\(--pimm30-header-space\) - var\(--pimm30-mobile-model-space\)\)/
  );
  assert.match(
    keynoteCss,
    /data-pimm30-layer=['"]pimm30-overview['"]\]\s*\{[\s\S]*?height:\s*var\(--pimm30-hero-media-height\) !important[\s\S]*?inset:\s*calc\(var\(--pimm30-header-space\) \+ var\(--pimm30-mobile-model-space\)\) 0 auto !important/
  );
  assert.match(
    keynoteCss,
    /\.pimm30-story \.pimm30-chapter--hero \.pimm30-chapter__content[\s\S]*?padding-top:\s*calc\([\s\S]*?var\(--pimm30-mobile-model-space\)[\s\S]*?var\(--pimm30-hero-media-height\)/
  );
  assert.match(
    keynoteCss,
    /\.pimm30-story \.pimm30-chapter--hero \.pimm30-chapter__model[\s\S]*?left:\s*50% !important[\s\S]*?position:\s*absolute !important[\s\S]*?top:\s*calc\(var\(--pimm30-header-space\) \+ clamp\(0\.8rem, 3svh, 1\.4rem\)\) !important[\s\S]*?transform:\s*translateX\(-50%\) !important/
  );
  assert.match(
    keynoteCss,
    /\.pimm30-story\.is-hero-bright \.pimm30-stage__backdrop\s*\{[\s\S]*?display:\s*flex !important[\s\S]*?font-size:\s*clamp\(3\.2rem, 13vw, 6\.2rem\) !important[\s\S]*?var\(--pimm30-mobile-model-space\)/
  );
  assert.match(
    keynoteCss,
    /data-pimm30-layer=['"]pimm30-overview['"]\][\s\S]*?\.pimm30-stage__poster\s+img,[\s\S]*?\.pimm30-stage__video\s*\{[\s\S]*?inset:\s*0 auto !important[\s\S]*?left:\s*50% !important[\s\S]*?transform:\s*translateX\(-50%\) !important[\s\S]*?width:\s*auto !important[\s\S]*?mask-image:\s*linear-gradient\(to right, transparent 0%, #000 14%, #000 86%, transparent 100%\) !important/
  );
  assert.match(
    keynoteCss,
    /@media \(max-width: 899px\), \(orientation: portrait\)[\s\S]*?data-pimm30-layer=['"]pimm30-overview['"]\]\:\:after\s*\{[\s\S]*?content:\s*none !important[\s\S]*?display:\s*none !important/
  );
  assert.match(
    keynoteCss,
    /@media \(max-width: 899px\), \(orientation: portrait\)[\s\S]*?--pimm30-mobile-feature-rail:\s*8\.8rem[\s\S]*?--pimm30-mobile-action-height:\s*5\.2rem[\s\S]*?--pimm30-mobile-scroll-height:\s*3rem[\s\S]*?--pimm30-hero-media-height:\s*clamp\([\s\S]*?100svh - var\(--pimm30-header-space\)[\s\S]*?var\(--pimm30-mobile-feature-rail\)[\s\S]*?var\(--pimm30-mobile-action-height\)[\s\S]*?var\(--pimm30-mobile-scroll-height\)/
  );
  assert.match(
    keynoteCss,
    /\.pimm30-story \.pimm30-chapter--hero \.pimm30-chapter__hero-heading,[\s\S]*?\.pimm30-chapter__lead\s*\{[\s\S]*?clip-path:\s*inset\(50%\) !important[\s\S]*?position:\s*absolute !important/
  );
  assert.match(
    keynoteCss,
    /\.pimm30-story \.pimm30-chapter--hero \.pimm30-spec-rail\.pimm30-spec-rail--hero\s*\{[\s\S]*?bottom:\s*calc\([\s\S]*?var\(--pimm30-mobile-scroll-height\)[\s\S]*?var\(--pimm30-mobile-action-height\)[\s\S]*?position:\s*absolute !important/
  );
  assert.match(
    keynoteCss,
    /\.pimm30-story \.pimm30-chapter--hero \.pimm30-action--hero\s*\{[\s\S]*?bottom:\s*calc\([\s\S]*?var\(--pimm30-mobile-scroll-height\)[\s\S]*?min-height:\s*var\(--pimm30-mobile-action-height\) !important[\s\S]*?position:\s*absolute !important/
  );
  assert.match(
    keynoteCss,
    /\.pimm30-story \.pimm30-chapter--hero \.pimm30-action--hero\s*\{[\s\S]*?left:\s*clamp\(1\.2rem, 6vw, 3\.2rem\) !important[\s\S]*?justify-self:\s*stretch !important[\s\S]*?right:\s*clamp\(1\.2rem, 6vw, 3\.2rem\) !important/
  );
  assert.match(
    keynoteCss,
    /data-active-chapter=['"]pimm30-overview['"][\s\S]*?\.pimm30-scroll-cue\s*\{[\s\S]*?bottom:\s*var\(--pimm30-mobile-safe-bottom\) !important[\s\S]*?display:\s*flex !important/
  );
  assert.match(
    keynoteCss,
    /@media \(min-width: 540px\) and \(max-width: 899px\) and \(orientation: landscape\)[\s\S]*?grid-template-columns:\s*var\(--pimm30-compact-landscape-copy\) minmax\(0, 1fr\) !important/
  );
  assert.match(
    keynoteCss,
    /@media \(min-width: 540px\) and \(max-width: 899px\) and \(orientation: landscape\)[\s\S]*?\.pimm30-chapter__model\s*\{[\s\S]*?position:\s*absolute !important[\s\S]*?top:\s*calc\(var\(--pimm30-header-space\) \+ 0\.75rem\) !important/
  );
  assert.match(
    keynoteCss,
    /@media \(orientation: portrait\) and \(min-height: 700px\)[\s\S]*?data-pimm30-layer=['"]pimm30-overview['"][\s\S]*?transform:\s*translateX\(-50%\) !important[\s\S]*?transform-origin:\s*50% 50% !important/
  );
  assert.match(
    keynoteCss,
    /@media \(min-width: 600px\) and \(orientation: portrait\)[\s\S]*?--pimm30-mobile-feature-rail:\s*6rem[\s\S]*?--pimm30-hero-media-height:\s*clamp\([\s\S]*?64rem/
  );
  assert.match(
    keynoteCss,
    /@media \(min-width: 600px\) and \(orientation: portrait\)[\s\S]*?transform:\s*translateX\(-50%\) !important[\s\S]*?transform-origin:\s*50% 50% !important[\s\S]*?\.pimm30-story\.is-hero-complete[\s\S]*?inset:\s*60% 0 -42% !important[\s\S]*?grid-template-columns:\s*repeat\(4, minmax\(0, 1fr\)\) !important[\s\S]*?max-width:\s*min\(42rem, calc\(100% - 4\.8rem\)\) !important/
  );
  assert.match(
    keynoteCss,
    /@media \(min-width: 600px\) and \(max-width: 899px\) and \(orientation: portrait\)[\s\S]*?--pimm30-mobile-control-gap:\s*2\.4rem[\s\S]*?\.pimm30-stage__backdrop\s*\{[\s\S]*?font-size:\s*clamp\(8\.4rem, 14vw, 9\.6rem\) !important[\s\S]*?height:\s*var\(--pimm30-hero-media-height\) !important[\s\S]*?mask-image:\s*none !important[\s\S]*?\.pimm30-stage__poster\s*\{[\s\S]*?height:\s*100% !important[\s\S]*?mask-composite:\s*intersect !important[\s\S]*?linear-gradient\(to bottom, #000 0%, #000 88%, transparent 100%\)[\s\S]*?transform:\s*translateX\(-50%\) scale\(1\.42\) !important[\s\S]*?transform-origin:\s*50% 50% !important[\s\S]*?grid-template-columns:\s*minmax\(0, 1fr\) auto minmax\(0, 1fr\) !important[\s\S]*?grid-column:\s*2 !important[\s\S]*?grid-column:\s*3 !important[\s\S]*?justify-self:\s*end !important/
  );
  assert.match(
    keynoteCss,
    /@media \(min-width: 600px\) and \(max-width: 899px\) and \(orientation: portrait\) and \(min-height: 1100px\)[\s\S]*?transform:\s*translateX\(-50%\) translateY\(0\.8rem\) scale\(1\.36\) !important/
  );
  assert.doesNotMatch(
    keynoteCss,
    /transform:\s*translateX\(-50%\) scale\(1\.18\) !important/
  );
});

test('completed tablet hero holds the animation frame without a poster swap', () => {
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');
  const script = read('assets/maliev-pimm-30g.js');

  assert.doesNotMatch(
    keynoteCss,
    /\.is-hero-complete[\s\S]*?\.pimm30-stage__video--mobile\s*\{[\s\S]*?opacity:\s*0 !important/
  );
  assert.match(script, /layer\.dataset\.pimm30Layer === 'pimm30-overview'[\s\S]*?video\.classList\.add\('is-paused'\)[\s\S]*?layer\.classList\.add\('has-active-video'\)/);
});

test('hero startup begins in a dark studio and turns light at the configured milestone', () => {
  const section = read('sections/maliev-pimm-30g-story.liquid');
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');
  const script = read('assets/maliev-pimm-30g.js');

  assert.match(section, /class="[^"]*is-hero-pending[^"]*is-hero-dark[^"]*"/);
  assert.doesNotMatch(section, /class="[^"]*is-hero-pending[^"]*is-hero-bright/);
  assert.match(section, /data-pimm30-light-milestone="\{\{ section\.settings\.hero_light_milestone \}\}"/);
  assert.match(section, /data-header-overlay-tone="dark"/);
  assert.match(keynoteCss, /\.pimm30-story\.is-hero-dark[\s\S]*?background:\s*var\(--pimm30-stage-dark\)\s*!important/);
  assert.match(keynoteCss, /\.pimm30-story\.is-hero-dark \.pimm30-stage[\s\S]*?background:\s*var\(--pimm30-stage-dark\)\s*!important/);
  assert.match(keynoteCss, /\.pimm30-story\.is-hero-dark \.pimm30-stage__backdrop\s*\{[\s\S]*?display:\s*none !important[\s\S]*?opacity:\s*0 !important/);
  assert.match(keynoteCss, /\.pimm30-story\.is-hero-bright \.pimm30-stage__backdrop\s*\{[\s\S]*?opacity:\s*1 !important/);
  assert.match(keynoteCss, /data-active-chapter=['"]pimm30-next_model['"][\s\S]*?\.pimm30-stage__backdrop\s*\{[\s\S]*?color:\s*rgba\(255, 255, 255, 0\.16\) !important/);
  assert.match(keynoteCss, /transition:\s*background-color 900ms cubic-bezier\(0\.22, 1, 0\.36, 1\)/);
  assert.match(script, /function setHeroTone\(bright\)[\s\S]*?classList\.toggle\('is-hero-bright', bright\)[\s\S]*?classList\.toggle\('is-hero-dark', !bright\)/);
  assert.doesNotMatch(script, /timeupdate'[\s\S]*?setHeroTone\(/);
  assert.match(script, /setSpecCounts\(0\);\s*setHeroComplete\(false\);\s*setHeroTone\(false\)/);
  assert.match(script, /if \(reduced \|\| !initialHeroVideo \|\| activeId !== 'pimm30-overview'\)[\s\S]*?setHeroTone\(true\)/);
  assert.match(keynoteCss, /\.pimm30-story\.is-hero-sequencing \.pimm30-chapter--hero \.pimm30-chapter__model\s*\{[\s\S]*?opacity:\s*0 !important/);
  assert.match(keynoteCss, /\.pimm30-story\.is-hero-sequencing \.pimm30-chapter--hero \.pimm30-chapter__content,[\s\S]*?\.pimm30-scroll-cue\s*\{[\s\S]*?visibility:\s*hidden !important/);
  assert.match(script, /function setHeroComplete\(complete\)[\s\S]*?classList\.toggle\('is-hero-complete', complete\)[\s\S]*?classList\.toggle\('is-hero-sequencing', !complete\)/);
  assert.match(script, /video\.addEventListener\('ended'[\s\S]*?heroHasPlayed = true;[\s\S]*?setHeroComplete\(true\);/);
  assert.match(script, /layer\.dataset\.pimm30Layer === 'pimm30-overview'[\s\S]*?video\.classList\.add\('is-paused'\)[\s\S]*?layer\.classList\.add\('has-active-video'\)/);
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

test('configuration enters on a visible interactive frame instead of the transparent video tail', () => {
  const script = read('assets/maliev-pimm-30g.js');

  assert.match(
    script,
    /layer\.matches\('\[data-pimm30-turntable\]'\)[\s\S]*?video\.currentTime = \(65 \/ 24 \+ 101 \/ 24\) \/ 2[\s\S]*?is-turntable-ready[\s\S]*?video\.load\(\)/,
  );
  assert.match(script, /video\.play\(\)[\s\S]*?requestAnimationFrame\(settleFrame\)/);
  assert.doesNotMatch(
    script,
    /layer\.matches\('\[data-pimm30-turntable\]'\)[\s\S]{0,260}?video\.play\(\)/,
  );
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
  assert.doesNotMatch(template, /pimm30-capacity-three-cube-mobile\.(?:webm|webp)/);
  assert.doesNotMatch(template, /pimm30-capacity-scale-(?:desktop|mobile)\.webm/);
});

test('hero feature rail keeps machine specifications readable as product highlights', () => {
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');

  // The rail has to earn its dedicated bottom lane: the labels and values
  // cannot collapse into the tiny technical annotation scale on phone.
  assert.match(
    keynoteCss,
    /--pimm30-mobile-feature-rail:\s*10rem[\s\S]*?\.pimm30-spec-rail--hero dt\s*\{[\s\S]*?font-size:\s*clamp\(1\.15rem, 3\.3vw, 1\.35rem\) !important[\s\S]*?\.pimm30-spec-rail--hero dd,[\s\S]*?font-size:\s*clamp\(2rem, 5\.5vw, 2\.6rem\) !important/
  );
  assert.match(
    keynoteCss,
    /\.pimm30-spec-rail--hero dt\s*\{[\s\S]*?font-size:\s*clamp\(1\.15rem, 0\.95vw, 1\.3rem\) !important[\s\S]*?\.pimm30-spec-rail--hero dd,[\s\S]*?font-size:\s*clamp\(2\.1rem, 1\.9vw, 2\.8rem\) !important/
  );
});

test('bright PIMM studio uses a high-key surface without diluting dark startup', () => {
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');

  assert.match(keynoteCss, /--pimm30-stage-background:\s*#fafbfc;/);
  assert.match(keynoteCss, /--pimm30-stage-surface:\s*#fafbfc;/);
  assert.match(keynoteCss, /--pimm30-stage-dark:\s*#0a0e13;/);
  assert.match(
    keynoteCss,
    /is-hero-dark[\s\S]*?--pimm30-stage-surface:\s*var\(--pimm30-stage-dark\)/,
  );
});

test('final responsive contract removes side fades and presents each hero feature independently', () => {
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');

  assert.match(
    keynoteCss,
    /PIMM responsive art-direction contract[\s\S]*?data-pimm30-layer=['"]pimm30-overview['"][\s\S]*?mask-image:\s*none !important/,
  );
  assert.match(
    keynoteCss,
    /PIMM responsive art-direction contract[\s\S]*?\.pimm30-spec-rail--hero\s*\{[\s\S]*?gap:\s*clamp\(0\.6rem, 1\.5vw, 1\.2rem\) !important[\s\S]*?\.pimm30-spec-rail--hero > div[\s\S]*?background:\s*rgba\(255, 255, 255, 0\.72\) !important[\s\S]*?border-radius:\s*1rem !important[\s\S]*?border-top:\s*0 !important/,
  );
  assert.match(
    keynoteCss,
    /Final compact\/tablet cascade seal[\s\S]*?min-width:\s*600px[\s\S]*?max-width:\s*899px[\s\S]*?scale\(1\.25\) !important/,
  );
  assert.doesNotMatch(
    keynoteCss,
    /Final compact\/tablet cascade seal[\s\S]*?scale\(1\.32\) !important/,
  );
});

test('detail chapters use the approved close-up assets and animated heater sequence', () => {
  const template = read('templates/product.injection-molding-machine.json');
  const noCropCss = read('assets/maliev-pimm-30g-no-crop.css');

  assert.match(
    template,
    /"temperature"[\s\S]*?pimm30-temperature-controller-desktop\.webm[\s\S]*?pimm30-temperature-controller-desktop\.webp[\s\S]*?pimm30-temperature-controller-mobile\.webm[\s\S]*?pimm30-temperature-controller-mobile\.webp/,
  );
  assert.match(
    noCropCss,
    /Temperature animation focus[\s\S]*?\.pimm30-story\.pimm30-story[\s\S]*?> \.pimm30-stage__layer\[data-pimm30-layer=['"]pimm30-temperature['"]\][\s\S]*?object-fit:\s*contain !important[\s\S]*?transform:\s*none !important/,
  );
  for (const [asset, width, height] of [
    ['pimm30-temperature-controller-desktop.webm', 1200, 1440],
    ['pimm30-temperature-controller-mobile.webm', 1080, 1920],
  ]) {
    const probe = JSON.parse(execFileSync(
      'ffprobe',
      [
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'format=duration:stream=width,height,avg_frame_rate:stream_tags=alpha_mode',
        '-of', 'json',
        join(root, 'assets', asset),
      ],
      { encoding: 'utf8' },
    ));
    assert.equal(probe.streams[0].width, width);
    assert.equal(probe.streams[0].height, height);
    assert.equal(probe.streams[0].avg_frame_rate, '24/1');
    assert.equal(probe.streams[0].tags.alpha_mode ?? probe.streams[0].tags.ALPHA_MODE, '1');
    assert.equal(Number(probe.format.duration), 10);

    const start = alphaBounds(`assets/${asset}`, 0);
    const end = alphaBounds(`assets/${asset}`, 9.9);
    const minimumCloseupWidth = width === 1200 ? 850 : 1000;
    assert.ok(start.w >= minimumCloseupWidth, `${asset} starts too far from the controllers: ${JSON.stringify(start)}`);
    assert.ok(end.w >= minimumCloseupWidth, `${asset} ends too far from the controllers: ${JSON.stringify(end)}`);
    assert.ok(start.h >= height * 0.98, `${asset} does not fill the stage vertically at startup: ${JSON.stringify(start)}`);
    assert.ok(end.h >= height * 0.98, `${asset} does not fill the stage vertically at completion: ${JSON.stringify(end)}`);
    if (asset.includes('desktop')) {
      assert.equal(width / height, 5 / 6, 'desktop controller media must fill the tall presentation stage');
    }
  }
  assert.match(template, /"regulator"[\s\S]*?pimm30-v4-regulator-desktop\.webp[\s\S]*?pimm30-v4-regulator-mobile\.webp/);
  assert.doesNotMatch(template, /pimm30-v10-regulator-(?:desktop|mobile)\.webp/);
});

test('portrait chapters contain media and keep all capacity content inside one viewport', () => {
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');
  const noCropCss = read('assets/maliev-pimm-30g-no-crop.css');
  const template = read('templates/product.injection-molding-machine.json');

  assert.doesNotMatch(keynoteCss, /pimm30-capacity[^}]*scale\(1\.55\) !important/);
  assert.match(template, /"capacity"[\s\S]*?"mobile_video_asset": "pimm30-capacity-three-cube-desktop\.webm"[\s\S]*?"mobile_poster_asset": "pimm30-capacity-three-cube-desktop\.webp"/);
  assert.match(
    noCropCss,
    /PIMM final media contract[\s\S]*?pimm30-capacity['"]\][\s\S]*?height:\s*clamp\(15rem, 40svh, 36rem\) !important[\s\S]*?object-fit:\s*contain !important[\s\S]*?transform:\s*none !important/,
  );
  assert.match(
    noCropCss,
    /pimm30-chapter--capacity \.pimm30-chapter__content[\s\S]*?height:\s*100svh !important[\s\S]*?padding:\s*calc\(var\(--pimm30-header-space\) \+ clamp\(15rem, 40svh, 36rem\)\)/,
  );
  assert.match(keynoteCss, /pimm30-temperature[\s\S]*?mask-image:\s*linear-gradient\(to bottom, transparent 0%, #000 12%, #000 88%, transparent 100%\) !important/);
  assert.match(keynoteCss, /pimm30-regulator[\s\S]*?object-position:\s*50% 50% !important/);
  assert.match(
    keynoteCss,
    /pimm30-configuration[\s\S]*?height:\s*46svh !important[\s\S]*?\.pimm30-chapter--configuration \.pimm30-chapter__content[\s\S]*?height:\s*100svh !important[\s\S]*?overflow:\s*hidden !important/,
  );
  assert.match(keynoteCss, /pimm30-configuration[\s\S]*?touch-action:\s*pan-y !important/);
  assert.match(
    keynoteCss,
    /Final compact\/tablet cascade seal[\s\S]*?\.pimm30-stage > \.pimm30-stage__layer\.is-active\s*\{[\s\S]*?opacity:\s*1 !important/,
  );
});

test('PIMM 50G finale removes the shared backdrop and strengthens the red stage glow', () => {
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');

  assert.match(
    keynoteCss,
    /data-active-chapter=['"]pimm30-next_model['"]\] \.pimm30-stage__backdrop\s*\{[\s\S]*?display:\s*none !important/,
  );
  assert.match(
    keynoteCss,
    /data-active-chapter=['"]pimm30-next_model['"]\] \.pimm30-stage\s*\{[\s\S]*?radial-gradient\(circle at 62% 38%, rgba\(228, 30, 24, 0\.46\), transparent 42%\)/,
  );
});

test('PIMM 50G portrait finale shares one centered presentation axis', () => {
  const keynoteCss = read('assets/maliev-pimm-30g-keynote.css');

  assert.match(
    keynoteCss,
    /Final PIMM 50G alignment seal[\s\S]*?\.pimm30-chapter--next_model \.pimm30-chapter__content\s*\{[\s\S]*?max-width:\s*none !important[\s\S]*?width:\s*100% !important/,
  );
  assert.match(
    keynoteCss,
    /Final PIMM 50G alignment seal[\s\S]*?\.pimm30-chapter__content > \*\s*\{[\s\S]*?margin-inline:\s*auto !important[\s\S]*?max-width:\s*min\(52rem, 100%\) !important[\s\S]*?width:\s*100% !important/,
  );
  assert.match(
    keynoteCss,
    /Final PIMM 50G alignment seal[\s\S]*?radial-gradient\(circle at 50% 38%, rgba\(228, 30, 24, 0\.46\), transparent 42%\)/,
  );
});
