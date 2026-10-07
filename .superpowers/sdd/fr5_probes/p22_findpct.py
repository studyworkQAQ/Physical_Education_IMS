import pathlib, re, collections
p = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\fr5_probes\p21_report.py")
src = p.read_text(encoding="utf-8")
i = src.index('SEC = """')
j = src.index('"""', i + 9)
sec = src[i + 9:j]
c = collections.Counter()
for m in re.finditer(r"%.", sec, re.S):
    c[m.group(0)] += 1
print("所有 '%%+下一个字符' 的出现次数：")
for k, v in sorted(c.items()):
    print("   %r x%d" % (k, v))
print()
print("所有 %%(name)s 形式：", re.findall(r"%\(\w+\)\w", sec))
print()
for m in re.finditer(r"%[^%(]", sec):
    k = m.start()
    print("   非 %% 非 named @%5d: %r   ctx=...%s" % (k, sec[k:k + 3], sec[max(0, k - 60):k + 20].replace("\n", "\\n")))
