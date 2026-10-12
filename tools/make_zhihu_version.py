"""生成知乎可直接粘贴的干净版：去掉附录、把表格转成列表。

用法：
  python tools/make_zhihu_version.py
产物：docs/engineering-postmortem-zhihu.md
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'docs', 'engineering-postmortem.md')
DST = os.path.join(ROOT, 'docs', 'engineering-postmortem-zhihu.md')

s = io.open(SRC, encoding='utf-8').read()

# 1. 去掉附录（从「## 附录」到文末）
s = re.split(r'\n## 附录：发知乎前请改这两处', s)[0]

# 2. 表格 → 列表（知乎会压扁表格）
TABLES = [
    # (表格起始标记, 列表替换文本)
    ('| 字段 | 实际情况 |', '- **`status` 恒为 2** —— 零区分度，看着能判断其实不能\n'
     '- **`downTime` 派对类是未来日期**（2027-12-31）—— 也不能判\n'
     '- **过滤 `spuId` 后仍 50 件全返回** —— **19 件其实已下架**'),
    ('| Bug | 代码做了什么 | 实际发生了什么 |',
     '1. **安装** —— 代码拼了下载 URL，实际指向一个不存在的分支\n'
     '2. **下架** —— 代码按性价比排序，实际排序结果里包含换不了的商品\n'
     '3. **外送** —— 代码给了一条出路，实际那条路从没被验证过\n'
     '4. **空账户** —— 代码正常渲染，实际从没在空数据下跑过\n'
     '5. **文档** —— 代码写了一行命令，实际那行命令少一个参数'),
]
for head, repl in TABLES:
    i = s.find(head)
    if i < 0:
        print('  ⚠ 没找到表格：%s' % head[:20])
        continue
    # 表格结束 = 第一个不以 | 开头的行
    j = s.find('\n', i)
    while j >= 0 and s[j + 1:j + 2] == '|':
        j = s.find('\n', j + 1)
    s = s[:i] + repl + s[j:]

# 3. 去掉「上面这张表如果发知乎…」那句提示
s = re.sub(r'\n?（上面这张表如果发知乎，记得手动转成列表.*?）\n', '\n', s)

io.open(DST, 'w', encoding='utf-8').write(s)

cn = len(re.findall(r'[\u4e00-\u9fff]',
                    re.sub(r'```.*?```', '', s, flags=re.S)))
print('已生成 %s' % os.path.relpath(DST, ROOT))
print('  中文字数（不含代码块）: %d' % cn)
print('  剩余表格: %d' % s.count('| --- |'))