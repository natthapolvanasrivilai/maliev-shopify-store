# PIMM 50G Red Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the final PIMM 50G chapter with a responsive, product-first red industrial presentation using a seamless five-second transparent Blender animation, verified 50G facts, live Shopify pricing, and accurate made-to-order status.

**Architecture:** Blender owns only the authentic 50G machine, contact shadow, restrained rear fog, and a periodic red backlight. Shopify Liquid and CSS own all text, facts, price, availability, CTA, layout, and responsive cropping. Existing PIMM chapter activation code remains responsible for playing only the visible media, pausing it offscreen, and falling back to a transparent poster when motion is reduced or video playback fails.

**Tech Stack:** Shopify Online Store 2.0 Liquid/JSON locales, CSS, vanilla JavaScript, Blender Cycles/Python, FFmpeg VP9/WebM and WebP, Node built-in test runner, Shopify Theme Check.

## Global Constraints

- Work only on branch `codex/impeccable-init`; do not push or deploy.
- Preserve unrelated dirty changes, especially `assets/maliev-commerce.css`, `templates/list-collections.json`, local logs, and untracked work.
- Do not overwrite the corrected 50G master. Copy:
  `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-50g-keynote-reveal-v2-regulator-materials.blend`
  to:
  `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-50g-red-stage-loop.blend`.
- Render no text, price, feature icons, phone frame, black background, or UI into Blender media.
- Preserve the corrected regulator material assignments in both the source copy and every rendered frame.
- Use one neutral 5000K key light. Any fill must be weaker and the same temperature. The red source is an effect/backlight, not a competing white key.
- Keep one fixed camera per composition, no camera movement, no narrow depth of field, and no clipped machine or contact shadow.
- Use verified claims only: `50g shot capacity`, `Steel melt zone`, and `2 × 350W hot-runner heater bands`. The corrected source master also contains the verified 350°C controller readout; keep that readout visible in the production media without baking marketing copy into the render.
- Available variants must display `Made to order`, never `In stock`. Keep the product and selected variant as the authority for title, THB price, availability, and CTA destination.
- Preserve English and Thai localization, keyboard/focus behavior, reduced-motion behavior, and Theme Editor schemas.
- Target zero horizontal overflow at 320, 390, 768, 1024, and 1440 CSS pixels.
- Target media budgets: desktop WebM at or below 8 MB, mobile WebM at or below 7 MB, and each poster at or below 350 KB.

---

## Task 1: Freeze the 50G presentation contract in focused tests

**Files:**

- Create: `scripts/tests/pimm50-red-stage.test.mjs`
- Read: `sections/maliev-pimm-30g-story.liquid`
- Read: `snippets/maliev-pimm-30g-chapter.liquid`
- Read: `templates/product.injection-molding-machine.json`
- Read: `locales/en.default.json`
- Read: `locales/th.json`

**Interfaces:**

- Consumes: the `next_model` block, next-product Liquid object, story template media settings, and locale JSON.
- Produces: executable assertions for made-to-order wording, localized facts, dedicated 50G assets, and next-model-only looping.

- [ ] Confirm the worktree baseline before any change:

  ```powershell
  git status --short
  git branch --show-current
  git diff -- assets/maliev-commerce.css templates/list-collections.json
  ```

  Expected: branch is `codex/impeccable-init`; unrelated changes are identified and remain untouched.

