import ast, pathlib

DOMAIN = pathlib.Path(__file__).parents[2] / "app" / "domain"
FORBIDDEN = {"sqlalchemy", "fastapi", "requests", "httpx", "pydantic_settings"}
FORBIDDEN_CALLS = {"datetime.now", "datetime.today", "open"}

def test_domain_has_no_forbidden_imports():
    # 守卫：Path.rglob() 对不存在的目录静默返回空，缺了这行测试会空转全绿
    assert DOMAIN.is_dir(), f"领域层目录缺失，架构测试将空转: {DOMAIN}"
    offenders = []
    for py in DOMAIN.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module.split(".")[0]]
            offenders += [f"{py.name}:{m}" for m in mods if m in FORBIDDEN]
    assert offenders == []

def test_domain_has_no_clock_or_file_access():
    assert DOMAIN.is_dir(), f"领域层目录缺失，架构测试将空转: {DOMAIN}"
    offenders = []
    for py in DOMAIN.rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        offenders += [f"{py.name}:{c}" for c in FORBIDDEN_CALLS if c in src]
    assert offenders == []
