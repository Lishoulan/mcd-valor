// 把本地 HTML 渲染成 PNG（README 配图）
const puppeteer = require('puppeteer-core');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

(async () => {
  const [, , inFile, outFile] = process.argv;
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--font-render-hinting=none'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1000, height: 700, deviceScaleFactor: 2 });
  await page.goto('file:///' + inFile.replace(/\\/g, '/'), { waitUntil: 'networkidle0' });
  await page.screenshot({ path: outFile, fullPage: true });
  await browser.close();
  console.log('saved', outFile);
})();