- [ ] Create a Node test using only built-in modules. It must strip the leading Shopify JSON comment before parsing the template and assert the following contracts:

  ```js
  import assert from 'node:assert/strict';
  import { readFileSync } from 'node:fs';
  import test from 'node:test';

  const read = (path) => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8');
  const parseTemplate = (source) => JSON.parse(source.replace(/^\/\*[\s\S]*?\*\//, '').trim());

  const section = read('sections/maliev-pimm-30g-story.liquid');
  const chapter = read('snippets/maliev-pimm-30g-chapter.liquid');
  const template = parseTemplate(read('templates/product.injection-molding-machine.json'));
  const en = JSON.parse(read('locales/en.default.json'));
  const th = JSON.parse(read('locales/th.json'));

  test('50G uses made-to-order commerce wording', () => {
    assert.match(section, /data-pimm50-made-to-order/);
    assert.doesNotMatch(section, /next_variant\.available[\s\S]{0,180}inventory_in_stock/);
    assert.equal(en.products.pimm30_story.next_model.made_to_order, 'Made to order');
    assert.equal(th.products.pimm30_story.next_model.made_to_order, 'ผลิตตามคำสั่งซื้อ');
  });

  test('50G facts remain verified and localized', () => {
    for (const locale of [en, th]) {
      const facts = locale.products.pimm30_story.next_model.facts;
      assert.equal(Object.keys(facts).length, 3);
      assert.ok(facts.capacity);
      assert.ok(facts.melt_zone);
      assert.ok(facts.heaters);
      assert.doesNotMatch(JSON.stringify(facts), /350\s*°?C/i);
    }
  });

  test('only the next-model chapter opts into looping video', () => {
    assert.match(chapter, /block\.settings\.role\s*==\s*'next_model'/);
    assert.match(chapter, /\{%\s*if is_looping\s*%\}loop\{%\s*endif\s*%\}/);
  });

  test('product story wires dedicated red-stage assets', () => {
    const story = template.sections.pimm_30g_story;
    const nextId = story.block_order.find((id) => story.blocks[id].settings.role === 'next_model');
    const settings = story.blocks[nextId].settings;
    assert.equal(settings.desktop_video_asset, 'pimm50-red-stage-desktop.webm');
    assert.equal(settings.mobile_video_asset, 'pimm50-red-stage-mobile.webm');
    assert.equal(settings.desktop_poster_asset, 'pimm50-red-stage-desktop.webp');
    assert.equal(settings.mobile_poster_asset, 'pimm50-red-stage-mobile.webp');
  });
  ```

- [ ] Run the focused test before implementation:

  ```powershell
  node --test scripts/tests/pimm50-red-stage.test.mjs
  ```

  Expected: failures for the deliberately missing made-to-order keys, media filenames, and conditional loop marker. Keep this red result as evidence that the test detects the old behavior.

---

## Task 2: Build an idempotent Blender production scene

**Files:**

- Create: `scripts/blender/create_pimm50_red_stage.py`
- Copy externally: corrected master to `PIMM-50g-red-stage-loop.blend`
- Modify externally: only `PIMM-50g-red-stage-loop.blend`

**Interfaces:**

- Consumes: corrected 50G geometry/materials and Blender Cycles.
- Produces: two named render scenes/cameras, procedural periodic atmosphere, transparent shadow-catching stage, and deterministic frame outputs.

- [ ] Locate the running Blender executable and verify the corrected source exists:

  ```powershell
  Get-Process blender -ErrorAction Stop | Select-Object -First 1 Path
  Get-Item -LiteralPath 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-50g-keynote-reveal-v2-regulator-materials.blend'
  ```

  Expected: one executable path and a non-zero corrected master file.

- [ ] Resolve the exact copy target and copy safely only when the target does not already contain newer intentional work:

  ```powershell
  $pimm50Source = 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-50g-keynote-reveal-v2-regulator-materials.blend'
  $pimm50Target = 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-50g-red-stage-loop.blend'
  Get-Item -LiteralPath $pimm50Source | Select-Object FullName,Length,LastWriteTime
  Test-Path -LiteralPath $pimm50Target
  Copy-Item -LiteralPath $pimm50Source -Destination $pimm50Target
  ```

  Expected: the corrected master remains unchanged; the new target is an independent copy.

- [ ] Open the copy through Blender MCP, enumerate scenes, collections, cameras, product bounds, and regulator-related objects/material slots. Record the exact product root and material names in constants at the top of the script. Fail loudly if any expected object is absent; do not guess by broad material reassignment.

