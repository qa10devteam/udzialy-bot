// Renders the carousel in every format: carousel/9x16, carousel/4x5, carousel/1x1 (PNG, 1080 px wide).
// In 9:16 slide 01 is the original cover supplied by BudOS (copied, not rendered).
// usage: FONTCACHE=<dir from fetch-fonts.sh ... carousel> node render-carousel.cjs [outRoot]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const outRoot = path.resolve(process.argv[2] || path.join(__dirname, '..', 'carousel'));
const NAMES = { '01': 'okladka', '02': 'zwiad', '03': 'filtry', '04': 'termin', '05': 'analiza-swz', '06': 'kosztorys', '07': 'wynik', '08': 'start' };
const FORMATS = { f916: '9x16', f45: '4x5', f11: '1x1' };
const src = fs.readFileSync(path.join(__dirname, '..', 'carousel.html'), 'utf8');
fs.mkdirSync(outRoot, { recursive: true });
const tmp = path.join(outRoot, '.page.html');
fs.writeFileSync(tmp, `<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>${src}</body></html>`);
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.error('PAGEERROR', e.message));
  const FC = process.env.FONTCACHE;
  if (FC) {
    await page.route('https://fonts.googleapis.com/**', r => r.fulfill({ status: 200, contentType: 'text/css', body: fs.readFileSync(path.join(FC, 'fonts.css'), 'utf8') }));
    await page.route('https://fonts.gstatic.com/**', r => r.fulfill({ status: 200, contentType: 'font/woff2', body: fs.readFileSync(path.join(FC, crypto.createHash('md5').update(r.request().url() + '\n').digest('hex').slice(0, 16) + '.woff2')) }));
  }
  await page.addInitScript(() => { window.__BUDOS_EXPORT = { carousel: true }; });
  await page.goto('file://' + tmp, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.__budosReady === true, null, { timeout: 30000 });
  for (const [f, dir] of Object.entries(FORMATS)) {
    await page.evaluate(f => window.__setFmt(f), f);
    const out = path.join(outRoot, dir); fs.mkdirSync(out, { recursive: true });
    for (const el of await page.$$('.slide[data-n]')) {
      if (!(await el.isVisible())) continue;
      const n = await el.getAttribute('data-n');
      await el.screenshot({ path: path.join(out, `${n}-${NAMES[n]}.png`) });
    }
    console.log('done', dir);
  }
  await browser.close(); fs.unlinkSync(tmp);
})();
