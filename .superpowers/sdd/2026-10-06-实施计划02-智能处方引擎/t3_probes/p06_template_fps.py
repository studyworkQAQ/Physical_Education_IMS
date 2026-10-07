import hashlib, pathlib
D = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\data\prescription')
order = [
    "RED-END-ABN-01", "RED-END-NOR-02", "RED-STR-ABN-03", "RED-STR-NOR-04",
    "RED-SPD-ABN-05", "RED-SPD-NOR-06",
    "YEL-END-ABN-07", "YEL-END-NOR-08", "YEL-STR-ABN-09", "YEL-STR-NOR-10",
    "YEL-SPD-ABN-11", "YEL-SPD-NOR-12",
    "GRN-END-ABN-13", "GRN-END-NOR-14", "GRN-STR-ABN-15", "GRN-STR-NOR-16",
    "GRN-SPD-ABN-17", "GRN-SPD-NOR-18",
]
files = sorted(p.stem for p in D.glob("*.yaml"))
assert files == sorted(order), (files, order)
total = 0
for tid in order:
    p = D / f"{tid}.yaml"
    b = p.read_bytes()
    total += len(b)
    assert b.count(b"\r\n") == 0, tid
    print('    "%s": "%s",   # %d B' % (
        tid, hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper(), len(b)))
print("18 个文件合计 %d B" % total)
