# -*- coding: utf-8 -*-
"""pe_fr3_commit.py — 用 UTF-8 临时文件写 commit message 并 git commit -F（Global Constraints 第 7 条）。

用法: python pe_fr3_commit.py <仓库根>
"""
import os
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(sys.argv[1]).resolve()
FILES = ["backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py"]

MSG = """test: Plan02 Task1 fix round 3，给两条架构守卫的 _absolute 补两份回归测试 + 更正 Ruling 42 的机制错话

Ruling 46 fix round 2 修掉的两个假绿 bug 此前在仓库里没有任何断言看着：删掉 _absolute 里的
if level - 1 > len(package): return None，或把 tail = module or name 改回 tail = module，
479 条全绿。这是硬规矩 #50 的欠账——上一轮的红/绿双输入取证是在合成树上做的一次性动作，
没有沉淀成仓库里的断言。本轮在 test_domain_purity.py 与 test_layering.py 各加一条
test_absolute_folding_matches_resolve_name（硬规矩 #51：两份 _absolute 就要两份回归测试，
漏一份等于留一条没人看的守卫），479 -> 481 passed，这是派单预授权的计数变化。

判据不抄任何期望值表：每格现场调一次 importlib.util.resolve_name("." * level +
(module or name), ".".join(package))，它对同一输入抛 ImportError 的那一档期望值就是 None。
这样测试锚在 Python 自己的语义上，而不是锚在某一次亲跑出来的一张表上（Ruling 45）。矩阵以
(module, level, package, name) 四元组为参数、不用「from … 的字面写法」当唯一标识，11 格覆盖：
level == 0 的绝对导入、level == 1 的包内合法导入（绿档，硬规矩 #50 的 ②）、跨包指向 app.seed
的真 offender、module 为空的 4 个形状（app/pipeline、app/db、app/db/models、app/domain）、
Ruling 35 的两个越界形状，外加 level - 1 == len(package) 这个由 not anchor 兜住的边界档。
两份的期望颜色列刻意不相同：("", 2, ("app","db","models"), "seed") 折成 app.db.seed，在
layering 的 app.seed 前缀下是 GREEN、在 purity 的白名单下是 RED——折算串错了不等于判定错了
（Ruling 41）。另额外钉住 Ruling 36 的另一半：一个 ImportFrom 节点带 N 个名字必须展开成 N 条
（from .. import seed, pipeline 要出 app.seed 与 app.pipeline 两条）。

变异验收 12 个相位全 PASS，两份分别做。① 删掉越界守卫：purity 侧报 _absolute('domain', 4,
('app','domain'), 'tables') = 'app.domain' 而 resolve_name('....domain','app.domain') = None、
并判成 GREEN 期望 RED；layering 侧报 _absolute('seed', 5, ('app','db','models'), 'generate')
= 'app.db.seed' 而 resolve_name 为 None。② tail = module：两侧各报 5 / 8 条不一致，含
_absolute('', 2, ('app','pipeline'), 'seed') = 'app' 而 resolve_name('..seed','app.pipeline')
= 'app.seed'。③ 额外的 names 展开变异（超出派单，为证明新测试末尾那段是活的）：两侧都报
['app.seed'] != ['app.seed','app.pipeline']，而同一次跑里旧的 4 条守卫 4 passed 无感——
正是 Ruling 46 说的那个口子。每个变异都在 AST 上确认「真的改了代码」，并做了两组对照
（硬规矩 #53）：M0 不变异时 2 passed（尺子能报绿）、M1 把 anchor 的切片算式等价改写成
package[: len(package) - level + 1] 时 AST 变了但仍 2 passed（尺子不是恒红）。只变异一份时
另一份保持绿，证明两条回归测试各自看着自己那一份 _absolute。

Ruling 42 test_domain_purity.py:167 那句「会折成 app.domain、命中白名单前缀 app.domain.
变成真绿」机制错了：_is_allowed 的实现是 module == ALLOWED_PACKAGE or
module.startswith(ALLOWED_PACKAGE + ".")，折算出的精确串 app.domain 命中的是相等那一支
（本机实跑 "app.domain" == ALLOWED_PACKAGE -> True、"app.domain".startswith(ALLOWED_PACKAGE
+ ".") -> False）。改成写明「命中的是相等这一支、不是 startswith 那一支」并附两行实跑值，
结论（真绿）不变。同文件 :139 与 :351（原 :246，因本轮插入而后移）说的是
app.domain.seed.generate，startswith("app.domain.") 确为 True，是正确的，未动；改完全仓
grep「白名单前缀」只剩这两处。layering 侧 _absolute 的 docstring 逐字未动。

硬规矩 #32 本轮形态：两个守卫文件都真改了代码，故剥 docstring 后 ast.dump 比基线必然是
DIFF——自证改成逐顶层单元比对（带三组对照：注入语义变异必须报 DIFF、基线自比必须报 SAME、
只改 docstring 必须「不剥时报 DIFF、剥掉后报 SAME」）。结果：两个文件有差异的顶层单元都只有
新增的 test_absolute_folding_matches_resolve_name 一个，_absolute / _imported_modules /
_package_of / _is_allowed / _is_forbidden / 三个既有 test_* / <module-level> 全部「未动」
（就地 import importlib.util 正是为了不碰 <module-level>）；既有 5 条 assert 逐字未动；
git diff --name-only 1fa9941 只含这两个守卫文件，backend/app/** 命中 0 个。两份 _absolute
剥 docstring 后函数体 AST 仍逐字相同（硬规矩 #51 闸门复跑 PASS）。

收工闸门 python -m pytest -q = 481 passed；-W error = 481 passed / 0 error；
--cov=app/domain --cov-branch = 399 stmts / Miss 0 / 114 branch / BrPart 0 / 100%
（同一次跑 480 passed, 1 skipped，那 1 条 skip 是 test_backfill.py 在 --cov 下的既有自我跳过）。
禁区 backend/pe.db 不存在、backend/data/seed/ 0 文件、national_standard_2014.csv
sha256[:16] = D2C8E539E2FA0029 且 CRLF = 0。变异全部按字节还原并核 sha256，全程未用
git checkout / git restore。
"""


