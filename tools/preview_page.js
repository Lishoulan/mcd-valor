// 本地起一个静态服务器并截图，验证演示页渲染正常
const http = require('http');
const fs = require('fs');
const path = require('path');
const puppeteer = require('C:/Users/Administrator/.workbuddy/binaries/node/workspace/node_modules/puppeteer-core');

const ROOT = process.argv[2];
const DOCS = path.join(ROOT, 'docs');
const PORT = 8899;
const MIME = { '.html': 'text/html', '.png': 'image/png', '.gif': 'image/gif',
  '.txt': 'text/plain', '.json': 'application/json' };

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/index.html';
  const f = path.join(DOCS, p);
  if (!f.startsWith(DOCS) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) {
    res.writeHead(404); res.end('not found'); return;
  }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});

(async () => {
  await new Promise(r => server.listen(PORT, r));
  const b = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    args: ['--no-sandbox', '--font-render-hinting=none'],
  });
  const p = await b.newPage();
  const errs = [];
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('requestfailed', r => errs.push('FAILED: ' + r.url().split('/').slice(-2).join('/')));
  await p.setViewport({ width: 1000, height: 900, deviceScaleFactor: 1 });
  // 模拟 Pages：站点根 = docs/
  await p.goto(`http://127.0.0.1:${PORT}/index.html`, { waitUntil: 'networkidle0' });
  const out = process.argv[3] || 'C:/Users/Administrator/AppData/Local/Temp/page.png';
  await p.screenshot({ path: out, fullPage: true });
  const h = await p.evaluate(() => document.body.scrollHeight);
  console.log('页面高度:', h, 'px');
  const imgs = await p.evaluate(() =>
    Array.from(document.images).map(i => ({ src: i.getAttribute('src'), ok: i.naturalWidth > 0 })));
  imgs.forEach(i => console.log('  图 ' + (i.ok ? 'OK ' : '坏 ') + i.src));
  console.log(errs.length ? '控制台问题:\n  ' + errs.join('\n  ') : '✓ 无资源加载失败');
  await b.close();
  server.close();
})();