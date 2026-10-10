"""Task 9 探针 12：对**真的跑起来的 uvicorn**（127.0.0.1:8010，库 = backend/pe_demo.db）
打一遍闭环，取 ``demo.ps1`` 的真机证据。

⚠️ 这与 ``tests/api/test_end_to_end.py`` 是**两个不同的证据**：那一条走
``TestClient``（httpx 的 ASGITransport，进程内），本探针走**真的 TCP + 真的 uvicorn
工作进程 + 真的磁盘 SQLite 文件**。前者证明代码接得上，后者证明「一条命令能把系统跑起来」。

⚠️ 只读 + 两次幂等写入（处置一条预警、重跑一次批处理），且**不碰**任何禁区。
"""
import json
import pathlib
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8010"
ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
TEACHER = {"X-Teacher-Staff-No": "T0001"}


def call(method: str, path: str, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={**(headers or {}),
                 **({"Content-Type": "application/json"} if data else {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def show(label: str, status: int, text: str, limit: int = 700) -> None:
    body = text if len(text) <= limit else text[:limit] + f" …（共 {len(text)} 字符）"
    print(f"\n--- {label} -> HTTP {status}\n{body}")


print("== ① 存活探针 ==")
status, text = call("GET", "/api/health")
show("GET /api/health", status, text, 400)
health = json.loads(text)
assert status == 200 and health["status"] == "ok", text
assert health["tables"] == 25, health
assert health["students"] == 60, health

print("\n== ② OpenAPI 面 ==")
status, text = call("GET", "/openapi.json")
spec = json.loads(text)
paths = spec["paths"]
api_paths = [p for p in paths if p.startswith("/api/")]
operations = sum(
    1 for item in paths.values() for method in item
    if method in ("get", "post", "put", "patch", "delete")
)
secured = sum(
    1 for item in paths.values() for method, op in item.items()
    if method in ("get", "post", "put", "patch", "delete") and "security" in op
)
print(f"HTTP {status}: 路径模板 {len(paths)}（/api/ 下 {len(api_paths)}）、"
      f"操作 {operations}、挂 security 的 {secured}")
print("run-daily 在不在:", "/api/pipeline/run-daily" in paths)

print("\n== ③ 教师端的预警队列 ==")
status, text = call("GET", "/api/alerts?limit=50")
alerts = json.loads(text)
print(f"HTTP {status}: total={alerts['total']}")
for item in alerts["items"][:4]:
    print("   ", {k: item[k] for k in ("id", "rule_id", "level", "student_id",
                                       "course_section_id", "status", "window_key")})
red = [a for a in alerts["items"] if a["rule_id"] == "RED_RPE_SUSTAINED"]
assert red, "演示库里应当有 RED_RPE_SUSTAINED"
target = red[0]
student_id = target["student_id"]
print(f"挑中学生 {student_id} 的那一条 alert id={target['id']}")

print("\n== ④ 学生端：处置**之前**的本周训练单 ==")
status, text = call(
    "GET", f"/api/students/{student_id}/weekly-sheet?as_of=2025-10-12",
    headers={"X-Student-Id": str(student_id)},
)
before = json.loads(text)
print(f"HTTP {status}: week={before['week']} factor={before['factor']} "
      f"reasons={before['reasons']} sources={before['sources']} paused={before['paused']}")

print("\n== ⑤ 越权对照：另一个学生的头读同一个人 ==")
status, text = call(
    "GET", f"/api/students/{student_id}/weekly-sheet?as_of=2025-10-12",
    headers={"X-Student-Id": str(student_id + 1)},
)
show("越权 GET weekly-sheet", status, text, 300)
assert status == 403, status

print("\n== ⑥ 教师处置：减量 20% ==")
status, text = call(
    "POST", f"/api/alerts/{target['id']}/handle?as_of=2025-10-12",
    body={"action": "reduce_20pct"}, headers=TEACHER,
)
handled = json.loads(text)
print(f"HTTP {status}: alert.status={handled['alert']['status']} "
      f"handled_action={handled['alert']['handled_action']!r} "
      f"adjustment={'None（管道已自动减过 → 撞唯一约束，没有第二次减量）' if handled['adjustment'] is None else handled['adjustment']}")
if handled["notification"]:
    print(f"      notification: id={handled['notification']['id']} "
          f"title={handled['notification']['title']!r} "
          f"-> {handled['notification']['recipient_kind']}:"
          f"{handled['notification']['recipient_id']}")

print("\n== ⑦ 学生端：处置**之后**的本周训练单 ==")
status, text = call(
    "GET", f"/api/students/{student_id}/weekly-sheet?as_of=2025-10-12",
    headers={"X-Student-Id": str(student_id)},
)
after = json.loads(text)
print(f"HTTP {status}: week={after['week']} factor={after['factor']} "
      f"reasons={after['reasons']} sources={after['sources']}")
assert after["factor"] == 0.8, after["factor"]
assert after["reasons"] == ["RED_RPE_SUSTAINED"], after["reasons"]
assert after["sources"] == ["auto"], after["sources"]

print("\n== ⑧ 学生端的消息中心 ==")
status, text = call("GET", "/api/notifications?limit=50")
notes = json.loads(text)
mine = [n for n in notes["items"]
        if n["recipient_kind"] == "student" and n["recipient_id"] == student_id]
print(f"HTTP {status}: total={notes['total']}，学生 {student_id} 的有 {len(mine)} 条")
for note in mine:
    print(f"    id={note['id']} title={note['title']!r} is_read={note['is_read']} "
          f"alert_id={note['alert_id']} prescription_id={note['prescription_id']}")
assert len(mine) == 1 and mine[0]["is_read"] is False
note_id = mine[0]["id"]
status, text = call("POST", f"/api/notifications/{note_id}/read",
                    headers={"X-Student-Id": str(student_id)})
show("POST /api/notifications/{id}/read", status, text, 300)
assert status == 200 and json.loads(text)["is_read"] is True

print("\n== ⑨ 教师大屏（班级周报那一块）==")
status, text = call("GET", "/api/dashboard/weekly-class-report/1?week=6&as_of=2025-10-12",
                    headers=TEACHER)
report = json.loads(text)
print(f"HTTP {status}: keys={sorted(report)}")
print("   progress_board =", json.dumps(report.get("progress_board"), ensure_ascii=False)[:400])
print("   suggestion     =", report.get("suggestion"))
print("   alert_summary  =", json.dumps(report.get("alert_summary"), ensure_ascii=False))

print("\n== ⑩ 手动重跑一次批处理（POST /api/pipeline/run-daily）==")
status, text = call("POST", "/api/pipeline/run-daily",
                    body={"business_date": "2025-10-12"}, headers=TEACHER)
run = json.loads(text)
print(f"HTTP {status}: status={run['status']} run_id={run['daily_sync_run_id']} "
      f"prescription_count={run['prescription_count']} alert_count={run['alert_count']} "
      f"csv_dir={run['csv_dir']}")
assert status == 200 and run["status"] == "success", text

print("\n== ⑪ 禁区复核 ==")
forbidden = BACKEND / "pe.db"
seed_dir = BACKEND / "data" / "seed"
seed_files = sorted(p.name for p in seed_dir.iterdir()) if seed_dir.is_dir() else []
print(f"backend/pe.db 存在 = {forbidden.exists()}（必须是 False）")
print(f"backend/data/seed/ 的文件 = {seed_files}（必须是 []）")
assert not forbidden.exists()
assert seed_files == []
print("\n全部通过")
sys.exit(0)