- [ ] Implement `scripts/blender/create_pimm50_red_stage.py` as an idempotent scene builder. It must:

  - delete/recreate only objects and collections prefixed `PIMM50_RED_STAGE_`;
  - create collections `RED_STAGE_LIGHTS`, `RED_STAGE_FOG`, `RED_STAGE_GROUND`, and `RED_STAGE_CAMERAS`;
  - preserve all imported machine geometry and existing material slots;
  - verify the regulator body remains black powder-coated steel, its mounting plate remains stainless steel, and its machined mounting body remains aluminum;
  - create fixed desktop and mobile cameras aimed at a shared target, with the whole machine and contact shadow inside safe margins;
  - create a very large Cycles shadow catcher below the feet, with no visible floor in alpha;
  - create one 5000K dominant key and a weaker 5000K fill;
  - create a red rear effect light and a restrained fog volume behind—not in front of—the product;
  - disable depth of field or use an aperture that keeps the entire machine sharp;
  - enable Film Transparent, RGBA PNG output, Cycles GPU, denoising, 128 samples, 24 fps, frames 1–120;
  - keep frame 1 and the loop boundary visually identical.

- [ ] Use explicit periodic lighting keyframes, with frame 121 matching frame 1 exactly:

  ```py
  def keyframe_energy(light, values):
      for frame, energy in values:
          light.data.energy = energy
          light.data.keyframe_insert('energy', frame=frame)
      for curve in light.data.animation_data.action.fcurves:
          for point in curve.keyframe_points:
              point.interpolation = 'BEZIER'

  keyframe_energy(red_backlight, [
      (1, 180.0), (20, 180.0), (84, 1050.0),
      (101, 520.0), (121, 180.0),
  ])
  ```

- [ ] Animate fog with deterministic procedural mapping, not a simulation cache. Use sine/cosine drivers whose values at frames 1 and 121 are identical. Keep density low enough that edges, controller faces, hoses, and feet remain legible at peak red light.

- [ ] Save from the script to the target path and write render outputs beneath:

  ```text
  M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\product-story\50g-red-stage\desktop\
  M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\product-story\50g-red-stage\mobile\
  ```

- [ ] Run the builder inside the copied Blender file, then save, close/reopen the copy, and run it a second time.

  Expected: no duplicate stage collections, cameras, lights, volume objects, or shadow catchers; the source master remains untouched.

- [ ] Render proof frames 1, 20, 84, 101, and 121 for both cameras. Inspect each at original resolution for:

  - authentic 50G geometry and corrected regulator materials;
  - grounded feet and unclipped soft contact shadow;
  - no baked background or text;
  - fog behind the machine only;
  - one coherent neutral key-light direction;
  - restrained red build without crushed product detail;
  - full machine and shadow inside mobile and desktop safe areas;
  - exact visual continuity between frames 1 and 121.

  Reject and adjust the Blender scene before rendering the full sequence if any check fails.

---

## Task 3: Render, encode, and verify transparent production media

**Files:**

- Create: `assets/pimm50-red-stage-desktop.webm`
- Create: `assets/pimm50-red-stage-mobile.webm`
- Create: `assets/pimm50-red-stage-desktop.webp`
- Create: `assets/pimm50-red-stage-mobile.webp`

**Interfaces:**

- Consumes: validated Blender proof scene.
- Produces: Shopify-ready alpha video and poster assets with a seamless five-second loop.

- [ ] Render frames 1–120 for each scene at 24 fps. Use separate camera compositions; do not crop one render into both aspect ratios.

  Expected: exactly 120 RGBA PNG frames per composition.

