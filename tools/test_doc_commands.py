"""从各文档里抽出所有 `python -m butler ...` 示例，逐条实跑。

目的：文档里写的命令必须真的能跑。文档与实现脱节 = 文档 bug。

用法（需要真实 Token，命令会真的调接口）：
  export MCD_MCP_TOKEN=你的Token
  python tools/test_doc_commands.py
"""
import io
import re
import subprocess
import sys
import os

PY = sys.executable
# 本文件在 tools/ 下，仓库根是它的上一级
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = ['README.md', 'SKILL.md', 'MCP_INTEGRATION.md', 'CONTEST_DECLARATION.md',
        'docs/index.html', 'docs/zhihu-article.md', 'examples/README.md',
        'tools/README.md', 'workbuddy.md']

# 命令后面跟的可能是注释、重定向、管道、引号或行尾标点，一律截断
TAIL = re.compile(r'[#>|`\'"<].*$')
pat = re.compile(r'python -m butler\b([^>|\n]*)')
# 占位符不是真命令：`butler <命令>`、但ler `value` 等
PLACEHOLDER = re.compile(r'^[<`\'"]|[\u4e00-\u9fff]{2,}')

seen = {}
for d in DOCS:
    p = os.path.join(ROOT, d)
    if not os.path.exists(p):
        continue
    for i, line in enumerate(io.open(p, encoding='utf-8').read().split('\n'), 1):
        for m in pat.finditer(line):
            cmd = TAIL.sub('', m.group(1)).strip()
            if not cmd or cmd.startswith('-h'):
                continue
            if PLACEHOLDER.match(cmd):
                continue          # `butler <命令>` / 但ler "value" 这类占位
            seen.setdefault(cmd, []).append('%s:%d' % (d, i))

print('文档里出现的命令共 %d 条' % len(seen))
if not seen:
    print('（没抽到任何命令 —— 提取正则本身可能坏了）')
    sys.exit(2)
print()

ok = fail = 0
env = dict(os.environ)
env['PYTHONPATH'] = ROOT
env['PYTHONIOENCODING'] = 'utf-8'
for cmd in sorted(seen):
    try:
        r = subprocess.run([PY, '-m', 'butler'] + cmd.split(),
                           capture_output=True, text=True, timeout=200,
                           cwd=ROOT, env=env)
        src = ', '.join(seen[cmd])
        bad = r.returncode != 0 or 'Traceback' in r.stderr
        if not bad:
            ok += 1
            first = (r.stdout.strip().split('\n') or [''])[0][:40]
            print('  ✓ butler %-32s %s' % (cmd, first))
        else:
            fail += 1
            print('  ✗ butler %-32s exit=%d  见于 %s' % (cmd, r.returncode, src))
            tail = [x for x in r.stderr.strip().split('\n') if x.strip()]
            if tail:
                print('      %s' % tail[-1][:96])
    except subprocess.TimeoutExpired:
        fail += 1
        print('  ✗ butler %-32s 超时  见于 %s' % (cmd, ', '.join(seen[cmd])))

print('\n通过 %d 条，失败 %d 条' % (ok, fail))
sys.exit(1 if fail else 0)