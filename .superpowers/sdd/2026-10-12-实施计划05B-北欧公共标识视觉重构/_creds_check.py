"""实测当前演示库的三种角色能否登录，给用户一组能用的账号。"""
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), dict(e.headers)


def get(path, cookie=None):
    req = urllib.request.Request(BASE + path, headers={"Cookie": cookie} if cookie else {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), dict(e.headers)


print("### 0. 后端是否在跑")
st, body, _ = get("/api/health")
print(f"  GET /api/health -> {st} {body[:120]}")
if st != 200:
    print("  !! 后端没在 8000 上跑。请先跑 backend\\scripts\\demo.ps1")
    sys.exit(1)

PW = "pe-demo-2025"
CANDIDATES = [
    ("student", "2023120001", "赵锦程（student.id=4，Plan 04 取证主身份）"),
    ("student", "2024090001", "赵婉清（student.id=5）"),
    ("student", "2025060001", "demo.ps1 打印的示例学号"),
    ("teacher", "T0001", "陈国华（普通教师，带班）"),
    ("teacher", "T0002", "林慧敏（普通教师）"),
    ("teacher", "T0003", "赵志刚（管理员 role=admin）"),
]

print("\n### 1. 逐个试登录")
ok_list = []
for kind, ident, note in CANDIDATES:
    st, body, hdrs = post("/api/auth/login", {"kind": kind, "login": ident, "password": PW})
    cookie = None
    for k, v in hdrs.items():
        if k.lower() == "set-cookie":
            cookie = v.split(";")[0]
    me = ""
    if st == 200 and cookie:
        s2, b2, _ = get("/api/auth/me", cookie)
        me = b2[:160]
    print(f"  {kind:8s} {ident:12s} -> {st}  {note}")
    if st == 200:
        print(f"           me = {me}")
        ok_list.append((kind, ident, note, cookie))
    else:
        print(f"           body = {body[:160]}")

print("\n### 2. 能用的账号")
for kind, ident, note, _ in ok_list:
    print(f"  {kind:8s} {ident:12s} 口令 {PW}   # {note}")
if not ok_list:
    print("  !! 一个都登不进去 —— 演示库可能是 05A 之前灌的旧库（没有 password_hash 列）。")
    print("     请重跑：backend\\scripts\\demo.ps1")

print("\n### 3. 各角色登录后能去哪（实测一个代表端点）")
for kind, ident, note, cookie in ok_list:
    if kind == "student":
        s, b, _ = get("/api/students/me-placeholder", cookie)  # 必然 404，只为看鉴权是否通过
        s2, b2, _ = get(f"/api/auth/me", cookie)
        sid = json.loads(b2).get("id")
        s3, b3, _ = get(f"/api/students/{sid}/home?as_of=2025-10-12", cookie)
        print(f"  学生 {ident}: GET /api/students/{sid}/home -> {s3}（200 即学生端有数据）")
    else:
        s2, b2, _ = get("/api/auth/me", cookie)
        role = json.loads(b2).get("role")
        s3, b3, _ = get("/api/dashboard/class/1?as_of=2025-10-12", cookie)
        s4, b4, _ = post("/api/semesters", {}) if False else (0, "", {})
        print(f"  {kind} {ident} role={role}: GET /api/dashboard/class/1 -> {s3}")
        if role == "admin":
            # 试一次管理台写操作的鉴权（不真写：用一个必然 422 的空 body）
            st5, b5, _ = post_with = None, None, None
            req = urllib.request.Request(BASE + "/api/semesters", data=b"{}",
                                         headers={"Content-Type": "application/json", "Cookie": cookie},
                                         method="POST")
            try:
                with urllib.request.urlopen(req) as r:
                    st5, b5 = r.status, r.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                st5, b5 = e.code, e.read().decode("utf-8")
            print(f"      管理台写 POST /api/semesters（空 body）-> {st5}（422=鉴权通过只是参数缺；401/403=鉴权没过）")