- [ ] Render frame 121 separately for loop-boundary validation, then compare frames 1 and 121 using Pillow:

  ```powershell
  @'
  from PIL import Image, ImageChops
  from pathlib import Path
  roots = [
      Path(r'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\product-story\50g-red-stage\desktop'),
      Path(r'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\product-story\50g-red-stage\mobile'),
  ]
  for root in roots:
      first = Image.open(root / 'pimm50-red-stage-0001.png').convert('RGBA')
      boundary = Image.open(root / 'pimm50-red-stage-0121.png').convert('RGBA')
      assert ImageChops.difference(first, boundary).getbbox() is None, root
      alpha = first.getchannel('A')
      assert alpha.getextrema()[0] == 0, f'{root}: background is not transparent'
      assert alpha.getbbox() is not None, f'{root}: product alpha is empty'
  print('loop boundary and alpha verified')
  '@ | python -
  ```

  Expected: `loop boundary and alpha verified`.

- [ ] Encode the desktop sequence as transparent VP9 WebM:

  ```powershell
  ffmpeg -y -framerate 24 -i 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\product-story\50g-red-stage\desktop\pimm50-red-stage-%04d.png' -frames:v 120 -c:v libvpx-vp9 -pix_fmt yuva420p -auto-alt-ref 0 -crf 28 -b:v 0 -row-mt 1 -metadata:s:v:0 alpha_mode=1 'assets\pimm50-red-stage-desktop.webm'
  ```

- [ ] Encode the mobile sequence with the same five-second duration and alpha settings:

  ```powershell
  ffmpeg -y -framerate 24 -i 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\product-story\50g-red-stage\mobile\pimm50-red-stage-%04d.png' -frames:v 120 -c:v libvpx-vp9 -pix_fmt yuva420p -auto-alt-ref 0 -crf 28 -b:v 0 -row-mt 1 -metadata:s:v:0 alpha_mode=1 'assets\pimm50-red-stage-mobile.webm'
  ```

- [ ] Encode peak-but-legible transparent posters from frame 84:

  ```powershell
  ffmpeg -y -i 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\product-story\50g-red-stage\desktop\pimm50-red-stage-0084.png' -c:v libwebp -quality 86 -compression_level 6 'assets\pimm50-red-stage-desktop.webp'
  ffmpeg -y -i 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\product-story\50g-red-stage\mobile\pimm50-red-stage-0084.png' -c:v libwebp -quality 86 -compression_level 6 'assets\pimm50-red-stage-mobile.webp'
  ```

- [ ] Verify duration, codec, alpha metadata, dimensions, and size:

  ```powershell
  ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt:stream_tags=alpha_mode -show_entries format=duration -of json assets/pimm50-red-stage-desktop.webm
  ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt:stream_tags=alpha_mode -show_entries format=duration -of json assets/pimm50-red-stage-mobile.webm
  Get-Item assets/pimm50-red-stage-* | Select-Object Name,Length
  ```

  Expected: VP9, five-second duration, alpha metadata present, correct independent aspect ratios, and all files within the global budgets. If a WebM exceeds budget, increase CRF in increments of 2 and re-inspect edge quality; do not lower the frame count below 90 or substitute a static image.

- [ ] Open both WebMs and both posters over a checkerboard and over the intended dark CSS background. Confirm no white/black baked rectangle, alpha band, clipped fog, clipped shadow, frame-one flash, or visible loop seam.

- [ ] Run the theme build before committing the media slice:

  ```powershell
  npm run verify
  ```

  Expected: zero warnings and zero errors.

- [ ] Stage only the production script and four media assets, inspect staged diff/stat, and commit:

  ```powershell
  git add -- scripts/blender/create_pimm50_red_stage.py assets/pimm50-red-stage-desktop.webm assets/pimm50-red-stage-mobile.webm assets/pimm50-red-stage-desktop.webp assets/pimm50-red-stage-mobile.webp
  git diff --cached --stat
  git commit -m "feat: add PIMM 50G red-stage media"
  ```

---

## Task 4: Add the 50G display font and localized commerce content

**Files:**

- Create: `assets/antonio-variable.ttf`
- Create: `docs/licenses/Antonio-OFL.txt`
- Modify: `assets/maliev-shell.css`
- Modify: `sections/maliev-pimm-30g-story.liquid`
- Modify: `snippets/maliev-pimm-30g-chapter.liquid`
- Modify: `locales/en.default.json`
- Modify: `locales/th.json`
- Modify: `templates/product.injection-molding-machine.json`

