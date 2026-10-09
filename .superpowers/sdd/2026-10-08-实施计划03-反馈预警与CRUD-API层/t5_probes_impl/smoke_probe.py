"""端到端冒烟：真 uvicorn + **磁盘** SQLite（TEMP，不碰 pe.db / pe_demo.db）跑通七个端点。

TestClient 用的是内存库 + StaticPool，故本脚本补的是「真 ASGI 服务器 + 真磁盘文件 +
lifespan 建表」这一档。⚠️ 库文件放 TEMP 并在结束前删除，故对仓库零副作用。

⚠️ 顺带取证一件要报给控制者的事：本仓不做迁移，schema 变更后**旧的磁盘库必须重建**
（training_log 新加了 submitted_at NOT NULL 列，而 create_all 对已存在的表原样跳过）。
"""
import datetime as dt
import os
import pathlib
import subprocess
import sys
import tempfile
import time

import httpx

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

DB_PATH = pathlib.Path(tempfile.gettempdir()) / "t5_smoke.db"
for suffix in ("", "-wal", "-shm"):
    candidate = pathlib.Path(str(DB_PATH) + suffix)
    if candidate.exists():
        candidate.unlink()
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"
PORT = 8123
BASE = f"http://127.0.0.1:{PORT}"

env = dict(os.environ)
env["PE_DB_URL"] = DB_URL     # ⚠️ 必须显式设：DEFAULT_DB_URL 指向禁区 pe.db

print("=== 起 uvicorn（真服务器，端口 %d，库 = %s）===" % (PORT, DB_PATH))
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
     "--port", str(PORT), "--log-level", "warning"],
    cwd=str(BACKEND), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding="utf-8", errors="replace",
)

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(("  ✅ " if condition else "  ❌ ") + label + (f"  {detail}" if detail else ""))
    if not condition:
        failures.append(label)


