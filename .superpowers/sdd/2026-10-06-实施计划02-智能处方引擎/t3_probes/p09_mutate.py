# -*- coding: utf-8 -*-
"""Step 7 变异验收 harness（硬规矩 #50/#53/#62/#65）。

**串行**：一次只跑一个相位（``python p09_mutate.py <名字>``），跑完立刻按字节复原并核 sha256。
**对照变异要在 AST 上确认真的改了代码**（#53）：``.py`` 的变异前后比对 ``ast.dump``，
``.yaml`` 的变异前后比对 ``yaml.safe_load`` 的结果。
"""
import ast
import hashlib
import pathlib
import subprocess
import sys

import yaml

BE = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\backend')
RP = BE / 'app/refdata_prescription.py'
TPL = BE / 'app/domain/prescription/templates.py'
EX = BE / 'data/exercises.yaml'
T01 = BE / 'data/prescription/RED-END-ABN-01.yaml'
G13 = BE / 'data/prescription/GRN-END-ABN-13.yaml'
TEST_TPL = BE / 'tests/domain/test_prescription_templates.py'


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16].upper()


def sub_once(text, old, new, nl='\n'):
    """按文件的**实际行尾**做一次性替换（``app/`` 下的 .py 是 CRLF、data 下的 YAML 是 LF）。

    ⚠️ 这一层是必需的：本 harness 第一次跑 M1 就是因为锚里写 ``\\n`` 而目标是 CRLF 文件、
    命中 0 次而炸（那次失败**没有改动任何文件**，故不构成一次变异相位）。
    """
    old = old.replace('\n', nl)
    new = new.replace('\n', nl)
    n = text.count(old)
    assert n == 1, '锚命中 %d 次（应为 1）：%r' % (n, old[:80])
    return text.replace(old, new)


def apply_m1(text, nl):
    """加载器把 pending 静默规范化成 approved（P3-A7 要挡的那个失效形态）。"""
    return sub_once(
        text,
        '    status = raw["status"]\n    try:\n        review_status = ReviewStatus(status)',
        '    status = raw["status"]\n    try:\n        review_status = ReviewStatus("approved")',
        nl,
    )


def apply_m5b(text, nl):
    """domain 侧的规则所有者被改坏：任何格子都判可达。"""
    return sub_once(
        text,
        '    return not (layer is Layer.GREEN and body_comp is BodyCompState.ABNORMAL)',
        '    return True',
        nl,
    )


def delete_entry(text, ref, nl):
    """从 exercises.yaml 里删掉一个顶层条目（含它前面的注释块）。"""
    lines = text.split('\n')
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith(ref + ':'):
            start = i
            break
    assert start is not None, ref
    head = start
    while head > 0 and lines[head - 1].startswith('#'):
        head -= 1
    end = start + 1
    while end < len(lines) and (lines[end].startswith(' ') or not lines[end].strip()):
        end += 1
    return '\n'.join(lines[:head] + lines[end:])


def apply_m2a(text, nl):
    return delete_entry(text, 'agility_ladder', nl)


def apply_m2b(text, nl):
    return delete_entry(text, 'interval_run', nl)


def apply_m3a(text, nl):
    return sub_once(text, 'week_deltas: [1.00, 1.05, 1.10, 0.85]',
                    'week_deltas: [1.00, 1.05, 0.85]', nl)


def apply_m3b(text, nl):
    """③ 的**隔离**变体：连 ``microcycle_weeks`` 一起改成 3，于是加载器的长度校验不再抢先开火。

    ⚠️ 锚带前导换行：文件头注释里也逐字印着 ``microcycle_weeks: 4`` 与
    ``weekly_frequency: 4``（那是「出处」那一段），不带换行的锚会命中 2 次。
    """
    text = apply_m3a(text, nl)
    return sub_once(text, '\nmicrocycle_weeks: 4 ', '\nmicrocycle_weeks: 3 ', nl)


def apply_m4a(text, nl):
    return sub_once(text, '\nweekly_frequency: 4 ', '\nweekly_frequency: 3 ', nl)


def apply_m4b(text, nl):
    """④ 的**隔离**变体：连第 4 天的 session 一起删，于是加载器的结构校验不再抢先开火。"""
    text = apply_m4a(text, nl)
    head, sep, tail = text.partition(nl + 'progression:' + nl)
    assert sep, 'progression 锚不在'
    cut = head.index(nl + '  - day: 4' + nl)
    return head[:cut + len(nl)] + 'progression:' + nl + tail


def apply_m5a(text, nl):
    # 锚带前导换行：文件头注释里也逐字印着 `reachable: false`（预留位那一段）
    return sub_once(text, '\nreachable: false', '\nreachable: true', nl)


def apply_m4c_loader(text, nl):
    """④ 的**合谋**变体（加载器那一半）：把加载器私有的指导文件档位改成红层 3 天。

    与 ``apply_m4b`` 同时用：只有「加载器那份表**和** YAML 一起改」才能让加载器放行，
    于是开火的就只剩测试侧那份字面量
    ``GUIDANCE_WEEKLY_FREQUENCY``——这正是 :data:`_GUIDANCE_FREQUENCY` 注释里写的
    「两侧刻意不同源」（硬规矩 #35）的兑现：任何**单侧**改坏都有一条守卫接住。
    """
    return sub_once(text, '_GUIDANCE_FREQUENCY = {Layer.RED: 4,',
                    '_GUIDANCE_FREQUENCY = {Layer.RED: 3,', nl)


