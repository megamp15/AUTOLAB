// The architecture map across browsers, screen sizes and zoom levels.
// WebKit (Safari's engine) and Chromium, nine viewports from a phone to a
// 3440 ultrawide, every zoom from the whole map to 400%, and a double-click
// on three machines. At each step: no text spills out of a card, no card
// reflows, the drawing stays inside its frame, every wire meets its boxes,
// and a double-click fills the frame with that machine without navigating.
//
// Needs the preview running (python3 scripts/preview_homepage.py) and
// Playwright in a scratch folder, not in this repository:
//   npm i -E playwright@1.49.1 && npx playwright install webkit chromium
//   node <this repo>/scripts/test_homepage_map_matrix.mjs [screenshot dir]
import { chromium, webkit } from 'playwright';
const URL = 'http://127.0.0.1:8766/index.html#architecture';
const SHOTS = process.argv[2] || '.';
const VIEWPORTS = [[393, 852], [820, 1180], [1024, 768], [1280, 800], [1440, 900], [1728, 1117], [1920, 1080], [2560, 1440], [3440, 1440]];
const ZOOMS = ['fit', 0.15, 0.3, 0.5, 0.75, 1, 1.5, 2, 4];

const probe = () => {
  const zoom = document.querySelector('.a-zoom'), canvas = document.querySelector('.a-canvas');
  const F = zoom.getBoundingClientRect(), C = canvas.getBoundingClientRect();
  const on = zoom.classList.contains('on');
  const scale = C.width / canvas.offsetWidth;
  const cards = [...canvas.querySelectorAll('.a-card, .a-vm')];
  const spill = cards.filter(c => c.scrollWidth > c.clientWidth + 1).map(c => c.querySelector('.a-title')?.textContent.trim().slice(0, 18));
  const sizes = cards.map(c => [c.offsetWidth, c.offsetHeight]);
  const problems = [];
  if (on) {
    const axis = (a0, a1, f0, f1) => (a1 - a0) <= (f1 - f0) + 1 ? Math.abs((a0 - f0) - (f1 - a1)) < 3 : a0 <= f0 + 1 && a1 >= f1 - 1;
    if (!axis(C.left, C.right, F.left, F.right) || !axis(C.top, C.bottom, F.top, F.bottom)) problems.push('drawing not placed inside frame');
  } else if (document.documentElement.scrollWidth > innerWidth + 1) problems.push('page scrolls sideways');
  // Wires, in the map's own units (path coordinates and box offsets are both
  // unscaled), so WebKit's getScreenCTM bug under CSS transforms can't fool it.
  const pos = e => { let x = 0, y = 0, n = e; while (n && n !== canvas) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; } return { l: x, t: y, r: x + e.offsetWidth, b: y + e.offsetHeight }; };
  const boxes = [...canvas.querySelectorAll('[data-wire]')].map(pos);
  const svg = canvas.querySelector('.a-wires');
  let loose = 0, wires = 0;
  if (svg && getComputedStyle(svg).display !== 'none') for (const p of svg.querySelectorAll('path.a-wire:not(.a-signal-streak)')) {
    wires++;
    const L = p.getTotalLength();
    for (const d of [0, L]) {
      const pt = p.getPointAtLength(d), t = 3;
      if (!boxes.some(b => pt.x >= b.l - t && pt.x <= b.r + t && pt.y >= b.t - t && pt.y <= b.b + t)) loose++;
    }
  }
  // The toolbar above the map must not overflow or overlap.
  const tb = document.querySelector('.a-toolbar');
  if (tb && tb.scrollWidth > tb.clientWidth + 1) problems.push('toolbar overflows');
  if (loose) problems.push(`${loose} wire ends loose of ${wires * 2}`);
  if (spill.length) problems.push('text spills out of: ' + spill.slice(0, 4).join(', '));
  const titlePx = parseFloat(getComputedStyle(canvas.querySelector('.a-title')).fontSize) * scale;
  return { on, scale: +scale.toFixed(3), sizes, problems, titlePx: +titlePx.toFixed(1), label: document.querySelector('[data-live=zoom]')?.textContent };
};

async function setZoom(page, target) {
  if (target === 'fit') { await page.evaluate(() => { document.querySelector('.a-zoom').focus(); }); await page.keyboard.press('Escape'); return; }
  for (let i = 0; i < 3; i++) await page.evaluate(t => {
    const zoom = document.querySelector('.a-zoom'), canvas = zoom.querySelector('.a-canvas'), r = zoom.getBoundingClientRect();
    const s = canvas.getBoundingClientRect().width / canvas.offsetWidth;
    zoom.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true, ctrlKey: true, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, deltaY: -Math.log(t / s) / .0025 }));
  }, target);
}

