"""Plan 03 Task 6 / Commit 1 的手术脚本：把 6 个通用 YAML 助手从
``app/refdata_prescription.py`` 抽到 ``app/refdata_yaml.py``（P6-A2）。

⚠️ 探针/手术脚本一律住在账本目录、不住 ``backend/`` 下（硬规矩 #108：架构守卫会 AST
解析工作树里的**全部** ``.py``，含未入库的）。

用**唯一锚点**做字符串替换，不用裸行号（行号会被编辑推走，Plan 02 账本 CE-7）。
每一步都先断言锚点恰好命中 1 次，命中数不对就当场 ``SystemExit``、不写盘。
"""
import hashlib
import pathlib
import sys

BACKEND = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")
TARGET = BACKEND / "app" / "refdata_prescription.py"

# ---------------------------------------------------------------- 读入（CRLF → LF）
raw_bytes = TARGET.read_bytes()
before_sha = hashlib.sha256(raw_bytes).hexdigest()[:16].upper()
text = raw_bytes.decode("utf-8")
crlf = text.count("\r\n")
text = text.replace("\r\n", "\n")
print(f"[before] bytes={len(raw_bytes)} sha256[:16]={before_sha} CRLF={crlf} "
      f"bare_LF={text.count(chr(10)) - crlf}")
if text.count("\ufeff"):
    sys.exit("BOM 出现了，停手")


def sub_once(haystack: str, needle: str, replacement: str, tag: str) -> str:
    """把 ``needle`` 恰好替换一次；命中数不是 1 就停手（不写盘）。"""
    hits = haystack.count(needle)
    if hits != 1:
        sys.exit(f"[{tag}] 锚点命中 {hits} 次，应恰好 1 次，停手")
    print(f"[{tag}] 锚点命中 1 次，OK")
    return haystack.replace(needle, replacement, 1)


# ---------------------------------------------------------------- ① 模块 docstring 补一段
DOC_ANCHOR = """那一档退化成 PyYAML 自己的 mark（已包成 ``ValueError`` 并带上文件名）。
"""
DOC_NEW = """那一档退化成 PyYAML 自己的 mark（已包成 ``ValueError`` 并带上文件名）。

⚠️ **Plan 03 Task 6 把那套机制里通用的 6 个助手抽进了 :mod:`app.refdata_yaml`**
（P6-A2：计划原文给的处置是「**直接照抄那套形状**，不要另发明一套」，而「照抄」在字面上
等于复制、**复制就是第二个所有者**，Global Constraint #3）。本模块从此只留 5 个**薄适配器**
（:func:`_fail` / :func:`_exact_keys` / :func:`_as_int` / :func:`_as_float` /
:func:`_as_optional_text`，各一句「转发 + 绑 :data:`_DOC_KIND`」）与一个别名
:data:`_line_index`。⚠️ **报错文本逐字不变**：那 6 个助手的逻辑只有
:mod:`app.refdata_yaml` 一份，而 ``doc_kind`` 由本模块绑成 ``"处方模板"``
（它原先是硬编码在 ``_fail`` 里的前缀；搬进共用模块之后若不参数化，
``alert_rules.yaml`` 被改坏时就会报「处方模板 …/alert_rules.yaml 第 3 行」）。
守卫是 ``tests/test_refdata_alerts.py``（AST 钉「6 个名字各只有一处定义」与
「适配器只转发」，另加 ``_line_index is refdata_yaml.line_index`` 的身份比对）。
"""
text = sub_once(text, DOC_ANCHOR, DOC_NEW, "docstring")

# ---------------------------------------------------------------- ② 加 import
IMPORT_ANCHOR = "from app.db.models.prescription import Exercise, PrescriptionTemplate\n"
IMPORT_NEW = "from app import refdata_yaml\n" + IMPORT_ANCHOR
text = sub_once(text, IMPORT_ANCHOR, IMPORT_NEW, "import")

# ---------------------------------------------------------------- ③ 换掉 6 个定义
START = "def _line_index(text: str) -> dict[tuple, int]:\n"
END = "def _intensity(path, lines, where, raw) -> Intensity:\n"
start_at = text.index(START)
end_at = text.index(END)
if not (0 < start_at < end_at):
    sys.exit(f"锚点顺序不对: start_at={start_at} end_at={end_at}")
