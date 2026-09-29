"""domain 层纯净性架构约束的可执行检查。

spec Global Constraints 规定 app/domain/ 禁止任何 I/O：不得 import 数据库/HTTP 框架，
不得调用时钟、文件与无种子随机数接口。时间与随机数一律由调用方注入，
这是分层引擎与处方引擎可单测、可复现的前提。
"""
import ast
import pathlib
import re

DOMAIN = pathlib.Path(__file__).parents[2] / "app" / "domain"
# 与 spec Global Constraints 逐条对应：禁 I/O 库、禁无种子随机数
FORBIDDEN = {"sqlalchemy", "fastapi", "requests", "httpx", "pydantic_settings", "random"}
# 时间必须由调用方注入；子串检查足以覆盖这四种写法
FORBIDDEN_CALLS = {"datetime.now", "datetime.today", "datetime.utcnow", "time.time"}
# open 用词边界正则而非裸子串，避免 open_ended / reopen / 注释里的 "open" 误报
FORBIDDEN_PATTERNS = (re.compile(r"\bopen\s*\("),)


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
        offenders += [f"{py.name}:{p.pattern}" for p in FORBIDDEN_PATTERNS if p.search(src)]
    assert offenders == []
