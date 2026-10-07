import pathlib, subprocess, sys

MSG = """docs: Plan02 Task4 报告回填 §13.1（commit fe5e6dd 之后的实测证据）+ 入库 p23/p24 取证脚本

主体 commit 是 fe5e6dd。本节回填的数字只能在 commit 之后取到（口径照 Task 3 的 ab075d3）：

* HEAD = fe5e6dd、git status --short 除本节脚本外 0 行、commit 之后复跑全量 592 passed in 62.64s
* git ls-files --eol：index 侧 8 个文件全是 i/lf；4 个既有文件工作树仍 w/crlf、
  3 个新建 .py 与报告是 w/lf；报告带 attr/-text（.gitattributes 对 .superpowers/** 的规定）
* git show HEAD:<path> 的 blob 字节 vs 工作树字节：8 个文件**归一化后逐字节相同**；
  4 个「裸字节不同」的差值恰好等于各自工作树的 CRLF 行数（106 / 1292 / 797 / 563）
* 禁区四项复验：CSV 21412 B / D2C8E539E2FA0029、exercises.yaml 22739 B / 3DE598AF38631209、
  exercise_equivalence.yaml 8245 B / 822CB86A5E998301（都是归一化后 sha256[:16]、CRLF 全 0）；
  pe.db 不存在、data/seed 0 文件、Base.metadata.tables = 16 张；
  git diff ab075d3..HEAD -- backend/data 为空、3473dc6..HEAD 对 backend/data /
  .gitattributes / backend/app/seed 都为空；SDD 目录下无 _xxx.py / tmp 残留
* 报告 78226 B / sha256[:16] EAF9A6448C81534B → 81845 B / 1109 行 / sha256[:16] 4786ED217679E998，
  追加前先做字节备份 t4_probes/task-4-report.md.bak-before-131（硬规矩 #68），
  追加用 python 字节级重写 + 双向串查（本轮已实测到 SearchReplace 对这个文件
  「报成功并回显 diff、而磁盘逐字未写」3 次，见报告 §12 第 8 条）
"""

path = pathlib.Path(".git/T4_DOCS_MSG.txt")
path.write_bytes(MSG.encode("utf-8"))
r = subprocess.run(["git", "commit", "-F", str(path)], capture_output=True, text=True,
                   encoding="utf-8")
print(r.stdout)
print(r.stderr)
sys.exit(r.returncode)
