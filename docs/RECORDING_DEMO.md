# 🎬 录制演示 GIF（可选素材）

README 首屏目前用的是静态截图（`value-demo.png`）。
如果你想换成**动态 GIF**（逐行输出、颜色渐显、进度条填充，观感明显优于静态图），
下面是最省事的做法。

---

## 为什么本仓库没有现成的 GIF

录制脚本依赖一个**本机不一定有的 GIF 编码器**：

| 方案 | 本机情况 |
| --- | --- |
| `ffmpeg` / `gifsicle` | ❌ 未安装 |
| ImageMagick（`magick`） | ❌ 未安装（注意：Windows 自带的 `convert.exe` 是磁盘转换工具，**不是** ImageMagick） |
| `sharp` 的多页 GIF 输出 | ❌ sharp 0.33.5 + libvips 8.15.3 不支持写出多页 GIF（报 `field "n-pages" not found`） |
| Chrome `MediaRecorder('image/gif')` | ❌ 本机 Chrome 无此能力 |

所以这里**不提供**一个在本机跑不通的脚本 —— 与其留个坏工具，不如把选择权交给你。

---

## 方案一：装 ffmpeg（最省事，推荐）

```bash
# Windows（winget）
winget install Gyan.FFmpeg

# 或 choco
choco install ffmpeg
```

然后用你顺手的方式录制终端（Windows Terminal / PowerShell录屏、
OBS、ShareX 等），导出 GIF，再压到 5 MB 以内：

```bash
ffmpeg -i raw.mp4 -vf "fps=12,scale=720:-1:flags=lanczos,palettegen=stats_mode=diff" pal.png
ffmpeg -i raw.mp4 -i pal.png -lavfi "fps=12,scale=720:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" valor-demo.gif
gifsicle -O3 --lossy=80 valor-demo.gif -o valor-demo-optimized.gif
```

放进 `docs/images/` 后，在 README 首屏替换：

```markdown
![积值 valor 真实运行录屏](images/valor-demo.gif)
```

**建议尺寸**：宽度 ≤ 720px、体积 ≤ 5 MB。GitHub 会压缩过大的 GIF，
但超过 10 MB 时仓库克隆会明显变慢。

---

## 方案二：网页版在线转换（零安装）

用 [ezgif](https://ezgif.com/gif-encoder) 或
[cloudconvert](https://cloudconvert.com/png-to-gif)：

1. 截图若干张（每张对应一个输出阶段）
2. 上传，设置每帧 10-12 fps
3. 下载后放进 `docs/images/`

---

## 录什么内容最有说服力

按这个顺序剪，全是真数据、不用摆拍：

| 阶段 | 命令 | 关键看点 |
| --- | --- | --- |
| 1 | `python -m butler value` | 表格逐行浮现 → 「最划算」绿字 → 底部红色「已过期 2902.9 分」 |
| 2 | `python -m butler redeem` | 绿色「✓ 可用」与红色「✗ 不支持」交替出现，反差最强 |
| 3 | `python -m butler prizes` | 末尾红色「3 个白抽了」 |

**第2 段最抓眼**——「6 张券里只有 2 张能用」这个结论，
用颜色对比一秒钟就能看懂，静态截图反而没这个效果。

---

## 终端录制小技巧

- 字体调大一点（14px 以上），缩小后仍可读
- 只录终端窗口，别录整个桌面
- 语速放慢，让每行文字停留久一点（GIF 帧率低，太快看不清）
- 关掉可能泄露隐私的内容（其他窗口通知、书签栏）

---

## 提示

**演示素材只是加分项。** README 里最抓人的其实是那张
`value-demo.png` 的「50 积分换 18.8 元」——
数字本身就有冲击力，不需要动画加持也能讲清道理。

如果时间紧张，**优先做这些**（按性价比排序）：

1. 报名 Issue —— 不报名一切归零，**这是唯一的必做项**
2. 找3 个人点 Star —— 及格线就3 个
3. 演示 GIF —— 锦上添花
