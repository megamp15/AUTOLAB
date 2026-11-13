// Run on a loaded local VM detail view with charts:
// agent-browser eval --stdin < scripts/test_homepage_details.js
(async () => {
  const wait = async predicate => {
    const end = performance.now() + 10000;
    while (!predicate()) {
      if (performance.now() > end) throw new Error('Detail update timed out');
      await new Promise(resolve => setTimeout(resolve, 50));
    }
  };
  await wait(() => document.querySelector('.d-chart') && document.querySelector('.d-updated')?.dataset.loading === 'false');
  const root = document.querySelector('.a-detail'), header = document.querySelector('.d-header');
  const charts = document.querySelector('.d-charts'), scroll = document.querySelector('#rows').scrollTop;
  const original = window.fetch;
  window.fetch = async (...args) => {
    if (String(args[0]).includes('api/detail')) await new Promise(resolve => setTimeout(resolve, 150));
    return original(...args);
  };
  try {
    for (const range of ['6h', '24h', '1h']) {
      const button = [...document.querySelectorAll('.d-range button')].find(b => b.textContent === range);
      if (button.getAttribute('aria-pressed') === 'true') continue;
      const firstChart = document.querySelector('.d-chart'); button.click();
      if (root !== document.querySelector('.a-detail') || header !== document.querySelector('.d-header') || firstChart !== document.querySelector('.d-chart')) throw new Error('History switch rebuilt the page or cleared charts');
      if (document.querySelector('.d-updated').dataset.loading !== 'true') throw new Error('Loading indicator missing');
      await wait(() => document.querySelector('.d-updated').dataset.loading === 'false');
      if (charts !== document.querySelector('.d-charts') || document.querySelector('#rows').scrollTop !== scroll) throw new Error('History refresh changed layout or scroll');
    }
    if (document.querySelector('meter')) throw new Error('Native meter style returned');
    return {history:'stable', ranges:['1h','6h','24h'], charts:document.querySelectorAll('.d-chart').length};
  } finally { window.fetch = original; }
})()
