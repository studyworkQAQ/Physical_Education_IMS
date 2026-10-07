import pathlib
p = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\tests\architecture\test_domain_purity.py")
t = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
L = t.splitlines()
for i in range(139, 150):
    print("%4d| %r" % (i + 1, L[i]))
