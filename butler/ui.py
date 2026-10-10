# -*- coding: utf-8 -*-
"""终端渲染小工具：ANSI 颜色、表格、进度式输出。"""

import os
import sys

_FORCE = os.environ.get("MCD_BUTLER_COLOR", "").lower()
if _FORCE in ("1", "always", "true"):
    ENABLE = True
elif _FORCE in ("0", "never", "false"):
    ENABLE = False
else:
    ENABLE = sys.stdout.isatty() and os.environ.get("TERM") != "dumb" and not os.environ.get("NO_COLOR")


def _c(code):
    return ("\033[%sm" % code) if ENABLE else ""


RESET = _c("0")
BOLD = _c("1")
DIM = _c("2")
RED = _c("31")
GREEN = _c("32")
YELLOW = _c("33")
BLUE = _c("34")
MAGENTA = _c("35")
CYAN = _c("36")
GREY = _c("90")

BRAND = "\033[38;5;208m" if ENABLE else ""   # 麦当劳金黄
BRAND_RESET = RESET


def brand(text):
    return BRAND + text + BRAND_RESET


def bold(text):
    return BOLD + str(text) + RESET


def red(text):
    return RED + str(text) + RESET


def green(text):
    return GREEN + str(text) + RESET


def yellow(text):
    return YELLOW + str(text) + RESET


def cyan(text):
    return CYAN + str(text) + RESET


def grey(text):
    return GREY + str(text) + RESET


def title(text, width=64):
    """带品牌色的标题条。"""
    bar = "─" * width
    top = BRAND + bold("┌" + bar) + BRAND_RESET
    mid = BRAND + bold("│ ") + brand(text) + " " * max(0, width - 2 - _w(text)) + BRAND + bold("│") + BRAND_RESET
    bot = BRAND + bold("└" + bar) + BRAND_RESET
    return "\n" + "\n".join((top, mid, bot))


def kv(label, value, label_w=14, color=None):
    value = str(value)
    if color:
        value = color(value)
    return "  %s %s" % (grey(("%-*s" % (label_w, label))), value)


def rule(width=64, ch="─"):
    return grey(ch * width)


def table(headers, rows, aligns=None, indent="  "):
    """极简对齐表格。aligns: list of 'l'/'r'。"""
    cols = len(headers)
    aligns = aligns or ["l"] * cols
    widths = []
    for i in range(cols):
        w = _w(headers[i])
        for row in rows:
            w = max(w, _w(_plain(row[i])))
        widths.append(w)

    def fmt(cells, bold_row=False):
        out = []
        for i in range(cols):
            cell = _plain(cells[i])
            if aligns[i] == "r":
                out.append(cell.rjust(widths[i]))
            else:
                out.append(cell.ljust(widths[i]))
        line = indent + "  ".join(out)
        return bold(line) if bold_row else line

    lines = [fmt(headers, bold_row=True), indent + grey("  ".join("─" * w for w in widths))]
    for row in rows:
        lines.append(fmt(row))
    return "\n".join(lines)


def bar(value, vmax, width=18, ch="█"):
    if vmax <= 0:
        return ""
    n = max(1, int(round(width * value / float(vmax)))) if value > 0 else 0
    return ch * n


def _plain(text):
    """去掉 ANSI 序列，用于计算显示宽度。"""
    if not ENABLE:
        return str(text)
    out, i = [], 0
    s = str(text)
    while i < len(s):
        if s[i] == "\033":
            j = s.find("m", i)
            if j == -1:
                break
            i = j + 1
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _w(text):
    """中文按2 列宽计算，保证表格真正对齐。"""
    text = _plain(text)
    return sum(2 if _is_wide(ch) else 1 for ch in text)


def truncate(text, width):
    """按显示宽度截断（中文算 2 列），超出加省略号。"""
    text = _plain(text)
    if _w(text) <= width:
        return text
    out, n = [], 0
    for ch in text:
        cw = 2 if _is_wide(ch) else 1
        if n + cw > width - 1:
            break
        out.append(ch)
        n += cw
    return "".join(out) + "…"


def _is_wide(ch):
    import unicodedata
    return unicodedata.east_asian_width(ch) in ("W", "F")


def pad(text, width, align="l"):
    text = _plain(text)
    gap = width - _w(text)
    gap = gap if gap > 0 else 0
    if align == "r":
        return " " * gap + text
    if align == "c":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def out(line=""):
    sys.stdout.write(line + "\n")


def rule_out(width=64):
    out(grey("─" * width))
