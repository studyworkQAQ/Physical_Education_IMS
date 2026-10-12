"""Plan 05A Task 1+2 亲验：两条 Critical 安全洞是否真的堵上了 + 承重计数。
⚠️ #109：不符项先用第二个工具复核。⚠️ #107：谓词先对已知反例验证。
"""
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = next(p for p in pathlib.Path(__file__).resolve().parents
            if (p / "backend" / "app").is_dir())
BACKEND = ROOT / "backend"
assert BACKEND.is_dir(), f"BACKEND 算错了：{ROOT}"
sys.path.insert(0, str(BACKEND))
ok = True


def chk(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"  {'OK ' if good else '!! '} {label}: 实测 {got!r}  期望 {want!r}")


tmp = pathlib.Path(tempfile.mkdtemp(prefix="pe_verify_"))
db = tmp / "v.db"
import os  # noqa: E402
os.environ["PE_DB_URL"] = f"sqlite:///{db.as_posix()}"
os.environ["PBKDF2_ITERATIONS"] = "1000"
os.environ["PE_ALLOW_HEADER_IDENTITY"] = "1"

print("### 1. 计数面")
from app.db import models as M  # noqa: E402
chk("表数", len(M.Base.metadata.tables), 26)
per = {s: len(list((BACKEND / "app" / s).rglob("*.py"))) for s in ("pipeline", "db", "domain", "api", "auth")}
print(f"  分目录 = {per}")
chk("扫描面", sum(per.values()), 66)
chk("user_session 在表里", "user_session" in M.Base.metadata.tables, True)
for tbl, cols in (("student", ("password_hash", "password_bound_at")),
                  ("teacher", ("role", "password_hash", "password_bound_at"))):
    have = {c.name for c in M.Base.metadata.tables[tbl].columns}
    for c in cols:
        chk(f"{tbl}.{c} 存在", c in have, True)
us = M.Base.metadata.tables["user_session"]
print(f"  user_session 列 = {[c.name for c in us.columns]}")
fks = [c for c in us.columns if c.foreign_keys]
chk("user_session.subject_id 无外键（多态）", len(fks), 0)

print("\n### 2. openapi 计数")
from app.main import create_app  # noqa: E402
app = create_app(db_url=f"sqlite:///{db.as_posix()}")
spec = app.openapi()
api = [p for p in spec["paths"] if p.startswith("/api/")]
ops = sum(1 for p in api for m in spec["paths"][p] if m in ("get", "post", "patch", "delete"))
chk("/api/ 路径模板数", len(api), 71)
chk("操作数", ops, 99)
n_sec = sum(1 for p in api for m, o in spec["paths"][p].items() if isinstance(o, dict) and o.get("security"))
chk("挂 security 的操作数", n_sec, 48)
schemes = spec.get("components", {}).get("securitySchemes", {})
chk("securitySchemes 格数", len(schemes), 3)
print(f"  schemes = {sorted(schemes)}")
for want in ("/api/auth/students/bind", "/api/auth/teachers/bind", "/api/auth/login",
             "/api/auth/logout", "/api/auth/me"):
    hit = want in spec["paths"]
    ok &= hit
    print(f"  {'OK ' if hit else '!! '} {want}")

print("\n### 3. ⚠️ Critical ⑦：泛型 list/read 是否泄漏 password_hash")
from fastapi.testclient import TestClient  # noqa: E402
with TestClient(app) as cl:
    # 建一个学生与一个教师，再看匿名 list/read 的响应体里有没有 password_hash
    r = cl.post("/api/students", json={"student_no": "V0001", "name": "验证甲", "gender": "male",
                                       "birth": "2005-01-01", "grade": "大一", "college": "X"})
    print(f"  POST /api/students -> {r.status_code}")
    sid = r.json().get("id") if r.status_code == 201 else None
    r = cl.post("/api/teachers", json={"staff_no": "V9001", "name": "验证师"})
    print(f"  POST /api/teachers -> {r.status_code}")
    tid = r.json().get("id") if r.status_code == 201 else None
    for path in ("/api/students?limit=5", "/api/teachers?limit=5"):
        body = cl.get(path).text
        hit = "password_hash" in body
        chk(f"{path} 响应体不含 password_hash", hit, False)
        print(f"      前 200 字符 = {body[:200]}")
    if sid:
        body = cl.get(f"/api/students/{sid}").text
        chk(f"GET /api/students/{{id}} 不含 password_hash", "password_hash" in body, False)
        print(f"      前 200 字符 = {body[:200]}")
    if tid:
        body = cl.get(f"/api/teachers/{tid}").text
        chk(f"GET /api/teachers/{{id}} 不含 password_hash", "password_hash" in body, False)

print("\n### 4. ⚠️ Critical ⑧：422 是否回显明文口令")
with TestClient(app) as cl:
    secret = "Zq7-MARKER-plaintext-42"
    r = cl.post("/api/auth/students/bind",
                json={"student_no": "V0001", "birth": "2005-01-01", "password": secret})
    print(f"  弱口令/或正常绑定 -> {r.status_code}")
    body = r.text
    chk("响应体不含明文口令", secret in body, False)
    print(f"      前 300 字符 = {body[:300]}")
    # 再试一个必定 422 的（口令太短）
    r2 = cl.post("/api/auth/students/bind",
                 json={"student_no": "V0001", "birth": "2005-01-01", "password": "abc"})
    print(f"  短口令 -> {r2.status_code}")
    chk("短口令的 422 不回显 'abc'", '"abc"' in r2.text, False)
    print(f"      前 300 字符 = {r2.text[:300]}")
    # 缺字段的 422（Pydantic 的 request_validation_failed）
    r3 = cl.post("/api/auth/login", json={"kind": "student"})
    print(f"  缺字段的 login -> {r3.status_code}")
    print(f"      前 300 字符 = {r3.text[:300]}")

print("\n### 5. 密码哈希的自描述串格式")
from app.auth import passwords as PW  # noqa: E402
h = PW.hash_password("正确口令-8位")
print(f"  hash_password 产物 = {h[:60]}…（{len(h)} 字符）")
chk("前缀是 pbkdf2_sha256$", h.startswith("pbkdf2_sha256$"), True)
chk("段数 4", len(h.split("$")), 4)
chk("迭代次数是测试值 1000", h.split("$")[1], "1000")
chk("verify 正确口令", PW.verify_password("正确口令-8位", h), True)
chk("verify 错误口令", PW.verify_password("错误口令-8位", h), False)
chk("同一个口令两次 hash 不同（盐随机）", PW.hash_password("正确口令-8位") != h, True)

print("\n### 6. 禁区")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301"),
                  ("data/alert_rules.yaml", "E48E3AC82BB45BB7")):
    b = (BACKEND / rel).read_bytes()
    chk(rel, hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper(), want)
r = subprocess.run(["git", "diff", "--stat", "1d1b6e8", "HEAD", "--", "backend/data"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff -- backend/data -> {(r.stdout or '').strip() or '（空）OK'}")
r = subprocess.run(["git", "diff", "--stat", "1d1b6e8", "HEAD", "--", "backend/pyproject.toml"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff -- pyproject.toml -> {(r.stdout or '').strip() or '（空）OK 新增依赖数 0'}")
chk("pe.db 存在?", (BACKEND / "pe.db").exists(), False)

import shutil  # noqa: E402
shutil.rmtree(tmp, ignore_errors=True)
print(f"\n===== 亲验结论：{'全部通过' if ok else '有不符项（按 #109 先复核再采信）'} =====")
sys.exit(0 if ok else 1)
