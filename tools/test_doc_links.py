"""检查文档里的相对链接是否指向真实存在的文件。

理由：README 里点不开的链接 = 功能缺失。评审和用户都会点。

用法（无需 Token）：
  python tools/test_doc_links.py
"""
import io
import os
import re
import glob
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = ('workbuddy/memory', '.git/', 'node_modules')

LINK = re.compile(r'\]\((?!https?://|#)([^)#]+?)(?:#[^)]*)?\)')

files = []
for pat in ('*.md', 'docs/*.md', 'tools/*.md', 'examples/*.md', 'docs/*.html'):
    files.extend(glob.glob(os.path.join(ROOT, pat)))

total = 0
broken = []
for f in sorted(set(files)):
    rel = os.path.relpath(f, ROOT)
    if any(s in rel.replace('\\', '/') for s in SKIP):
        continue
    try:
        s = io.open(f, encoding='utf-8').read()
    except (IOError, UnicodeDecodeError):
        continue
    for m in LINK.finditer(s):
        link = m.group(1).strip()
        if not link or link.startswith('mailto:'):
            continue
        total += 1
        target = os.path.normpath(os.path.join(os.path.dirname(f), link))
        if not os.path.exists(target):
            broken.append((rel, link))

print('扫描 %d 个文档，%d 条相对链接' % (len(set(files)), total))
if broken:
    print('\n失效 %d 条：' % len(broken))
    for src, link in broken:
        print('  ✗ %s  →  %s' % (src, link))
    sys.exit(1)
print('✓ 全部相对链接有效')