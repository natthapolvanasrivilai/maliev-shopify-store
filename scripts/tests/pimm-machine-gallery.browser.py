"""Live local-only gallery regression checks. Run with the preview server already running."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.codex-tmp'
BASE = 'http://127.0.0.1:9494'


def open_page(browser, language='en', width=1440, **options):
    context = browser.new_context(viewport={'width': width, 'height': 1000 if width > 699 else 844}, **options)
    page = context.new_page()
    prefix = '/th' if language == 'th' else ''
    response = page.goto(f'{BASE}{prefix}/products/pneumatic-injection-molding-machine', wait_until='domcontentloaded')
    assert response and response.status == 200, f'Preview response {response.status if response else "missing"}: {language} {width}'
    page.wait_for_function("Boolean(customElements.get('pimm-machine-gallery'))")
    for name in ['Decline', 'ปฏิเสธ']:
        button = page.get_by_role('button', name=name, exact=True)
        if button.count() and button.is_visible():
            button.click()
    page.evaluate('document.fonts.ready')
    return context, page


def reveal(page):
    page.locator('pimm-machine-gallery').evaluate('(e) => window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 92)')


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page = open_page(browser)
        assert page.locator('[data-gallery-item]').count() == 3
        assert page.locator('[data-gallery-item][data-kind="image"]').count() == 0
        assert page.locator('[data-gallery-preview]').count() == 3
        assert page.locator('[data-gallery-preview][src]').count() == 0, 'Offscreen previews must not load'
        assert page.locator('.pimm-gallery iframe').count() == 0
        reveal(page)
        page.wait_for_function("[...document.querySelectorAll('[data-gallery-preview]')].every(v => !v.paused && !v.hidden && v.currentTime > .2)")
        assert page.locator('[data-gallery-preview]').evaluate_all('(vs) => vs.every(v => v.muted && v.loop && v.playsInline && !v.error)')
        page.wait_for_timeout(6800)
        assert page.locator('[data-gallery-preview]').evaluate_all('(vs) => vs.every(v => !v.paused && v.currentTime < 6.1 && v.duration === 6)')
        page.locator('[data-gallery-pause]').click()
        assert page.locator('[data-gallery-preview]').evaluate_all('(vs) => vs.every(v => v.paused)')
        page.locator('[data-gallery-pause]').click()
        reveal(page)
        page.wait_for_function("[...document.querySelectorAll('[data-gallery-preview]')].every(v => !v.paused)")
        page.locator('[data-gallery-open]').first.click()
        assert page.locator('dialog.pimm-gallery__viewer').evaluate('(d) => d.open')
        assert page.locator('[data-gallery-preview]').evaluate_all('(vs) => vs.every(v => v.paused)')
        frame_src = page.locator('.pimm-gallery iframe').get_attribute('src')
        assert 'SlCkqUcpZ_Y' in frame_src and 'autoplay=1' in frame_src and 'end=' not in frame_src
        frame = page.frame_locator('.pimm-gallery iframe')
        frame.locator('video').wait_for(timeout=30000)
        playing = frame.locator('video').evaluate('''(v) => new Promise(resolve => {
            let ticks = 0;
            const timer = setInterval(() => {
                if ((v.currentTime > 0 && !v.paused) || ++ticks > 100) {
                    clearInterval(timer); resolve(v.currentTime > 0 && !v.paused);
                }
            }, 250);
        })''')
        if not playing:
            page.screenshot(path=str(OUT / 'gallery-full-video-blocked.png'))
            print('Player state:', frame.locator('video').evaluate('(v) => ({time:v.currentTime,paused:v.paused,ready:v.readyState,error:v.error?.code})'))
        assert playing, 'Full video must play'
        page.screenshot(path=str(OUT / 'gallery-viewer-desktop.png'))
        for expected in ['PHqab73X5C0', 'zoRajgCbsko']:
            page.locator('[data-gallery-next]').click()
            assert expected in page.locator('.pimm-gallery iframe').get_attribute('src')
        page.locator('[data-gallery-next]').click()
        assert 'SlCkqUcpZ_Y' in page.locator('.pimm-gallery iframe').get_attribute('src')
        page.locator('[data-gallery-close]').focus()
        page.keyboard.press('Shift+Tab')
        assert page.evaluate("document.activeElement.closest('dialog') !== null"), 'Dialog focus trap'
        page.keyboard.press('Escape')
        assert not page.locator('dialog.pimm-gallery__viewer').evaluate('(d) => d.open')
        assert page.locator('[data-gallery-stage]').evaluate('(s) => s.childElementCount === 0')
        assert page.locator('[data-gallery-open]').first.evaluate('(e) => e === document.activeElement')
        page.evaluate('window.scrollTo(0,0)')
        page.wait_for_timeout(400)
        assert page.locator('[data-gallery-preview]').evaluate_all('(vs) => vs.every(v => v.paused)')
        context.close()
        print('PASS: video-only defaults, lazy autoplay, six-second loop, pause/resume, full videos, wraparound, Escape, focus and offscreen pause')

        for language in ['en', 'th']:
            for width in [320, 390, 768, 1440]:
                print(f'Checking {language} at {width}px')
                context, page = open_page(browser, language, width)
                reveal(page)
                page.wait_for_timeout(700)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow {language} {width}'
                assert page.locator('.pimm-gallery__heading h2').inner_text() == ('ชมการทำงานของ 30G' if language == 'th' else 'See the 30G in action.')
                assert page.locator('pimm-machine-gallery').evaluate('(g) => g.nextElementSibling.classList.contains("pimm-machine__purchase")')
                assert page.locator('[data-gallery-item]').evaluate_all('(items) => items.every(i => { const a=i.querySelector(".pimm-gallery__media").getBoundingClientRect(), b=i.querySelector(".pimm-gallery__caption").getBoundingClientRect(); return a.bottom <= b.top + 1; })')
                if width in [390, 1440]:
                    page.locator('pimm-machine-gallery').screenshot(path=str(OUT / f'gallery-{language}-{width}.png'))
                page.locator('[data-gallery-open]').first.click()
                assert page.locator('dialog.pimm-gallery__viewer').evaluate('(d) => { const r=d.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight; }')
                page.locator('[data-gallery-close]').click()
                context.close()
        print('PASS: EN/TH at 320, 390, 768, 1440; no overflow, unobscured media, bounded modal and booking placement')

        context, page = open_page(browser, reduced_motion='reduce')
        reveal(page)
        page.wait_for_timeout(800)
        assert page.locator('[data-gallery-preview][src]').count() == 0
        assert page.locator('[data-gallery-pause]').is_hidden()
        page.locator('[data-gallery-open]').first.click()
        assert page.locator('dialog.pimm-gallery__viewer').evaluate('(d) => d.open')
        context.close()
        print('PASS: reduced motion keeps stills without blocking the viewer')

        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        context.add_init_script("Object.defineProperty(navigator.connection, 'saveData', { get: () => true })")
        page = context.new_page()
        page.goto(f'{BASE}/products/pneumatic-injection-molding-machine', wait_until='domcontentloaded')
        reveal(page)
        page.wait_for_timeout(800)
        assert page.locator('[data-gallery-preview][src]').count() == 0
        context.close()
        print('PASS: data saver never requests preview video')

        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        context.add_init_script("const original=HTMLMediaElement.prototype.play; HTMLMediaElement.prototype.play=function(){return this.hasAttribute('data-gallery-preview') ? Promise.reject(new DOMException('Blocked','NotAllowedError')) : original.call(this)}")
        page = context.new_page()
        page.goto(f'{BASE}/products/pneumatic-injection-molding-machine', wait_until='domcontentloaded')
        reveal(page)
        page.wait_for_timeout(800)
        assert page.locator('[data-gallery-preview]').evaluate_all('(vs) => vs.every(v => v.hidden)')
        assert page.locator('[data-gallery-open]').first.get_attribute('href').startswith('https://www.youtube.com/')
        context.close()
        print('PASS: blocked autoplay retains poster and full-video destination')
        browser.close()


if __name__ == '__main__':
    run()