**Interfaces:**

- Consumes: Shopify product/variant/metafield data and the next-model block contract.
- Produces: accessible localized HTML, next-model-only looping, and filenames for the new assets.

- [ ] Download Antonio from the official Google Fonts repository and keep its license in source control:

  ```powershell
  Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/google/fonts/main/ofl/antonio/Antonio%5Bwght%5D.ttf' -OutFile 'assets/antonio-variable.ttf'
  New-Item -ItemType Directory -Force -Path 'docs/licenses' | Out-Null
  Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/google/fonts/main/ofl/antonio/OFL.txt' -OutFile 'docs/licenses/Antonio-OFL.txt'
  ```

  Expected: a non-empty variable font and OFL license from the same upstream family directory.

- [ ] Register the font once in `assets/maliev-shell.css`:

  ```css
  @font-face {
    font-family: 'Antonio';
    src: url('{{ "antonio-variable.ttf" | asset_url }}') format('truetype');
    font-style: normal;
    font-weight: 100 700;
    font-display: swap;
  }
  ```

  If the stylesheet is not Liquid-rendered, follow its existing Shopify asset URL convention exactly rather than introducing a different loading path.

- [ ] Add English and Thai keys under `products.pimm30_story.next_model`:

  ```json
  {
    "made_to_order": "Made to order",
    "lead_time": "{{ days }}-day production lead time",
    "facts": {
      "capacity": "50g shot capacity",
      "melt_zone": "Steel melt zone",
      "heaters": "2 × 350W hot-runner heater bands"
    }
  }
  ```

  ```json
  {
    "made_to_order": "ผลิตตามคำสั่งซื้อ",
    "lead_time": "ระยะเวลาผลิต {{ days }} วัน",
    "facts": {
      "capacity": "ความจุการฉีด 50 กรัม",
      "melt_zone": "ชุดหลอมผลิตจากเหล็ก",
      "heaters": "ฮีตเตอร์ฮอตรันเนอร์ 350 วัตต์ 2 ชุด"
    }
  }
  ```

- [ ] Replace the current `next_model` feature list with the localized three-fact set, preserving semantic list markup. Keep title, THB price, and availability bound to `next_product`/`next_variant`; do not hardcode `฿170,000.00 THB`.

- [ ] Replace available-stock text with accurate made-to-order markup:

  ```liquid
  {% if next_variant.available %}
    <p class="pimm30-next-model__availability" data-pimm50-made-to-order>
      {{ 'products.pimm30_story.next_model.made_to_order' | t }}
    </p>
    {% assign next_lead_time = next_product.metafields.custom.lead_time.value | default: 30 %}
    <p class="pimm30-next-model__lead-time">
      {{ 'products.pimm30_story.next_model.lead_time' | t: days: next_lead_time }}
    </p>
  {% else %}
    <p class="pimm30-next-model__availability is-unavailable">
      {{ 'products.product.inventory_out_of_stock' | t }}
    </p>
  {% endif %}
  ```

  Preserve the store's existing lead-time metafield shape if inspection shows it is not a scalar value; the displayed fallback remains 30 days.

- [ ] In `snippets/maliev-pimm-30g-chapter.liquid`, derive looping only from the chapter role and add it to both responsive video elements:

  ```liquid
  {% assign is_looping = false %}
  {% if block.settings.role == 'next_model' %}
    {% assign is_looping = true %}
  {% endif %}
  ```

  Add `{% if is_looping %}loop{% endif %}` to the `<video>` attributes. Do not make hero or feature videos loop.

- [ ] Update the `next_model` block in `templates/product.injection-molding-machine.json` to the four exact `pimm50-red-stage-*` filenames.

- [ ] Run the focused contract test:

  ```powershell
  node --test scripts/tests/pimm50-red-stage.test.mjs
  ```

  Expected: all Task 1 assertions pass.

---

## Task 5: Implement the responsive red-stage presentation

**Files:**

