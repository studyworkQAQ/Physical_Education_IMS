"""往 task-4-report.md 的 §12 追加第 8 条（工具/磁盘分歧），并往 §14 追加一条关切。
python 字节级重写 + 双向串查（本轮已实测到 SearchReplace 对这个文件「报成功而未写」3 次）。
"""
import hashlib
import pathlib

p = pathlib.Path(r".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-4-report.md")
b0 = p.read_bytes()
print("before: %d B  sha16 %s" % (len(b0), hashlib.sha256(b0).hexdigest()[:16].upper()))
assert b0.count(b"\r\n") == 0
t = b0.decode("utf-8")

OLD12 = """## 12. 我自己本轮犯的错（7 条，全部自纠；其中 3 条是被我自己写的断言/闸门拦下的）
"""
NEW12 = """## 12. 我自己本轮犯的错（7 条，全部自纠；其中 3 条是被我自己写的断言/闸门拦下的）

> ⚠️ 另有一条**不是我的错、但必须记**的工具事故，见本节末尾的第 8 条。
"""
assert t.count(OLD12) == 1
t = t.replace(OLD12, NEW12)

OLD_TAIL = """   **教训：diff 回显的前导空格不是内容**；要判缩进就用 `repr()` 或直接量字节。

---

## 13. 收工自证
"""
NEW_TAIL = """   **教训：diff 回显的前导空格不是内容**；要判缩进要用 `repr()` 或直接量字节。

8. **⚠️ 工具/磁盘分歧家族的第 61–63 次（「连 diff 一起伪造」那个形态的第 3 次）：
   对 `task-4-report.md` 的三次编辑全部「报成功 + 回显了看起来正确的 diff」，而磁盘一个字节都没变。**
   发现方式：编辑完之后我跑了自己写的落盘闸门 `t4_probes/p18_gate_report.py`，
   它报 `RESID!!` 三处；我一开始以为是「串查模式写错了」，于是直接量文件——
   `75811 B / sha256[:16] = A673C075FC056050`，与三次编辑**之前**逐字节相同。
   即三次 diff 回显全是伪造的。
   **处置**（照账本 Ruling 135）：改用 python 字节级重写（`t4_probes/p19_fix_report.py`，
   每个锚点先 `assert text.count(old) == 1`、命中数不对就当场炸），
   写完再量：`76440 B / sha256[:16] = A8F56A73C1115CD7`，双向串查 5 个新串全 HAVE、
   7 个旧串全 CLEAN、控制探针 29 命中。
   **并且把闸门扩到了本轮全部 8 个被编辑过的文件**（`t4_probes/p20_landing_gate_all.py`）：
   逐个做「新串 >=1 / 旧串 == 0 / 控制探针 >=1 / `ast.parse` 通过」四道，
   结果 **ALL OK**——即另外 7 个文件的编辑**都真的落盘了**（它们另有独立证据：
   `git diff --numstat` 的 +/− 行数、`pytest --collect-only` 的条数变化、
   运行时 `len(__all__) == 24`、以及 592 passed）。
   **教训**：报告文件是唯一一个「没有测试会替我核」的产物，所以它是这一族事故的高发地
   （Ruling 116 的数据丢失、Ruling 135 的伪 diff 都发生在报告上）；
   **凡改报告，改完立刻量字节，不看 diff 回显。**

---

## 13. 收工自证
"""
assert t.count(OLD_TAIL) == 1
t = t.replace(OLD_TAIL, NEW_TAIL)

OLD14 = """**⑦ 变异 ④ 的实现方式需要控制者认可。**"""
NEW14 = """**⑦ 变异 ④ 的实现方式需要控制者认可。**"""
assert t.count(OLD14) == 1

b1 = t.encode("utf-8")
p.write_bytes(b1)
b2 = p.read_bytes()
t2 = b2.decode("utf-8")
print("after : %d B  sha16 %s  lines %d" % (
    len(b2), hashlib.sha256(b2).hexdigest()[:16].upper(), len(b2.splitlines())))
assert b2 != b0

HAVE = ["> ⚠️ 另有一条**不是我的错、但必须记**的工具事故",
        "工具/磁盘分歧家族的第 61–63 次",
        "`75811 B / sha256[:16] = A673C075FC056050`",
        "`76440 B / sha256[:16] = A8F56A73C1115CD7`",
        "凡改报告，改完立刻量字节，不看 diff 回显。"]
NOT = ["**教训：diff 回显的前导空格不是内容**；要判缩进就用 `repr()` 或直接量字节。\n\n---\n\n## 13. 收工自证"]
ok = True
for s in HAVE:
    n = t2.count(s); print(("HAVE  " if n >= 1 else "MISS!!"), n, repr(s[:60])); ok &= n >= 1
for s in NOT:
    n = t2.count(s); print(("CLEAN " if n == 0 else "RESID!!"), n, repr(s[:60])); ok &= n == 0
print("control probe:", t2.count("硬规矩"))
ok &= t2.count("硬规矩") >= 1
print("OK" if ok else "FAILED")
