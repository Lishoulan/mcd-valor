# tools/ · 配图生成脚本（**非运行依赖**）

> ⚠️ **这里的脚本不是积值运行的一部分。**
> `python -m butler` 只用 Python 标准库，不依赖 `tools/` 下任何东西。
> 本目录只用于生成 README 里的配图，方便复现与更新。

## 目录内容

| 文件 | 作用 | 依赖 |
| --- | --- | --- |
| **`record_run.py`** | **每日跑一次，追加跨天运行记录（最硬的实证）** | 无（标准库） |
| `make_demo_gif.py` | 逐帧绘制终端文字 → 动画 GIF（首屏演示） | Pillow |
| `render_shot.js` | 带ANSI 色的终端输出 → PNG | Node + puppeteer-core + Chrome |
| `render_html.js` | 本地 HTML → PNG（结构图） | 同上 |
| `assets.html` | 「三类资产」结构图的 HTML 源 | 无 |

## 跨天运行记录（最有价值的一个）

```bash
export MCD_MCP_TOKEN=你的Token
python tools/record_run.py          # 记录今天
python tools/record_run.py --show   # 只看已有记录
```

产物：
- `examples/run-log.jsonl` —— 每行一条 JSON（机器可读）
- `docs/RUN_LOG.md` —— 自动渲染成表格（人可读）

**为什么这个比配图重要**：券每天在过期、每天有新的进账。
所有参赛项目的 README 都只贴**某一刻**的截图，读者无法判断真假；
而这是一条随时间延伸的序列，**证明项目真的在持续运行**。

记录的「能用掉的」一列是**逐张券 × 逐家门店调`query-store-coupons`
交叉验证后**的结果，通常明显小于「3 天内到期」——差值就是注定归零的资产。

> 这是**可选**的，不需要每天跑。想攒证据就隔几天跑一次，
> 跑三五天已经足够说明问题。工具本身在需要的时候敲一条命令即可。


## 为什么 GIF 用 Python 而不是 ffmpeg

本机没有 `ffmpeg` / `gifsicle` / ImageMagick，浏览器也不支持
`MediaRecorder('image/gif')`，而 sharp/libvips 也不支持写出多页 GIF。

**关键技巧**：不截图、不处理像素，而是用 Pillow **逐帧把文字画出来**，
再用 `save_all + append_images` 合成 —— 这样根本不需要 GIF 编码器，
Pillow 自己就能完成。

```bash
# 1. 准备独立环境（不要污染项目的零依赖）
python -m venv .venv-tools
.venv-tools/Scripts/pip install Pillow

# 2. 抓真实输出（必须带颜色）
export MCD_BUTLER_COLOR=1
python -m butler value > /tmp/value.txt

# 3. 生成 GIF
.venv-tools/Scripts/python tools/make_demo_gif.py /tmp/value.txt \
  docs/images/valor-demo.gif
```

## 字体说明

脚本按字符宽度自动切换字体：ASCII 用 `CascadiaMono.ttf`，
中文用 `msyh.ttc`（微软雅黑）。这样中文表格才能真正对齐。

字体缺字形的符号（emoji、框线字符）会被**跳过不画**，
避免出现「豆腐块」方框。

## PNG 配图

```bash
export MCD_BUTLER_COLOR=1
python -m butler value > /tmp/v.txt
NODE_PATH=<puppeteer-core 路径> node tools/render_shot.js \
  /tmp/v.txt docs/images/value-demo.png "mcd-valor — python -m butler value"
```

## 图里的数据是真的

所有配图都是**真实调用麦当劳 MCP** 后的终端输出原样渲染，
**没有任何手写美化或伪造的数值**。跨天后券数会变属正常现象——
遇到与 README 不一致时，**以实际运行结果为准**，并同步更新 README。
