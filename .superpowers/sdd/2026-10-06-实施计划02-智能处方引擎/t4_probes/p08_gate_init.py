import pathlib, hashlib, sys
sys.path.insert(0, "backend")

p = pathlib.Path("backend/app/domain/prescription/__init__.py")
b = p.read_bytes()
t = b.decode("utf-8").replace("\r\n", "\n")   # 工作树是 CRLF（w/crlf），归一化后再串查
print("bytes", len(b), "lines", len(b.splitlines()), "CRLF", b.count(b"\r\n"),
      "sha16(raw)", hashlib.sha256(b).hexdigest()[:16].upper())

must_have = [
    "from .match import (\n    MatchInput,\n    MatchOutcome,\n    MatchStatus,\n    match_template,\n)",
    '"MatchStatus",\n    "MatchInput",\n    "MatchOutcome",\n    "match_template",\n]',
    "共 **24** 个",
    "``assert len(...) == 24``",
]
must_not = [
    "共 **20** 个。Task 4 建",
    "``assert len(...) == 20``",
    "Task 4 建 ``match.py``",
    "``BodyCompState`` / ``WeaknessBucket`` 取自",
]
ok = True
for s in must_have:
    n = t.count(s); print(("HAVE  " if n >= 1 else "MISS!!"), n, repr(s[:60])); ok &= n >= 1
for s in must_not:
    n = t.count(s); print(("CLEAN " if n == 0 else "RESID!!"), n, repr(s[:60])); ok &= n == 0
print("control probe (must be >=1):", t.count('from app.domain.stratify import Layer'))
ok &= t.count('from app.domain.stratify import Layer') >= 1

from app.domain import prescription as pkg
print("len(__all__) =", len(pkg.__all__))
print(pkg.__all__)
import app.domain.prescription.match as m
print("match public:", [n for n in dir(m) if not n.startswith("_")])
print("MatchStatus:", [(x.name, x.value) for x in pkg.MatchStatus])
print("templates.__all__ len:", len(pkg.__all__) and len(__import__("app.domain.prescription.templates", fromlist=["x"]).__all__))
print("OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
