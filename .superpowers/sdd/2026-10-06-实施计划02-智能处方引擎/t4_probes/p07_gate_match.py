import pathlib, hashlib, ast, sys

p = pathlib.Path("backend/app/domain/prescription/match.py")
b = p.read_bytes()
text = b.decode("utf-8")
print("bytes", len(b), "lines(splitlines)", len(b.splitlines()), "CRLF", b.count(b"\r\n"),
      "sha16(raw)", hashlib.sha256(b).hexdigest()[:16].upper(),
      "sha16(nl-normalised)", hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper())

must_have = [
    "from .templates import BodyCompState, ReviewStatus, Template\n",
    "class MatchStatus(str, Enum):",
    "class MatchInput:",
    "class MatchOutcome:",
    "def match_template(inp: MatchInput, templates: Mapping[str, Template]) -> MatchOutcome:",
    "_NO_LAYER_REASON = f\"有效项不足 {MIN_VALID_COUNT} 项，本日不分层\"",
    "for template_id in sorted(templates):",
]
must_not = [
    "__all__",
    "WeaknessBucket",
    "is_reachable(",
    "read_text", "read_bytes", "Path(", "import os", "__file__", "json.load",
    "pickle.load", "csv.reader", "read_csv",
]
ok = True
for s in must_have:
    n = text.count(s)
    print(("HAVE  " if n >= 1 else "MISS!!"), n, repr(s[:70]))
    ok &= n >= 1
for s in must_not:
    n = text.count(s)
    print(("CLEAN " if n == 0 else "RESID!!"), n, repr(s))
    ok &= n == 0

# 查询本身有效性对照（硬规矩 #48：任何「0 命中」的结论先用一个已知存在的串验证）
ctrl = "MatchStatus.NO_LAYER"
print("control probe (must be >=1):", text.count(ctrl))
ok &= text.count(ctrl) >= 1

tree = ast.parse(text)
print("top-level public defs:", sorted(
    {n.name for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and not n.name.startswith("_")}
    | {t.id for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
       for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
       if isinstance(t, ast.Name) and not t.id.startswith("_")}))
imports = [(n.level, n.module) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
print("ImportFrom:", imports)
plain = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
print("Import:", plain)
print("OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