def main():
    fd, path = tempfile.mkstemp(prefix="pe_fr3_msg_", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(MSG)
    raw = pathlib.Path(path).read_bytes()
    print("commit message 临时文件: %s  %d 字节  裸LF=%d CRLF=%d"
          % (path, len(raw), raw.count(b"\n") - raw.count(b"\r\n"), raw.count(b"\r\n")))
    r = subprocess.run(["git", "status", "--short"], cwd=str(REPO), capture_output=True)
    print("提交前 git status --short:")
    for l in r.stdout.decode("utf-8").splitlines():
        print("   ", l)
    r = subprocess.run(["git", "add", "--"] + FILES, cwd=str(REPO), capture_output=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(REPO), capture_output=True)
    staged = r.stdout.decode("utf-8").split()
    print("已暂存:", staged)
    assert staged == FILES, staged
    r = subprocess.run(["git", "commit", "-F", path], cwd=str(REPO), capture_output=True)
    print("commit rc=%d" % r.returncode)
    print(r.stdout.decode("utf-8", "replace"))
    print(r.stderr.decode("utf-8", "replace"))
    os.unlink(path)
    assert r.returncode == 0
    r = subprocess.run(["git", "log", "--oneline", "-3"], cwd=str(REPO), capture_output=True)
    print(r.stdout.decode("utf-8"))
    r = subprocess.run(["git", "status", "--short"], cwd=str(REPO), capture_output=True)
    out = r.stdout.decode("utf-8").splitlines()
    print("提交后 git status --short: %d 行 %s" % (len(out), out))


main()
