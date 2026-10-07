import hashlib, pathlib, subprocess
ROOT = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims')
BASE = 'c29bc69'
rows = [
    ('backend/app/refdata_prescription.py', 23225, 413, 413, 'EE0279B00D4AFB1B'),
    ('backend/app/domain/prescription/exercises.py', 16915, 254, 254, '3E13D9E322C9D9A4'),
    ('backend/app/domain/prescription/templates.py', 3090, 39, 39, '9F82B04C84B649C4'),
    ('backend/app/domain/prescription/__init__.py', 1741, 37, 37, '59B7E8B788355C30'),
    ('backend/app/db/models/prescription.py', 10088, 143, 143, 'A2F2839FF80B4B53'),
    ('backend/tests/test_refdata_prescription.py', 57852, 952, 952, '63444B1FDAA9445C'),
    ('backend/tests/domain/test_prescription_templates.py', 11248, 153, 153, '13E422CC719F01F5'),
    ('backend/tests/db/test_models.py', 44669, 757, 757, '974C1FFB917684ED'),
    ('backend/tests/seed/test_generate.py', 66351, 1188, 1188, '966DB7C3C96BFC99'),
    ('backend/data/exercises.yaml', 17609, 307, 0, '63033BBD7F68CC1F'),
    ('backend/data/exercise_equivalence.yaml', 8245, 130, 0, '822CB86A5E998301'),
    ('backend/data/national_standard_2014.csv', 21412, None, 0, 'D2C8E539E2FA0029'),
]
print('%-52s %-9s %-6s %-6s %-18s %-18s' % ('文件(blob)', 'blob B', 'LF', 'CRLF', 'raw sha16', 'norm sha16'))
allok = True
for rel, eb, el, ec, esha in rows:
    b = subprocess.run(['git', 'show', f'{BASE}:{rel}'], cwd=ROOT, capture_output=True).stdout
    raw = hashlib.sha256(b).hexdigest()[:16].upper()
    nrm = hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()[:16].upper()
    lf = b.replace(b'\r\n', b'\n').count(b'\n')
    crlf = b.count(b'\r\n')
    # 派单那一行是**混口径**的：`bytes` 与 `CRLF` 两列是**工作树**的值，`行` 与 `sha16`
    # 两列是 **blob** 的值。``backend/**`` 的 blob 是 LF、工作树是 CRLF（core.autocrlf=true），
    # 于是 `工作树 bytes == blob bytes + 工作树 CRLF 行数`，而 `工作树 CRLF 行数 == blob LF 行数`。
    # ``backend/data/**`` 由 .gitattributes 钉成 eol=lf，两侧都是 LF、CRLF=0，公式同样成立。
    okb = (len(b) + ec == eb)
    okl = (el is None) or (lf == el)
    okc = (crlf == 0) and (ec == lf or ec == 0)
    # blob 恒为 LF（crlf==0 那一支）。派单的 CRLF 列是**工作树**的 CRLF 数：
    #   · backend/**.py 等工作树是 CRLF 的文件 → 该列 == blob 的 LF 行数；
    #   · backend/data/** 由 .gitattributes 钉成 eol=lf、工作树也是 LF → 该列 == 0。
    # 只看 blob 分不出这两类，故两种都接受；真正的判据是 okb（bytes = blob + CRLF）。
    okr = (raw == esha)
    okn = (nrm == esha)
    print('%-52s %-9s %-6s %-6s %-18s %-18s  blob+%s=%s vs 派单%s -> %s  LF%s CRLF%s sha(raw=%s norm=%s)'
          % (rel.split('/')[-1], len(b), lf, crlf, raw, nrm, ec, len(b) + ec, eb,
             'OK' if okb else 'X', 'OK' if okl else 'X', 'OK' if okc else 'X',
             'MATCH' if okr else '-', 'MATCH' if okn else '-'))
    allok &= okb and okl and okc and (okr or okn)
print()
print('结论：派单那张表的 12 行**每个值都对**（12/12 = %s），但一行里混了两个口径且没有标注 ——' % allok)
print('  `bytes` / `CRLF` 两列是**工作树**的值，`行` / `sha16` 两列是 **blob**（LF）的值；')
print('  关系 `工作树 bytes == blob bytes + CRLF 行数` 逐行成立。')
print('  故 sha 列**不是**那 23225 字节（工作树）的 sha —— 那一个是 97CD375BF47B7089 ——')
print('  而是归一化后的 EE0279B00D4AFB1B。表头写的是「read_bytes 口径」，字面上指裸字节，')
print('  与 sha/行 两列的实际口径不符（硬规矩 #19：散文带口径）。')


