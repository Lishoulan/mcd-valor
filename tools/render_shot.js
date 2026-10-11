// 把带 ANSI 色的终端输出渲染成 PNG（用于 README 配图）
// 用法: node render_shot.js <输入txt> <输出png> <标题> <副标题>
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const MONO = 'Cascadia Mono, Consolas, SF Mono, DejaVu Sans Mono, monospace';
const CJK = 'Microsoft YaHei UI, Microsoft YaHei, PingFang SC, sans-serif';

const SGR = {
  '0': 'reset', '1': 'bold', '2': 'dim',
  '31': 'red', '32': 'green', '33': 'yellow', '34': 'blue',
  '35': 'magenta', '36': 'cyan', '90': 'grey',
};
const FG = {
  red: '#ff6b6b', green: '#7ee787', yellow: '#ffd479', blue: '#79c0ff',
  magenta: '#d2a8ff', cyan: '#76e3ea', grey: '#8b949e', reset: '#e6edf3',
};

// ANSI -> HTML
function ansiToHtml(raw) {
  let out = '';
  let open = 0;
  const re = /\x1b\[([0-9;]*)m/g;
  let last = 0, m;
  while ((m = re.exec(raw)) !== null) {
    out += esc(raw.slice(last, m.index));
    const codes = m[1].split(';').filter(Boolean);
    for (const c of codes) {
      const name = SGR[c];
      if (!name) continue;
      if (name === 'reset') {
        while (open > 0) { out += '</span>'; open--; }
      } else {
        out += `<span class="${name}">`; open++;
      }
    }
    last = re.lastIndex;
  }
  out += esc(raw.slice(last));
  while (open > 0) { out += '</span>'; open--; }
  return out;
}
function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

(async () => {
  const [, , inFile, outFile, title, subtitle] = process.argv;
  const body = ansiToHtml(fs.readFileSync(inFile, 'utf8'));

  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:#0d1117;padding:0;font-family:${CJK};width:960px}
  .win{background:#0d1117}
  .bar{background:#161b22;border-bottom:1px solid #30363d;padding:11px 16px;
       display:flex;align-items:center;gap:8px}
  .d{width:12px;height:12px;border-radius:50%}
  .t{margin-left:10px;color:#8b949e;font-size:12px;font-family:${MONO}}
  pre{margin:0;padding:18px 20px 20px;color:${FG.reset};
      font-family:${MONO};font-size:12.5px;line-height:1.5;
      white-space:pre;tab-size:4}
  .bold{font-weight:700}
  .dim{opacity:.62}
  .red{color:${FG.red}} .green{color:${FG.green}} .yellow{color:${FG.yellow}}
  .blue{color:${FG.blue}} .magenta{color:${FG.magenta}} .cyan{color:${FG.cyan}}
  .grey{color:${FG.grey}}
  </style></head><body><div class="win">
  <div class="bar">
    <div class="d" style="background:#ff5f57"></div>
    <div class="d" style="background:#febc2e"></div>
    <div class="d" style="background:#28c840"></div>
    <div class="t">${esc(title)}</div>
  </div>
  <pre>${body}</pre>
  </div></body></html>`;

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--font-render-hinting=none'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1000, height: 800, deviceScaleFactor: 2 });
  await page.setContent(html, { waitUntil: 'networkidle0' });
  const el = await page.$('.win');
  await el.screenshot({ path: outFile });
  await browser.close();
  console.log('saved', outFile, fs.statSync(outFile).size, 'bytes');
})();
