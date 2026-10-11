# tools/ · 配图生成脚本（非运行依赖）

>⚠️ **这里的脚本不是积值运行的一部分。**
> `python -m butler` 只用 Python 标准库，不依赖 `tools/` 下任何东西。
> 本目录只是用来生成 README 里的配图，方便后续复现与更新。

## 用途

| 脚本 | 作用 |
| --- | --- |
| `render_shot.js` | 把带 ANSI 色的终端输出渲染成 PNG（README 首屏演示图） |
| `render_html.js` | 把本地 HTML 渲染成 PNG（结构图） |
| `assets.html` | 「三类资产」结构图的HTML 源 |

## 依赖

需要 Node.js + `puppeteer-core` + 本机已安装的 Chrome/Edge。
**这些只在本机生成配图时需要**，与参赛项目的运行无关。

```bash
# 抓取带颜色的真实输出
export MCD_BUTLER_COLOR=1
python -m butler value > /tmp/value.txt

# 渲染成图
NODE_PATH=<puppeteer-core所在路径> node tools/render_shot.js \
  /tmp/value.txt docs/images/value-demo.png "mcd-valor — python -m butler value"
```

## 图里的数据是真的

所有配图都是**真实调用麦当劳 MCP** 后的终端输出原样渲染，
没有任何手写美化或伪造的数值。跨天后券数会变属正常现象。
