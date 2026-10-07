import pathlib, hashlib, ast

p = pathlib.Path("backend/tests/architecture/test_domain_purity.py")
b = p.read_bytes()
before = hashlib.sha256(b).hexdigest()[:16].upper()
NL = "\r\n"
t = b.decode("utf-8")
lines = t.split(NL)

i_start = [k for k, ln in enumerate(lines) if "CE-6）。" in ln]
i_end = [k for k, ln in enumerate(lines) if ln.strip().startswith("折算之后（⚠️")]
print("anchors:", i_start, i_end)
assert len(i_start) == 1 and len(i_end) == 1
a, z = i_start[0] + 1, i_end[0]
block = lines[a:z]
print("block lines:", len(block))
indent = min(len(ln) - len(ln.lstrip(" ")) for ln in block if ln.strip())
print("min indent in block =", indent)
fixed = [ln[1:] if ln.startswith(" " * (indent + 1)) else ln for ln in block]
print("changed:", sum(1 for x, y in zip(block, fixed) if x != y))
lines2 = lines[:a] + fixed + lines[z:]
t2 = NL.join(lines2)
b2 = t2.encode("utf-8")
p.write_bytes(b2)

b3 = p.read_bytes(); t3 = b3.decode("utf-8")
ast.parse(t3)
print("before sha16", before, "bytes", len(b))
print("after  sha16", hashlib.sha256(b3).hexdigest()[:16].upper(), "bytes", len(b3),
      "CRLF", b3.count(b"\r\n"), "bare LF", b3.count(b"\n") - b3.count(b"\r\n"))
# 双向串查
new7 = "       ⚠️ **Task 4 落地后的当前值是 17 条**"
old8 = "        ⚠️ **Task 4 落地后的当前值是 17 条**"
print("NEW(7sp) hits:", t3.count(new7), "| OLD(8sp) residual:", t3.count(old8))
print("control probe (must be >=1):", t3.count("def test_absolute_folding_matches_resolve_name():"))
print("ast.parse OK")
