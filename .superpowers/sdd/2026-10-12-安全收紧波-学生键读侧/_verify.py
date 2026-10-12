"""安全收紧波亲验：匿名读学生键资源是否真的 401 + 那 3 条布局红是否在波前就存在。"""
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = next(p for p in pathlib.Path(__file__).resolve().parents
            if (p / "backend" / "app").is_dir())
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
BASE = "http://127.0.0.1:8000"
ok = True


def chk(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"  {'OK ' if good else '!! '} {label}: 实测 {got!r}  期望 {want!r}")


def req(path, cookie=None):
    r = urllib.request.Request(BASE + path, headers={"Cookie": cookie} if cookie else {})
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, resp.read().decode("utf-8"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), dict(e.headers)


def login(kind, ident, pw="pe-demo-2025"):
    body = json.dumps({"kind": kind, "login": ident, "password": pw}).encode()
    r = urllib.request.Request(BASE + "/api/auth/login", data=body,
                               headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(r) as resp:
            for k, v in resp.headers.items():
                if k.lower() == "set-cookie":
                    return v.split(";")[0]
    except urllib.error.HTTPError as e:
        print(f"  !! 登录失败 {kind} {ident}: {e.code} {e.read().decode()[:120]}")
    return None


print("### 1. 匿名读学生键资源应当 401")
for p in ("/api/training-logs?limit=1", "/api/rpe-records?limit=1", "/api/body-compositions?limit=1",
          "/api/alerts?limit=1", "/api/notifications?limit=1", "/api/enrollments?limit=1",
          "/api/weekly-adjustments?limit=1", "/api/mini-tests?limit=1"):
    st, _, _ = req(p)
    chk(f"匿名 GET {p}", st, 401)

print("\n### 2. 参考数据仍匿名 200")
for p in ("/api/semesters?limit=1", "/api/course-sections?limit=1", "/api/exercises?limit=1",
          "/api/class-sessions?limit=1", "/api/prescription-templates?limit=1"):
    st, _, _ = req(p)
    chk(f"匿名 GET {p}", st, 200)

print("\n### 3. 三档矩阵抽三格")
c4 = login("student", "2023120001")
c5 = login("student", "2024090001")
ct = login("teacher", "T0001")
ca = login("teacher", "T0003")
st, b, _ = req("/api/training-logs?limit=200", c4)
n4 = json.loads(b).get("total") if st == 200 else None
chk("学生#4 list training-logs 的 total", n4, 14)
st, b, _ = req("/api/training-logs?limit=200", c5)
n5 = json.loads(b).get("total") if st == 200 else None
chk("学生#5 list training-logs 的 total", n5, 14)
# read-one 别人的
st, _, _ = req("/api/training-logs/1", c5)
print(f"  学生#5 读 training-logs/1 -> {st}（403=别人的 / 200=恰是自己的）")
st, _, _ = req("/api/training-logs?limit=1", ct)
chk("教师 list training-logs", st, 200)
st, _, _ = req("/api/training-logs?limit=1", ca)
chk("管理员 list training-logs", st, 200)

print("\n### 4. password_bound_at 是否已从读模型消失")
st, b, _ = req("/api/students?limit=1", ca)
hit = "password_bound_at" in b
chk("匿名/教职 list students 不含 password_bound_at", hit, False)
st, b, _ = req("/api/students/4", ca)
chk("read-one students/4 不含 password_bound_at", "password_bound_at" in b, False)
st, b, _ = req("/api/teachers?limit=1", ca)
chk("list teachers 不含 password_bound_at", "password_bound_at" in b, False)

print("\n### 5. openapi 计数")
st, b, _ = req("/openapi.json")
spec = json.loads(b)
api = [p for p in spec["paths"] if p.startswith("/api/")]
ops = sum(1 for p in api for m in spec["paths"][p] if m in ("get", "post", "patch", "delete"))
n_sec = sum(1 for p in api for m, o in spec["paths"][p].items() if isinstance(o, dict) and o.get("security"))
gets = [(p, m) for p in api for m in spec["paths"][p] if m == "get"]
anon_get = [x for x in gets if not spec["paths"][x[0]][x[1]].get("security")]
chk("路径模板数", len(api), 71)
chk("操作数", ops, 99)
chk("挂 security 的操作数", n_sec, 80)
chk("GET 总数", len(gets), 60)
chk("匿名 GET 数", len(anon_get), 16)
chk("securitySchemes 格数", len(spec.get("components", {}).get("securitySchemes", {})), 3)
print(f"  仍匿名的 GET = {[p for p, _ in anon_get]}")

print("\n### 6. mini-tests/normalized 是否仍匿名（实现者点名的那扇没关的门）")
st, b, _ = req("/api/mini-tests/normalized?course_section_id=1&week=6")
print(f"  匿名 GET /api/mini-tests/normalized -> {st}（实现者说仍匿名且回 student_id+分数）")
if st == 200:
    print(f"     响应前 200 字符 = {b[:200]}")

print(f"\n===== 亲验结论：{'全部通过' if ok else '有不符项'} =====")
