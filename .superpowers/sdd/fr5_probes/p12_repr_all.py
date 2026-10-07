import pathlib
ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
SPEC = [
    ("backend/tests/architecture/test_domain_purity.py",
     [(208, 211), (220, 225), (229, 234), (243, 251), (271, 276), (312, 316),
      (391, 394), (521, 527), (542, 546)]),
    ("backend/tests/architecture/test_layering.py",
     [(143, 148), (148, 153), (195, 200), (207, 213), (216, 225), (230, 238),
      (257, 262), (298, 302), (369, 373), (383, 387)]),
    ("backend/tests/db/test_models.py", [(607, 620)]),
    ("backend/app/pipeline/daily.py", [(224, 231)]),
]
for rel, ranges in SPEC:
    t = (ROOT / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")
    L = t.splitlines()
    print("########", rel)
    for a, b in ranges:
        print("  ---- %d..%d" % (a + 1, b))
        for i in range(a, min(b, len(L))):
            print("  %4d| %r" % (i + 1, L[i]))