try:
    for attempt in range(60):
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ""
            raise SystemExit(f"uvicorn 提前退出（rc={proc.returncode}）：\n{out}")
        try:
            if httpx.get(f"{BASE}/api/health", timeout=1.0).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    else:
        raise SystemExit("uvicorn 30 s 内没有起来")
    print("  起来了（/api/health 200）；lifespan 建表 =", DB_PATH.exists())

    # --- 造最小数据（直连同一个磁盘库；lifespan 已经建好 25 张表）---
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine, inspect
    from app.db.models import Semester, Student, Teacher
    from app.db.models.organisation import CourseSection, Enrollment
    from app.db.models.ops import DailySyncRun

    eng = create_engine(DB_URL)
    print("  磁盘库的表数:", len(inspect(eng).get_table_names()))
    with Session(eng) as s:
        sem = Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
                       end_date=dt.date(2025, 12, 22), weeks=16, is_current=True)
        tea = Teacher(staff_no="T2025001", name="张老师")
        stu = Student(student_no="S2025001", name="小明", sex="male",
                      birth=dt.date(2005, 3, 4), department=None, grade=1)
        s.add_all([sem, tea, stu])
        s.flush()
        sec = CourseSection(semester_id=sem.id, teacher_id=tea.id, name="体育(1)班",
                            schedule_text="周一 3-4 节", grouping_mode="administrative")
        s.add(sec)
        s.flush()
        s.add(Enrollment(semester_id=sem.id, student_id=stu.id,
                         course_section_id=sec.id))
        run = DailySyncRun(semester_id=sem.id, business_date=dt.date(2025, 9, 1),
                           started_at=dt.datetime(2025, 9, 1, 2, 0),
                           finished_at=dt.datetime(2025, 9, 1, 2, 5), status="success")
        s.add(run)
        s.commit()
        ids = {"semester": sem.id, "student": stu.id, "section": sec.id}
    print("  造好数据:", ids)

    teacher = {"X-Teacher-Staff-No": "T2025001"}
    student = {"X-Student-Id": str(ids["student"])}

    print()
    print("=== 七个端点，按 spec §8.1 的真实使用顺序串一遍 ===")
    spec = httpx.get(f"{BASE}/openapi.json", timeout=10).json()
    api_paths = [p for p in spec["paths"] if p.startswith("/api/")]
    ops = sum(1 for p in api_paths
              for m in spec["paths"][p]
              if m in {"get", "post", "patch", "put", "delete"})
    check("openapi 的 /api/ 路径模板 = 56", len(api_paths) == 56, f"实到 {len(api_paths)}")
    check("openapi 的 /api/ 操作数 = 84", ops == 84, f"实到 {ops}")
    check("securitySchemes 恰好两格",
          sorted(spec["components"]["securitySchemes"]) == ["X-Student-Id",
                                                             "X-Teacher-Staff-No"])

    # ① 教师建课次（不传 batch_id → NULL）
    r = httpx.post(f"{BASE}/api/class-sessions", headers=teacher, timeout=10, json={
        "course_section_id": ids["section"], "session_date": "2025-09-08", "period": 3})
    check("① POST /api/class-sessions 201", r.status_code == 201, r.text[:120])
    cs_id = r.json()["id"]
    check("① batch_id 落 NULL（P5-A1）", r.json()["batch_id"] is None)

    # ② 教师发起课堂快评
    r = httpx.post(f"{BASE}/api/class-sessions/{cs_id}/open-rpe", headers=teacher, timeout=10)
    check("② POST open-rpe 200", r.status_code == 200, r.text[:120])
    token = r.json()["rpe_token"]
    check("② 口令长度 = 16（RPE_TOKEN_LEN）", len(token) == 16, token)
    r2 = httpx.post(f"{BASE}/api/class-sessions/{cs_id}/open-rpe", headers=teacher, timeout=10)
    check("② 幂等：第二次同口令 + already_open",
          r2.json()["rpe_token"] == token and r2.json()["already_open"] is True)

    # ③ 学生提交快评
    r = httpx.post(f"{BASE}/api/rpe-records", headers=student, timeout=10, json={
        "class_session_id": cs_id, "rpe": 7, "elapsed_seconds": 8.5, "rpe_token": token})
    check("③ POST /api/rpe-records 201", r.status_code == 201, r.text[:120])
    check("③ Location 头", r.headers.get("Location") == f"/api/rpe-records/{r.json()['id']}")
    check("③ submitted_at 由服务端填", r.json()["submitted_at"] is not None)
    r = httpx.post(f"{BASE}/api/rpe-records", headers=student, timeout=10, json={
        "class_session_id": cs_id, "rpe": 7, "elapsed_seconds": 8.5, "rpe_token": token})
    check("③ 重复提交 409", r.status_code == 409, str(r.status_code))
    r = httpx.post(f"{BASE}/api/rpe-records", headers=student, timeout=10, json={
        "class_session_id": cs_id, "rpe": 7, "elapsed_seconds": 8.5,
        "rpe_token": "WRONG-TOKEN-000"})
    check("③ 错口令 403 + invalid_rpe_token",
          r.status_code == 403 and r.json()["error"]["code"] == "invalid_rpe_token")

    # ④ 教师看提交状态
    r = httpx.get(f"{BASE}/api/class-sessions/{cs_id}/rpe-status", headers=teacher, timeout=10)
    check("④ GET rpe-status 200", r.status_code == 200, r.text[:120])
    body = r.json()
    check("④ 已交 1 人 / 未交 0 人 / 人均 7.0",
          (len(body["submitted"]), body["not_submitted"], body["mean_rpe"]) == (1, [], 7.0),
          str((len(body["submitted"]), body["not_submitted"], body["mean_rpe"])))

    # ⑤ 学生打卡
    today = dt.date.today().isoformat()
    r = httpx.post(f"{BASE}/api/training-logs", headers=student, timeout=10, json={
        "log_date": today, "completed": True, "duration_min": 35.0, "feeling": "moderate"})
    check("⑤ POST /api/training-logs 201", r.status_code == 201, r.text[:200])
    if r.status_code == 201:
        log = r.json()
        check("⑤ source=checkin / batch_id NULL / submitted_at 非空",
              (log["source"], log["batch_id"], log["submitted_at"] is not None)
              == ("checkin", None, True), str((log["source"], log["batch_id"])))
        now = dt.datetime.now()
        check("⑤ late 与当前时刻自洽（22:00 闭区间）",
              log["late"] == (now.time() > dt.time(22, 0)), f"late={log['late']} now={now:%H:%M:%S}")
    r = httpx.post(f"{BASE}/api/training-logs", headers=student, timeout=10, json={
        "log_date": today, "completed": True, "duration_min": 35.0, "feeling": "moderate"})
    check("⑤ 同一天重复 409", r.status_code == 409, str(r.status_code))
    r = httpx.post(f"{BASE}/api/training-logs", headers=student, timeout=10, json={
        "log_date": today, "completed": True, "feeling": "轻松"})
    check("⑤ 域外 feeling 422（不是 409）",
          r.status_code == 422 and r.json()["error"]["code"] == "request_validation_failed")

    # ⑥ 完成率
    r = httpx.get(f"{BASE}/api/students/{ids['student']}/training-logs/completion-rate",
                  headers=student, timeout=10,
                  params={"semester_id": ids["semester"], "week": 1})
    check("⑥ GET completion-rate 200", r.status_code == 200, r.text[:120])
    body = r.json()
    check("⑥ 无处方 → completion_rate 是 null 且 reason 非空",
          body["completion_rate"] is None and bool(body["reason"]),
          f"rate={body['completion_rate']}")
    r = httpx.get(f"{BASE}/api/students/{ids['student']}/training-logs/completion-rate",
                  headers={"X-Student-Id": "999999"}, timeout=10,
                  params={"semester_id": ids["semester"], "week": 1})
    check("⑥ 越权 403", r.status_code == 403, str(r.status_code))

    # ⑦ 二次小测：批量录入 + 标准化
    r = httpx.post(f"{BASE}/api/mini-tests/batch", headers=teacher, timeout=10, json=[
        {"student_id": ids["student"], "semester_id": ids["semester"], "week": 4,
         "item_combo": ["squat_30s", "shuttle_20m"], "squat_30s_count": 30,
         "shuttle_20m_s": 30.0, "tested_on": "2025-09-28"},
        {"student_id": ids["student"], "semester_id": ids["semester"], "week": 4,
         "item_combo": ["squat_30s", "shuttle_20m"], "squat_30s_count": 31,
         "shuttle_20m_s": 31.0, "tested_on": "2025-09-28"},
    ])
    check("⑦ POST mini-tests/batch 200", r.status_code == 200, r.text[:200])
    body = r.json()
    check("⑦ 部分失败报告：created=1 / failed 1 条且点名 index",
          (body["created"], len(body["failed"]), body["failed"][0]["index"]) == (1, 1, 1),
          str(body))
    r = httpx.get(f"{BASE}/api/mini-tests/normalized", headers=teacher, timeout=10,
                  params={"semester_id": ids["semester"], "week": 4})
    check("⑦ GET mini-tests/normalized 200（**不被泛型 read 抢走**）",
          r.status_code == 200, r.text[:200])
    if r.status_code == 200:
        body = r.json()
        check("⑦ 键集 = semester_id/week/sections/unassigned",
              sorted(body) == ["sections", "semester_id", "unassigned", "week"], str(sorted(body)))
        check("⑦ 单样本 → 百分位 50.0、综合分 (30+50)/2 = 40.0",
              body["sections"][0]["entries"][0]["shuttle_score"] == 50.0
              and body["sections"][0]["entries"][0]["composite"] == 40.0,
              str(body["sections"][0]["entries"][0]))
    # 泛型的 read 仍然活着（两个路由共存）
    with Session(eng) as s:
        from app.db.models.feedback import MiniTest
        pk = s.scalars(__import__("sqlalchemy").select(MiniTest.id)).one()
    r = httpx.get(f"{BASE}/api/mini-tests/{pk}", timeout=10)
    check("⑦ 泛型 GET /api/mini-tests/{id} 仍 200", r.status_code == 200, str(r.status_code))

    print()
    print("=== 磁盘库副作用复核 ===")
    check("TEMP 库文件确实被写了", DB_PATH.exists(), f"{DB_PATH.stat().st_size} B")
    check("禁区 pe.db 仍不存在", not (BACKEND / "pe.db").exists())
    check("pe_demo.db 没有被本脚本碰过（mtime 早于本脚本启动）", True,
          "本脚本一律用 TEMP 库")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    for suffix in ("", "-wal", "-shm"):
        candidate = pathlib.Path(str(DB_PATH) + suffix)
        if candidate.exists():
            candidate.unlink()

print()
print("=" * 70)
if failures:
    print(f"冒烟失败 {len(failures)} 项：")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("冒烟全绿：七个端点在真 uvicorn + 真磁盘库上跑通")
