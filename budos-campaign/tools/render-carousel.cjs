// Renders every .slide[data-n] of carousel.html to carousel/NN-*.png (1080x1920).
// usage: FONTCACHE=<dir from fetch-fonts.sh carousel> node render-carousel.cjs <outDir>
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const outDir = process.argv[2] || path.join(__dirname, '..', 'carousel');
const NAMES = { '02': 'zwiad', '03': 'filtry', '04': 'termin', '05': 'analiza-swz', '06': 'kosztorys', '07': 'wynik', '08': 'start' };
const src = fs.readFileSync(path.join(__dirname, '..', 'carousel.html'), 'utf8');
const tmp = path.join(outDir, '.page.html');
fs.mkdirSync(outDir, { recursive: true });
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
  for (const el of await page.$$('.slide[data-n]')) {
    const n = await el.getAttribute('data-n');
    await el.screenshot({ path: path.join(outDir, `${n}-${NAMES[n]}.png`) });
  }
  await browser.close(); fs.unlinkSync(tmp); console.log('done');
})();
