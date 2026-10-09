"""写 commit 1 的信息（UTF-8 无 BOM）到 TEMP，供 git commit -F 用。"""
import os
import pathlib

MESSAGE = """refactor(refdata): 把 6 个通用 YAML 报错助手抽进 app/refdata_yaml.py（P6-A2）

计划 Task 6 给的处置是「直接照抄 refdata_prescription 那套形状，不要另发明一套」，
而「照抄」在字面上等于复制、复制就是第二个所有者（Global Constraint #3）。故把
line_index / fail / exact_keys / as_int / as_float / as_optional_text 搬进新模块
app/refdata_yaml.py，refdata_prescription.py 只留 5 个「一句转发」的薄适配器
（_fail / _exact_keys / _as_int / _as_float / _as_optional_text）与一个
_line_index 别名——那 6 个名字在原模块共有 57 处调用点（AST 实测），逐点改就是
57 次改坏一条被测试逐字钉住的报错文本的机会。

⚠️ 搬家时多出一个 doc_kind **必填关键字参数**（计划的 P6-A2 没提这一条）：
fail 的消息前缀原先硬编码成「处方模板」，原样共用的话 alert_rules.yaml 被改坏时
会报「处方模板 …/alert_rules.yaml 第 3 行」——指着一份预警阈值文件说它是处方模板，
Review Focus 第 5 条要的「指出是哪个文件哪一行哪个键」当场变成假话。没有缺省值，
于是「忘了传」是 TypeError 而不是静默用别人的措辞。**报错文本逐字不变**
（tests/domain/test_prescription_templates.py 那两条 match="处方模板" 仍绿）。

守卫 tests/test_refdata_alerts.py 5 条：AST 钉 6 个名字在 app/ 下各只有一处 def、
5 个适配器的函数体恰好一句且在调 refdata_yaml.<同名>、_line_index is
refdata_yaml.line_index、doc_kind 是 KEYWORD_ONLY 且无缺省 + 逐消费者绑对措辞、
refdata_yaml 不 import app 里的任何东西（它是叶子，否则环就出来了）。

956 → 961 passed。_PRESCRIPTION_PUBLIC_BASELINE 仍 51（它钉的是
app.domain.prescription.__all__，与本模块的公开面无关）。
"""

out = pathlib.Path(os.environ["TEMP"]) / "t6_commit1.txt"
out.write_bytes(MESSAGE.encode("utf-8"))
data = out.read_bytes()
print("wrote", out, len(data), "bytes; BOM:", data.startswith(b"\xef\xbb\xbf"))
