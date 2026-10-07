import pathlib, hashlib

p = pathlib.Path(r".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-4-report.md")
b = p.read_bytes()
t = b.decode("utf-8")
print("bytes", len(b), "lines", len(b.splitlines()), "CRLF", b.count(b"\r\n"),
      "sha16(raw)", hashlib.sha256(b).hexdigest()[:16].upper())

must = [
    "## 0. 环境与基线复现", "## 1. 交付清单", "## 2. TDD 的红 → 绿链",
    "## 3. 交付内容的设计决定", "## 4. 32 格穷举的实测分类", "## 5. 新增/搬动测试逐条清单",
    "## 6. 覆盖率增量的解释", "## 7. 变异验收", "## 8. 改动面自证",
    "## 9. 两份架构守卫的改动", "## 10. Task 3 转来的 4 项",
    "## 11. 我发现的控制者错误", "## 12. 我自己本轮犯的错", "## 13. 收工自证",
    "## 14. 关切与未尽事项",
    "CE-1", "CE-2", "CE-3", "CE-4", "CE-5", "CE-6", "CE-7",
    "ImportError: cannot import name 'MatchInput'",
    "{'no_layer': 8, 'no_bucket': 6, 'unreachable': 3, 'matched': 15}",
    "no_bucket: **5**", "40E08F5587C92F46", "D2C8E539E2FA0029",
    "541 stmts / Miss 0 / 132 branch", "592 passed", "### 13.1 commit 之后补录",
]
mustnot = [
    # 硬规矩 #74：被撤销的原句不得在本报告里逐字复述（否则「grep 旧串应当 0 命中」这道闸门失效）
    "MatchResult",
    "若写相对导入会变 17",
    "计数变 17、level 分布变",
    "Task 2 的形状（fix round 5 新加",
    "Task 2 会新建 app/domain/prescription/ 子包（今天不存在）",
    "这一层子包已经建出，Task 3 的",
    "今天看着它的本来只有两条",
    "NO_BUCKET:4, UNREACHABLE:5",
]
ok = True
for s in must:
    n = t.count(s)
    print(("HAVE  " if n >= 1 else "MISS!!"), n, repr(s[:64]))
    ok &= n >= 1
for s in mustnot:
    n = t.count(s)
    print(("CLEAN " if n == 0 else "RESID!!"), n, repr(s[:64]))
    ok &= n == 0
# 查询本身有效性对照（硬规矩 #48：任何「0 命中」的结论先用一个已知存在的串验证）
print("control probe (must be >=1):", t.count("硬规矩"))
ok &= t.count("硬规矩") >= 1
print("tail:", repr(t[-120:]))
print("OK" if ok else "FAILED")
