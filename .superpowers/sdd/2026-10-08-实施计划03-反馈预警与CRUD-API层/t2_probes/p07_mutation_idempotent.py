"""变异取证：证明 test_build_demo_feedback_is_idempotent 不是恒真的。

把 `_training_logs` 里的 `repo.upsert(...)` 换成裸 `session.add(...)`（即去掉幂等），
跑那一条测试，然后按字节还原原文件并复核 sha256。
"""
import hashlib
import pathlib
import subprocess
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"
TARGET = BACKEND / "app" / "demo_data.py"
original = TARGET.read_bytes()
digest = hashlib.sha256(original).hexdigest()

MUTATE_FROM = b"""            repo.upsert(
                session,
                TrainingLog,
                ("student_id", "log_date"),
                {"""
MUTATE_TO = b"""            session.add(TrainingLog(**{"""

# 文件在磁盘上是纯 CRLF，故把两个字面量也换成 CRLF 再匹配
MUTATE_FROM = MUTATE_FROM.replace(b"\n", b"\r\n")
MUTATE_TO = MUTATE_TO.replace(b"\n", b"\r\n")
assert original.count(MUTATE_FROM) == 1, original.count(MUTATE_FROM)
mutated = original.replace(MUTATE_FROM, MUTATE_TO)
# 对应的收尾括号也要改：upsert 的 dict 后面是 `            )`，add 的是 `            }))`
CLOSE_FROM = b"""                    "batch_id": batch_id,
                },
            )
    session.flush()""".replace(b"\n", b"\r\n")
CLOSE_TO = b"""                    "batch_id": batch_id,
            }))
    session.flush()""".replace(b"\n", b"\r\n")
assert mutated.count(CLOSE_FROM) == 1, mutated.count(CLOSE_FROM)
mutated = mutated.replace(CLOSE_FROM, CLOSE_TO)

try:
    TARGET.write_bytes(mutated)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q",
         "tests/test_demo_data.py::test_build_demo_feedback_is_idempotent"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print("--- mutated run (期望 RED) ---")
    print(proc.stdout[-1800:])
    print("returncode =", proc.returncode)
finally:
    TARGET.write_bytes(original)

after = TARGET.read_bytes()
print("restored sha256 match:", hashlib.sha256(after).hexdigest() == digest)
print("CRLF =", after.count(b"\r\n"), "bareLF =", after.count(b"\n") - after.count(b"\r\n"))
