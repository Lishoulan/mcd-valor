#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用真实MCP 输出生成 README 首屏演示 GIF。

原理：不像截图那样逐帧处理像素，而是用 Pillow **逐帧绘制终端风格文字**，
再用 `save_all + append_images` 合成动画 GIF。
这是唯一绕开GIF 编码难点的可靠路径（无ffmpeg / ImageMagick 依赖）。

注意：Pillow 仅用于**生成配图**。积值本身运行零第三方依赖。

用法：
    python -m butler value > value.txt        # 先抓真实输出（MCD_BUTLER_COLOR=1）
    python tools/make_demo_gif.py value.txt demo.gif

依赖：Pillow（pip install Pillow）
"""

import re
import sys
import unicodedata

from PIL import Image, ImageDraw, ImageFont

# ---------- 画布 ----------
W = 900
H_MAX = 1180              # 最多显示到多少像素高
BAR_H = 38
PAD = 18
LINE_H = 19
FONT_MONO = "C:/Windows/Fonts/consola.ttf"
# 中文必须用等宽字体，否则表格列会歪。
# SimHei 实测：中=15.0 宽、数字=8.0 与 consola 完全一致，
# 且「中中」宽度正好是单个的两倍（比例 2.00）。
# 微软雅黑虽然也有这个比例，但数字宽 9.0 与 consola 的 8.0 不一致，会错位。
FONT_CJK = "C:/Windows/Fonts/SimHei.ttf"
FS = 14

# GitHub 暗色终端配色
BG = (13, 17, 23)
BAR_BG = (22, 27, 34)
BORDER = (48, 54, 61)
FG = (201, 209, 217)
MUTED = (139, 148, 158)
RED = (255, 107, 107)
GREEN = (126, 231, 135)
YELLOW = (255, 212, 121)
CYAN = (118, 227, 234)
GREY = (139, 148, 148)
WHITE = (240, 246, 252)
RULE = (72, 79, 88)
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 64)]

SGR = {"0": None, "1": "bold", "2": "dim", "31": "red", "32": "green",
       "33": "yellow", "34": "blue", "36": "cyan", "90": "grey"}
COLOR = {"red": RED, "green": GREEN, "yellow": YELLOW,
         "cyan": CYAN, "grey": GREY, None: FG}

mono = ImageFont.truetype(FONT_MONO, FS)
cjk = ImageFont.truetype(FONT_CJK, FS)


def wide(ch):
    return unicodedata.east_asian_width(ch) in ("W", "F")


def tokens(line):
    """把带 ANSI 的行拆成 [(text, colorkey, bold)]。"""
    out, last, stack = [], 0, []
    for m in re.finditer(r"\x1b\[([0-9;]*)m", line):
        if m.start() > last:
            out.append((line[last:m.start()], stack[-1] if stack else None,
                        "bold" in stack))
        for c in m.group(1).split(";"):
            if not c:
                continue
            n = SGR.get(c, "?")
            if n is None:
                stack = []
            elif n != "?":
                stack.append(n)
        last = m.end()
    if last < len(line):
        out.append((line[last:], stack[-1] if stack else None, "bold" in stack))
    return out


BOX = "┌┐└┘├┤┬┴┼─│━┃╭╮╰╯═ "

# 字体缺字形的符号（emoji / 特殊图形）——直接不画，避免出现豆腐块
SKIP = set("🍔💎🔥✓✗⚠⚑★☆●○├→←↑↓•◆■□▍▏░▒▓")


def is_rule(line):
    """框线行：整行只有制表符和空格 -> 画成一条横线。"""
    s = line.strip()
    return bool(s) and all(ch in BOX for ch in s) and any(ch in BOX for ch in "─━═")


def draw_line(d, x, y, line):
    for text, ck, bold in tokens(line):
        col = COLOR.get(ck, FG)
        if ck == "dim":
            col = MUTED
        buf = ""
        for ch in text:
            if ch in SKIP:
                if buf:
                    x = _flush(d, x, y, buf, col)
                    buf = ""
                continue
            if ch in BOX:
                if buf:
                    x = _flush(d, x, y, buf, col)
                    buf = ""
                x += mono.getlength("─")   # 跳过绘制，但保留占位宽度
                continue
            buf += ch
        if buf:
            x = _flush(d, x, y, buf, col)
    return x


def _flush(d, x, y, buf, col):
    """按宽字符占两格绘制，保证中文表格能对齐。"""
    for ch in buf:
        if wide(ch):
            d.text((x, y), ch, font=cjk, fill=col)
            x += cjk.getlength(ch)          # 中文本来就占两格宽
        else:
            d.text((x, y), ch, font=mono, fill=col)
            x += mono.getlength(ch)
    return x


def render(lines, shown, path):
    img = Image.new("RGB", (W, H_MAX), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, BAR_H], fill=BAR_BG)
    d.line([0, BAR_H, W, BAR_H], fill=BORDER)
    for i, c in enumerate(DOTS):
        d.ellipse([14 + i * 18, BAR_H // 2 - 5, 24 + i * 18, BAR_H // 2 + 5], fill=c)
    d.text((76, BAR_H // 2 - 8), "mcd-valor — python -m butler value",
           font=mono, fill=MUTED)

    y = BAR_H + PAD
    # 命令行
    d.text((PAD, y), "$", font=mono, fill=GREEN)
    d.text((PAD + 12, y), "python -m butler value", font=mono, fill=WHITE)
    y += LINE_H + 8

    for i in range(shown):
        line = lines[i]
        if y > H_MAX - LINE_H:
            break
        if is_rule(line):
            d.line([PAD, y + 9, W - PAD, y + 9], fill=RULE)
        else:
            draw_line(d, PAD, y, line)
        y += LINE_H
    # 光标
    if shown < len(lines):
        d.rectangle([PAD, y + 2, PAD + 7, y + 15], fill=WHITE)
    img.save(path)


def main():
    src, out = sys.argv[1], sys.argv[2]
    raw = open(src, encoding="utf-8", errors="replace").read().replace("\r", "")
    lines = [l for l in raw.split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    lines = [""] + lines
    print("lines:", len(lines))

    frames = []
    step = 1
    idxs = list(range(0, len(lines), step)) + [len(lines) - 1]
    for n in idxs:
        p = "frames/f%03d.png" % n
        render(lines, n, p)
        frames.append(p)
    # 结尾停留 3 帧
    for _ in range(3):
        frames.append(frames[-1])
    print("frames:", len(frames))

    imgs = [Image.open(f).convert("P", palette=Image.ADAPTIVE, colors=128)
            for f in frames]
    imgs[0].save(out, save_all=True, append_images=imgs[1:],
                 duration=90, loop=0, optimize=True, disposal=2)
    print("saved", out)


if __name__ == "__main__":
    main()
