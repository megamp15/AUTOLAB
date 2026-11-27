// Run against the homepage Architecture tab in a desktop browser, for example:
// agent-browser eval --stdin < scripts/test_homepage_canvas.js
// Uses actual wheel/reset controls and rendered SVG geometry, with no test hooks.
(async () => {
  await document.fonts.ready;
  window.scrollTo(0, document.documentElement.scrollHeight);
  const zoom = document.querySelector('.a-zoom.on');
  if (!zoom) throw new Error('Open the Architecture tab at a desktop viewport first');
  const canvas = zoom.querySelector('.a-canvas');
  const tick = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const scale = () => canvas.getBoundingClientRect().width / canvas.offsetWidth;
  await tick();
  const cards = [...canvas.querySelectorAll('.a-card')];
  const geometry = () => cards.map(card => [card.offsetWidth, card.offsetHeight]);
  const baseline = geometry();
  const results = [];
  for (const target of [1, .39, .15, 2, 4]) {
    const r = zoom.getBoundingClientRect();
    zoom.dispatchEvent(new WheelEvent('wheel', {
      bubbles: true, cancelable: true, ctrlKey: true,
      clientX: r.left + r.width / 2, clientY: r.top + r.height / 2,
      deltaY: -Math.log(target / scale()) / .0025,
    }));
    await tick();
    const next = geometry();
    if (next.some((size, i) => size.some((value, j) => Math.abs(value - baseline[i][j]) > .2))) {
      throw new Error(`Cards reflowed at ${Math.round(target * 100)}%`);
    }
    const boxes = [...canvas.querySelectorAll('[data-wire]')].map(element => ({
      key: element.dataset.wire, rect: element.getBoundingClientRect(),
    }));
    const paths = [...canvas.querySelectorAll('.a-wires path.a-wire:not(.a-signal-streak)')];
    if (!paths.length) throw new Error('No connection wires rendered');
    for (const path of paths) {
      const length = path.getTotalLength(), matrix = path.getScreenCTM();
      const screenPoint = d => path.getPointAtLength(d).matrixTransform(matrix);
      for (const distance of [0, length]) {
        const p = screenPoint(distance);
        const touches = boxes.some(({rect: b}) => {
          const tolerance = 2 * scale();
          const withinX = p.x >= b.left - tolerance && p.x <= b.right + tolerance;
          const withinY = p.y >= b.top - tolerance && p.y <= b.bottom + tolerance;
          return withinX && withinY && Math.min(Math.abs(p.x - b.left), Math.abs(p.x - b.right), Math.abs(p.y - b.top), Math.abs(p.y - b.bottom)) <= tolerance;
        });
        if (!touches) throw new Error(`Disconnected wire at ${target}: ${path.getAttribute('d')}`);
      }
      for (let d = 3; d < length - 3; d += 4) {
        const p = screenPoint(d), inset = 2 * scale();
        const crossed = boxes.find(({key, rect: b}) => key !== 'internet' && p.x > b.left + inset && p.x < b.right - inset && p.y > b.top + inset && p.y < b.bottom - inset);
        if (crossed) throw new Error(`Wire crosses ${crossed.key} at ${target}: ${path.getAttribute('d')}`);
      }
    }
    results.push({zoom: Math.round(target * 100), cards: cards.length, connectedWires: paths.length});
  }
  const privatePaths = [...canvas.querySelectorAll('path.a-tailnet')];
  for (const host of canvas.querySelectorAll('.a-row-nodes > .a-node')) {
    const box = host.getBoundingClientRect(), tolerance = 2 * scale();
    const connected = privatePaths.some(path => {
      const end = path.getPointAtLength(path.getTotalLength()).matrixTransform(path.getScreenCTM());
      return end.x >= box.left && end.x <= box.right && Math.abs(end.y - box.top) < tolerance;
    });
    if (!connected) throw new Error(`Missing private management connection for ${host.dataset.wire}`);
  }
  // The same packet must travel through the whole journey at one speed,
  // including its hidden passage through Cloudflare or the front door.
  const svg = canvas.querySelector('.a-wires');
  const journeys = [...svg.querySelectorAll('.a-journey')];
  if (journeys.length < 2) throw new Error('Expected public and private packet journeys');
  const before = svg.getCurrentTime();
  svg.pauseAnimations();
  try {
    for (const [i, path] of journeys.entries()) {
      const circle = svg.querySelector(`[data-journey="${i}"]`);
      const motion = circle.querySelector('animateMotion');
      const duration = parseFloat(motion.getAttribute('dur'));
      const moving = parseFloat(motion.getAttribute('keyTimes').split(';')[1]);
      const speed = path.getTotalLength() / (duration * moving);
      if (Math.abs(speed - 90) > .01) throw new Error(`Packet journey ${i} changes speed`);
      for (const time of [.25, .75]) {
        svg.setCurrentTime(time);
        const expected = path.getPointAtLength(time * speed).matrixTransform(path.getCTM());
        const actual = circle.getCTM();
        if (Math.hypot(actual.e - expected.x, actual.f - expected.y) > .5) {
          throw new Error(`Packet journey ${i} is out of sync at ${time}s`);
        }
      }
    }
  } finally {
    svg.setCurrentTime(before);
    svg.unpauseAnimations();
  }
  document.querySelector('.a-zoomctl [data-reset]').click();
  await tick();
  if (!document.querySelector('.a-zoomctl [data-reset]').disabled) throw new Error('Reset did not return to fit');
  console.log('Homepage canvas passed', results);
  return results;
})()
