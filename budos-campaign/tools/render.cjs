// Renders the BudOS spot to PNG frames + WAV, then muxes MP4 with ffmpeg.
// usage: node render.cjs <format f169|f916|f45> <outDir> [fps=30] [--sheet t1,t2,...]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), { execFileSync } = require('child_process');
const [fmt = 'f169', outDir = 'out', fpsArg = '30', ...rest] = process.argv.slice(2);
const fps = +fpsArg;
const sheetIdx = rest.indexOf('--sheet');
const sheet = sheetIdx >= 0 ? rest[sheetIdx + 1].split(',').map(Number) : null;
const SIZES = { f169: [1920, 1080], f916: [1080, 1920], f45: [1080, 1350] };
const [W, H] = SIZES[fmt];
const src = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const html = `<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>${src}</body></html>`;
fs.mkdirSync(outDir, { recursive: true });
const pagePath = path.resolve(outDir, 'page.html'); fs.writeFileSync(pagePath, html);
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME || undefined, args: ['--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.error('PAGEERROR', e.message));
  page.on('console', m => { if (m.type() === 'error') console.error('CONSOLE', m.text()); });
  // serve Google Fonts from a local cache (filled by fetch-fonts.sh with curl, which trusts the proxy CA)
  const FC = process.env.FONTCACHE;
  if (FC) {
    const crypto = require('crypto');
    await page.route('https://fonts.googleapis.com/**', r => r.fulfill({ status: 200, contentType: 'text/css', body: fs.readFileSync(path.join(FC, 'fonts.css'), 'utf8') }));
    await page.route('https://fonts.gstatic.com/**', r => { const f = path.join(FC, crypto.createHash('md5').update(r.request().url() + '\n').digest('hex').slice(0, 16) + '.woff2'); r.fulfill({ status: 200, contentType: 'font/woff2', body: fs.readFileSync(f) }); });
  }
  await page.addInitScript(f => { window.__BUDOS_EXPORT = { format: f }; }, fmt);
  await page.goto('file://' + pagePath, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.__budosReady === true, null, { timeout: 30000 });
  const el = await page.$('#stage');
  if (sheet) {
    for (const t of sheet) { await page.evaluate(t => window.__budos.seek(t), t); await el.screenshot({ path: path.join(outDir, `s_${fmt}_${String(t).padStart(5, '0')}.png`) }); }
    await browser.close(); return;
  }
  const DUR = await page.evaluate(() => window.__budos.DUR);
  const wav = await page.evaluate(() => window.__budos.renderWav());
  fs.writeFileSync(path.join(outDir, 'audio.wav'), Buffer.from(wav, 'base64'));
  if (rest.includes('--wav-only')) { await browser.close(); return; }
  const n = Math.round(DUR * fps);
  const ff = require('child_process').spawn(process.env.FFMPEG, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-', '-i', path.join(outDir, 'audio.wav'),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', path.join(outDir, `budos-spot-${fmt}.mp4`)], { stdio: ['pipe', 'inherit', 'inherit'] });
  for (let i = 0; i < n; i++) {
    await page.evaluate(t => window.__budos.seek(t), i / fps);
    const buf = await el.screenshot({ type: 'jpeg', quality: 95 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 90 === 0) console.log(fmt, i, '/', n);
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r));
  await browser.close(); console.log('done', fmt);
})();