removed = text[start_at:end_at]
removed_defs = [ln for ln in removed.split("\n") if ln.startswith("def ")]
print(f"[block] 待替换 {len(removed)} 字符 / {removed.count(chr(10))} 行")
for line in removed_defs:
    print("        顶层 def:", line)
if len(removed_defs) != 6:
    sys.exit(f"待替换块里有 {len(removed_defs)} 个顶层 def，应恰好 6 个，停手")

ADAPTERS = '''#: 本模块加载的那些 YAML 的**文档种类**，绑进 :func:`app.refdata_yaml.fail` 的报错前缀。
#: ⚠️ 它此前是硬编码在 ``_fail`` 里的 ``f"处方模板 {path} …"``；Plan 03 Task 6 把那 6 个
#: 助手抽进 :mod:`app.refdata_yaml` 之后（P6-A2），前缀必须由**各消费者自己**说清，
#: 否则 ``alert_rules.yaml`` 被改坏时会报「处方模板 …/alert_rules.yaml 第 3 行」。
_DOC_KIND = "处方模板"

#: 行号索引不需要 ``doc_kind``，故直接别名引用**同一个函数对象**（不是副本）。
#: 守卫是 ``tests/test_refdata_alerts.py`` 的
#: ``test_line_index_is_the_same_object_in_every_consumer``（``is`` 比对）。
_line_index = refdata_yaml.line_index


def _fail(path, lines, key_path, message) -> ValueError:
    """**薄适配器**：转发给 :func:`app.refdata_yaml.fail` 并绑上本模块的 :data:`_DOC_KIND`。

    ⚠️ **本函数除本 docstring 外只许有那一句**：行号索引怎么用、查不到时怎么退到父路径、
    那一档的措辞是什么，全部住在 :mod:`app.refdata_yaml`；这里再写一遍就是第二个所有者
    （Global Constraint #3）。守卫是 ``tests/test_refdata_alerts.py`` 的
    ``test_every_consumer_binds_doc_kind_through_a_one_statement_adapter``
    （AST 数函数体长度 + 查那一句在调谁）。**保留适配器而不是逐点改 44 处调用**的理由见
    :mod:`app.refdata_yaml` 的模块 docstring（逐点改就是 44 次「有机会改坏一条被测试逐字
    钉住的报错文本」的机会）。

    ``key_path`` / ``lines`` / ``message`` 三个参数的语义逐字见
    :func:`app.refdata_yaml.fail`。
    """
    return refdata_yaml.fail(path, lines, key_path, message, doc_kind=_DOC_KIND)


def _exact_keys(path, lines, where, raw, required, label) -> None:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。"""
    refdata_yaml.exact_keys(path, lines, where, raw, required, label,
                            doc_kind=_DOC_KIND)


def _as_int(path, lines, where, raw, label) -> int:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。"""
    return refdata_yaml.as_int(path, lines, where, raw, label, doc_kind=_DOC_KIND)


def _as_float(path, lines, where, raw, label) -> float:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。"""
    return refdata_yaml.as_float(path, lines, where, raw, label, doc_kind=_DOC_KIND)


def _as_optional_text(path, lines, where, raw, label) -> str | None:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。"""
    return refdata_yaml.as_optional_text(path, lines, where, raw, label,
                                         doc_kind=_DOC_KIND)


'''
text = text[:start_at] + ADAPTERS + text[end_at:]

# ---------------------------------------------------------------- 写回（LF → CRLF）
out = text.replace("\n", "\r\n").encode("utf-8")
if out.startswith(b"\xef\xbb\xbf"):
    sys.exit("写出了 BOM，停手")
TARGET.write_bytes(out)
after = TARGET.read_bytes()
after_crlf = after.count(bytes([13, 10]))
after_lf = after.count(bytes([10]))
after_sha = hashlib.sha256(after).hexdigest()[:16].upper()
print(f"[after ] bytes={len(after)} sha256[:16]={after_sha} "
      f"CRLF={after_crlf} bare_LF={after_lf - after_crlf}")
print("[done] 写回完成")