MUTATIONS = {
    'M1': (RP, apply_m1, 'py'),
    'M2a': (EX, apply_m2a, 'yaml'),
    'M2b': (EX, apply_m2b, 'yaml'),
    'M3a': (T01, apply_m3a, 'yaml'),
    'M3b': (T01, apply_m3b, 'yaml'),
    'M4a': (T01, apply_m4a, 'yaml'),
    'M4b': (T01, apply_m4b, 'yaml'),
    'M5a': (G13, apply_m5a, 'yaml'),
    'M5b': (TPL, apply_m5b, 'py'),
}

#: 多目标变异：``{名字: [(路径, 变异函数, 类型), …]}``（**全部**改动一起生效、一起复原）
def apply_m4d(text, nl):
    """④ 的**测试侧**变体：只改测试里那份字面量 ``GUIDANCE_WEEKLY_FREQUENCY``。

    M4c 证明了「改加载器那份」会被 18 份 YAML 撞上（另 5 套红层的 weekly_frequency 仍是 4，
    加载器照样拒绝），故它**不能**隔离出测试侧那一份。本变异走另一侧：只把测试里的字面量
    改成红层 3 天，于是
    ``test_weekly_frequency_follows_the_guidance_document`` 的**支 1**
    （``assert GUIDANCE_WEEKLY_FREQUENCY == {"red": 4, "yellow": 3, "green": 2}``）必须开火
    ——它证明支 1 不是装饰，而是「测试侧那一份被改坏」的唯一守卫。两侧合起来才是
    硬规矩 #35 那句「刻意不同源」的完整兑现。
    """
    return sub_once(text, 'GUIDANCE_WEEKLY_FREQUENCY = {"red": 4, "yellow": 3, "green": 2}',
                    'GUIDANCE_WEEKLY_FREQUENCY = {"red": 3, "yellow": 3, "green": 2}', nl)


MULTI = {
    'M4c': [(RP, apply_m4c_loader, 'py'), (T01, apply_m4b, 'yaml')],
    'M4d': [(TEST_TPL, apply_m4d, 'py')],
}


def main():
    name = sys.argv[1]
    log = open(pathlib.Path(__file__).with_name('mutation_log.txt'), 'a', encoding='utf-8')

    def emit(line):
        print(line)
        log.write(line + '\n')
        log.flush()

    targets = MUTATIONS.get(name)
    targets = [targets] if targets else MULTI[name]
    originals = []
    try:
        for path, fn, kind in targets:
            original = path.read_bytes()
            originals.append((path, original))
            nl = '\r\n' if b'\r\n' in original else '\n'
            emit('=== %s ===  目标 %s  行尾=%s  CRLF=%d'
                 % (name, path.relative_to(BE), repr(nl), original.count(b'\r\n')))
            emit('  改前 bytes=%d sha16=%s' % (len(original), sha(original)))
            text = original.decode('utf-8')
            mutated_text = fn(text, nl)
            assert mutated_text != text, '变异没有改变文本'
            path.write_bytes(mutated_text.encode('utf-8'))
            after = path.read_bytes()
            if kind == 'py':
                changed = ast.dump(ast.parse(text)) != ast.dump(ast.parse(mutated_text))
                emit('  AST 真的变了吗? %s' % changed)
                assert changed
            else:
                changed = yaml.safe_load(text) != yaml.safe_load(mutated_text)
                emit('  解析结果真的变了吗? %s' % changed)
                assert changed
            emit('  改后 bytes=%d sha16=%s' % (len(after), sha(after)))
        proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', '--no-header', '-p',
                               'no:cacheprovider'],
                              cwd=BE, capture_output=True, text=True)
        out = proc.stdout + proc.stderr
        emit('  pytest 退出码 = %d' % proc.returncode)
        tail = [l for l in out.splitlines() if l.strip()]
        summary = [l for l in tail if ' passed' in l or ' failed' in l or ' error' in l]
        emit('  摘要行: %s' % (summary[-1] if summary else '(无)'))
        failed = sorted({l.split(' - ')[0].strip() for l in tail
                         if l.startswith('FAILED') or l.startswith('ERROR')})
        emit('  红的条目数（去重）= %d' % len(failed))
        for f in failed:
            emit('     %s' % f)
        causes = [l.strip() for l in tail
                  if l.strip().startswith('E  ') and
                  ('ValueError' in l or 'AssertionError' in l or 'FileNotFoundError' in l)]
        for c in dict.fromkeys(causes[:4]):
            emit('  真因: %s' % c[:400])
    finally:
        for path, original in originals:
            path.write_bytes(original)
            restored = path.read_bytes()
            emit('  复原核 %s sha16=%s  一致? %s'
                 % (path.name, sha(restored), sha(restored) == sha(original)))
            assert restored == original
        log.close()


if __name__ == '__main__':
    main()