let failures = 0, checks = 0;
for (const [name, engine] of [['webkit', webkit], ['chromium', chromium]]) {
  const browser = await engine.launch();
  for (const [w, h] of VIEWPORTS) {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    await page.goto(URL);
    await page.waitForTimeout(1200);
    await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
    await page.waitForFunction(() => document.querySelector('[data-sg-root]').classList.contains('arrived') && document.querySelector('.a-canvas'), null, { timeout: 15000 });
    await page.waitForTimeout(600);
    const on = await page.evaluate(() => document.querySelector('.a-zoom').classList.contains('on'));
    const levels = on ? ZOOMS : ['static'];
    let base = null;
    for (const z of levels) {
      if (on) { await setZoom(page, z); await page.waitForTimeout(250); }
      const r = await page.evaluate(probe);
      if (z === 'fit' || z === 'static') base = r.sizes;
      // Reflow: a card more than 20% taller or narrower than at fit.
      const reflow = r.sizes.filter((s, i) => base[i] && (s[1] > base[i][1] * 1.2 + 4 || s[0] < base[i][0] * 0.8 - 4)).length;
      if (reflow) r.problems.push(`${reflow} cards reflowed`);
      checks++;
      const tag = `${name} ${w}x${h} ${String(z).padEnd(6)}`;
      if (r.problems.length) { failures++; console.log(`FAIL ${tag} scale ${r.scale} (${r.label}): ${r.problems.join('; ')}`); }
      else console.log(`ok   ${tag} scale ${r.scale} title ${r.titlePx}px`);
      if ((w === 1440 || w === 393 || w === 3440) && [ 'fit', 0.15, 2, 'static'].includes(z)) await page.screenshot({ path: `${SHOTS}/${name}-${w}-${z}.png` });
    }
    if (on) for (const who of ['nebula', 'jwst', 'xps-pve']) {
      // Double-click a machine: it must fill the frame, every chip inside it
      // visible and on top (elementFromPoint hits it), then Escape fits again.
      await setZoom(page, 'fit'); await page.waitForTimeout(250);
      const pt = await page.evaluate(w => {
        const card = [...document.querySelectorAll('.a-vm, .a-node')].find(c => c.querySelector('.a-title')?.textContent.trim().startsWith(w));
        const r = card.querySelector('.a-sub, .a-spec').getBoundingClientRect(); return [r.right - 4, r.top + r.height / 2];
      }, who);
      await page.mouse.dblclick(pt[0], pt[1]); await page.waitForTimeout(300);
      const r = await page.evaluate(w => {
        const F = document.querySelector('.a-zoom').getBoundingClientRect();
        const card = [...document.querySelectorAll('.a-vm, .a-node')].find(c => c.querySelector('.a-title')?.textContent.trim().startsWith(w));
        const C = card.getBoundingClientRect(), problems = [];
        const inside = C.left >= F.left - 1 && C.right <= F.right + 1 && C.top >= F.top - 1 && C.bottom <= F.bottom + 1;
        const chips = [...card.querySelectorAll('.a-chip')].filter(x => x.closest('.a-vm, .a-node') === card);
        let hidden = 0;
        for (const x of chips) { const b = x.getBoundingClientRect(); const hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); if (!hit || !(x === hit || x.contains(hit))) hidden++; }
        if (!inside && C.height * (F.width / C.width) <= F.height) problems.push('card not fully in frame');
        if (hidden) problems.push(`${hidden}/${chips.length} chips not visible`);
        return { problems, hash: location.hash, label: document.querySelector('[data-live=zoom]').textContent, chips: chips.length };
      }, who);
      if (r.hash !== '#architecture') r.problems.push('double-click navigated away: ' + r.hash);
      checks++;
      const tag = `${name} ${w}x${h} dblclick ${who}`;
      if (r.problems.length) { failures++; console.log(`FAIL ${tag} (${r.label}): ${r.problems.join('; ')}`); } else console.log(`ok   ${tag} ${r.label} ${r.chips} chips`);
      if (w === 1440 && who === 'nebula') await page.screenshot({ path: `${SHOTS}/${name}-${w}-dbl-nebula.png` });
      await page.keyboard.press('Escape'); await page.waitForTimeout(200);
      if (r.hash !== '#architecture') { await page.goto(URL); await page.waitForTimeout(1500); }
    }
    await page.close();
  }
  await browser.close();
}
console.log(`\n${checks - failures}/${checks} passed`);
process.exit(failures ? 1 : 0);