- Modify: `assets/maliev-pimm-30g.css`
- Modify only if inspection proves necessary: `assets/maliev-pimm-30g.js`

**Interfaces:**

- Consumes: existing chapter activation classes, new alpha video/poster, and next-model semantic markup.
- Produces: responsive 40/60 desktop composition, mobile presentation, CSS atmosphere fallback, and reduced-motion behavior.

- [ ] Scope all new visual rules beneath the next-model chapter selector. Introduce local tokens without changing the rest of the product story:

  ```css
  .pimm30-chapter[data-chapter-role='next_model'] {
    --pimm50-bg: #08090b;
    --pimm50-panel: #111317;
    --pimm50-text: #f4f2ed;
    --pimm50-muted: #aaa9a5;
    --pimm50-red: #d51f1f;
    --pimm50-red-dark: #760d0d;
    --pimm50-font-impact: 'Antonio', var(--maliev-font-sans);
    color: var(--pimm50-text);
    background: var(--pimm50-bg);
    isolation: isolate;
  }
  ```

- [ ] Add restrained CSS atmosphere behind the transparent media using pseudo-elements. Use a dark neutral base, one soft red radial source, and subtle grain/noise if already available in theme assets. Never place a gradient or opacity wash over the machine.

- [ ] On desktop at `min-width: 990px`, implement a 40/60 content/media split:

  ```css
  .pimm30-chapter[data-chapter-role='next_model'] .pimm30-chapter__inner {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
    min-height: 100svh;
  }
  ```

  Keep copy within the left column, center the complete machine and shadow inside the right column, and prevent any text from overlaying the product.

- [ ] Use Antonio only for the 50G title, fact values, live product title, live price, and primary CTA label. Keep descriptions, availability, lead time, and Thai body copy in the existing MALIEV/Thai font families.

- [ ] Style the title as `PIMM 50G` with tight but readable tracking. Use oxidized red as emphasis, not as a glow. Keep the three facts in a semantic list with compact dividers and no glass cards.

- [ ] On mobile, keep the chapter full viewport below the transparent header where content fits, but allow natural overflow on short/zoomed screens. Position the title first, then the complete machine, facts, commerce summary, and CTA. Do not use a phone-frame graphic or a nested scroll container.

- [ ] Keep the entire mobile machine and contact shadow visible with safe inline margins. Use `object-fit: contain` and explicit `object-position` tuned to the mobile camera; do not enlarge by clipping the cylinder, controller, feet, fog, or shadow.

- [ ] Style `Made to order` distinctly from `Out of stock` and display the 30-day lead time directly beside/below it. Do not use green stock styling.

- [ ] Give the CTA a solid red treatment with clear hover, active, and focus-visible states. Keep a minimum 44px touch target and preserve the current destination.

- [ ] Preserve the existing media lifecycle in `maliev-pimm-30g.js`: play when the next-model chapter becomes active, pause/reset when it leaves, and never preload offscreen video. Modify JavaScript only if a browser check shows the `loop` attribute is being overridden. If changed, add a test assertion for that exact behavior.

- [ ] Add reduced-motion rules so the poster is immediately visible, the video does not autoplay, and no pulsing CSS atmosphere runs:

  ```css
  @media (prefers-reduced-motion: reduce) {
    .pimm30-chapter[data-chapter-role='next_model']::before,
    .pimm30-chapter[data-chapter-role='next_model']::after {
      animation: none !important;
    }
  }
  ```

- [ ] Run focused tests again:

  ```powershell
  node --test scripts/tests/pimm50-red-stage.test.mjs
  ```

  Expected: all tests pass.

---

## Task 6: Validate the integrated chapter across media, commerce, and devices

**Files:**

- Validate all files changed in Tasks 1–5.
- Do not modify unrelated files discovered during validation.

**Interfaces:**

- Consumes: final local Shopify preview and generated media.
- Produces: build, test, browser, accessibility, and visual evidence sufficient to commit.

