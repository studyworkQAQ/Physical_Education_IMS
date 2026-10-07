import pathlib
ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
SPEC = [
    ("backend/tests/architecture/test_domain_purity.py", [(143, 156), (211, 226), (241, 272),
                                                          (303, 318), (559, 578), (589, 606)]),
    ("backend/tests/architecture/test_layering.py", [(143, 162), (195, 212), (225, 262),
                                                     (285, 300)]),
    ("backend/tests/db/test_models.py", [(606, 632)]),
    ("backend/app/pipeline/daily.py", [(223, 236)]),
]
for rel, ranges in SPEC:
    L = (ROOT / rel).read_bytes().decode("utf-8").replace("\r\n", "\n").splitlines()
    print("########", rel, "总行数", len(L))
    for a, b in ranges:
        print("  ---- %d..%d" % (a, b))
        for i in range(a - 1, min(b, len(L))):
            print("  %4d| %s" % (i + 1, L[i]))
