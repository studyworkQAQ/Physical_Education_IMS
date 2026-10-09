"""对着跑起来的 uvicorn 打真实 HTTP（修正版）：完整 CRUD 一圈 + 前后端对接核查。"""
import json

import httpx

BASE = "http://127.0.0.1:8000"
c = httpx.Client(base_url=BASE, timeout=30.0)


def url_of(r):
    q = r.request.url.query
    if isinstance(q, bytes):
        q = q.decode()
    return f"{r.request.url.path}{('?'+q) if q else ''}"


def show(title, r, body_limit=430):
    print(f"\n--- {title}")
    print(f"  {r.request.method} {url_of(r)}  -> {r.status_code}")
    txt = r.text
    print(f"  {txt[:body_limit]}{' …' if len(txt) > body_limit else ''}")
    return r


spec = c.get("/openapi.json").json()
print(f"OpenAPI {spec['openapi']}  paths={len(spec['paths'])}  schemas={len(spec['components']['schemas'])}")

print("\n========== A. SemesterCreate 的必填字段（从 OpenAPI 读，不猜）==========")
sc = spec["components"]["schemas"].get("SemesterCreate")
print(f"  {json.dumps(sc, ensure_ascii=False)[:700]}")

print("\n========== B. 完整 CRUD 一圈 ==========")
payload = {"name": "2025-2026 学年 第一学期", "start_date": "2025-09-01",
           "end_date": "2026-01-18", "weeks": 20}
r = show("① POST 建一个学期 -> 应 201 + Location", c.post("/api/semesters", json=payload))
sem = r.json() if r.status_code in (200, 201) else {}
sid = sem.get("id")
print(f"  Location = {r.headers.get('location')!r}   id = {sid}")

show("② POST 撞同名 -> 应 409（自然键 name）", c.post("/api/semesters", json=payload))
show("③ GET list", c.get("/api/semesters"))
show(f"④ GET read-one /api/semesters/{sid}", c.get(f"/api/semesters/{sid}"))
show("⑤ PATCH 只传一个键（部分更新）", c.patch(f"/api/semesters/{sid}", json={"weeks": 18}))
r = show("⑥ GET 复核：weeks 变了、name 没被清掉", c.get(f"/api/semesters/{sid}"))
if r.status_code == 200:
    d = r.json()
    print(f"  >>> weeks={d.get('weeks')}（应 18）  name={d.get('name')!r}（应原样保留）")
show("⑦ PATCH 传 null 与「没传」可区分（start_date 显式 null）",
     c.patch(f"/api/semesters/{sid}", json={"start_date": None}))
show("⑧ DELETE -> 应 405（semester 是 on_delete=forbid）", c.delete(f"/api/semesters/{sid}"))

print("\n========== C. 教师（可写 + on_delete=restrict）走一遍删除 ==========")
r = show("① POST 建一个教师", c.post("/api/teachers", json={"staff_no": "T2025001", "name": "张老师"}))
tid = (r.json() or {}).get("id")
show("② DELETE -> 应 204（没有子行）", c.delete(f"/api/teachers/{tid}"))
show("③ GET 复核已删 -> 应 404", c.get(f"/api/teachers/{tid}"))

print("\n========== D. 只读资源应拒写 ==========")
show("POST /api/stratification-results -> 应 405", c.post("/api/stratification-results", json={}))
show("DELETE /api/prescriptions/1 -> 应 405（restrict 但 writable=False）", c.delete("/api/prescriptions/1"))
show("GET /api/prescriptions（5 个大 JSON 列应不在 list 里）", c.get("/api/prescriptions"))

print("\n========== E. 前后端对接的核查 ==========")
r = c.options("/api/semesters", headers={"Origin": "http://localhost:5173",
                                         "Access-Control-Request-Method": "PATCH",
                                         "Access-Control-Request-Headers": "X-Student-Id,Content-Type"})
print(f"  CORS 预检 -> {r.status_code}")
for h in ("access-control-allow-origin", "access-control-allow-methods",
          "access-control-allow-headers", "access-control-allow-credentials"):
    print(f"     {h}: {r.headers.get(h)!r}")
hdr = sorted({p["name"] for ops in spec["paths"].values() for op in ops.values()
              if isinstance(op, dict) for p in op.get("parameters", []) if p.get("in") == "header"})
print(f"  OpenAPI 里声明过的身份请求头 = {hdr or '（空 —— Task 4/5 的 scope 端点建好后才会有）'}")
n_schema = sum(1 for ops in spec["paths"].values() for op in ops.values() if isinstance(op, dict)
               for code, resp in op.get("responses", {}).items()
               if code.startswith("2") and resp.get("content", {}).get("application/json", {}).get("schema"))
n_ok = sum(1 for ops in spec["paths"].values() for op in ops.values() if isinstance(op, dict)
           for code in op.get("responses", {}) if code.startswith("2"))
print(f"  2xx 响应里带 schema 的 = {n_schema} / {n_ok}")
paths_with_pk = sorted({p for p in spec["paths"] if "{" in p})[:3]
for p in paths_with_pk:
    prm = [x["name"] for x in spec["paths"][p]["get"].get("parameters", []) if x.get("in") == "path"]
    print(f"  detail 路径 {p} 的 path 参数名 = {prm}")

print("\n========== F. 收尾 ==========")
print(f"  /api/health = {c.get('/api/health').json()}")
print(f"  /api/semesters total = {c.get('/api/semesters').json().get('total')}")
c.close()