- [ ] Run the required build first:

  ```powershell
  npm run verify
  ```

  Expected: zero warnings and zero errors. Stop and fix any failure before browser validation.

- [ ] Run the focused suite:

  ```powershell
  node --test scripts/tests/pimm50-red-stage.test.mjs
  ```

  Expected: all tests pass with the final file set.

- [ ] Start or reuse the local Shopify preview without deploying:

  ```powershell
  npm run dev
  ```

  Expected: `http://127.0.0.1:9393/products/pneumatic-injection-molding-machine` loads the development theme.

- [ ] Validate 320×800, 390×844, 768×1024, 1024×768, and 1440×900 viewports. At every size confirm:

  - title, full machine, and complete contact shadow are visible;
  - no transparent-video rectangle or baked background appears;
  - fog stays behind the product and remains restrained;
  - the 5-second red-light loop has no visible seam;
  - text never overlays the machine;
  - the desktop content ratio reads as 40/60;
  - no horizontal scrollbar or clipped CTA appears;
  - price is the live THB value from Shopify;
  - availability reads `Made to order` / `ผลิตตามคำสั่งซื้อ`, not `In stock`;
  - lead time displays 30 days when no metafield override exists;
  - CTA navigates to the live 50G product;
  - scrolling past the chapter reaches the footer normally.

- [ ] Validate video lifecycle by scrolling into, away from, and back to the chapter. Confirm the video loops only while active, pauses offscreen, and resumes cleanly without flashing the previous chapter.

- [ ] Emulate `prefers-reduced-motion: reduce`. Confirm the poster is sharp, no autoplay/pulse occurs, all content and CTA remain available, and the browser uses ordinary page scrolling.

- [ ] Simulate video failure by blocking the two WebM requests. Confirm the transparent WebP poster and CSS atmosphere render without layout shift or a blank media region.

- [ ] Switch the storefront to Thai. Confirm Thai wrapping does not collide with media or facts and the made-to-order/lead-time wording is correct.

- [ ] Tab through the chapter. Confirm visible focus on the CTA, logical reading order, no focus trap, and adequate contrast for red/white/gray states.

- [ ] Recheck generated media sizes and repository state:

  ```powershell
  Get-Item assets/pimm50-red-stage-* | Select-Object Name,Length
  git status --short
  git diff --check
  ```

  Expected: media stays within budget, `git diff --check` is clean, and unrelated dirty files are unchanged.

- [ ] Stage only the theme integration, font/license, locale, template, and focused test:

  ```powershell
  git add -- assets/antonio-variable.ttf docs/licenses/Antonio-OFL.txt assets/maliev-shell.css assets/maliev-pimm-30g.css sections/maliev-pimm-30g-story.liquid snippets/maliev-pimm-30g-chapter.liquid locales/en.default.json locales/th.json templates/product.injection-molding-machine.json scripts/tests/pimm50-red-stage.test.mjs
  git diff --cached --check
  git diff --cached --stat
  git commit -m "feat: redesign the PIMM 50G presentation chapter"
  ```

  If `assets/maliev-pimm-30g.js` required a verified fix, include that file in this same coherent integration commit.

---

## Task 7: Completion audit and handoff

- [ ] Compare the final implementation line-by-line against:
  `docs/superpowers/specs/2026-08-06-pimm-50g-red-stage-design.md`.

- [ ] Confirm there are no placeholders, unverified claims, hardcoded price strings, `In stock` text for available 50G variants, baked typography, black video backgrounds, or accidental edits to the corrected Blender master.

- [ ] Record final evidence:

  ```powershell
  git log -3 --oneline
  git status --short
  npm run verify
  node --test scripts/tests/pimm50-red-stage.test.mjs
  ```

- [ ] Report:

  - whether the 50G red-stage goal was achieved;
  - exact theme and Blender files changed;
  - video dimensions, durations, alpha result, and sizes;
  - build/test counts and browser viewport checks;
  - commit hashes;
  - any residual browser codec or performance risk;
  - explicit confirmation that nothing was pushed or deployed.
