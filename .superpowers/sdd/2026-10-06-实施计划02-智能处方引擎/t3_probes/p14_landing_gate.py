# -*- coding: utf-8 -*-
"""落盘闸门（硬规矩 #48 升级口径）：每个改过的文件做双向串查——
新串命中 >= 1 **且** 旧串残留 == 0。任何一条不满足就是「报成功而磁盘未写」。
"""
import hashlib, pathlib
BE = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\backend')
ROOT = BE.parent

CASES = [
    # (文件, 新串, 旧串)
    (ROOT / '.gitattributes',
     'backend/data/**/*.yaml text eol=lf',
     None),
    (BE / 'app/domain/prescription/templates.py',
     'TEMPLATE_LAYERS: frozenset[Layer] = frozenset({Layer.RED, Layer.YELLOW, Layer.GREEN})',
     '__all__ = ["ImpactLevel"]'),
    (BE / 'app/domain/prescription/templates.py',
     'def is_reachable(layer: Layer, body_comp: BodyCompState) -> bool:',
     '本模块今天没有任何自己的定义'),
    (BE / 'app/domain/prescription/__init__.py',
     'from app.domain.stratify import Layer',
     'Task 3 往 ``templates.py`` / ``match.py`` 加东西'),
    (BE / 'app/domain/prescription/__init__.py',
     '"is_reachable",\n]',
     None),
    (BE / 'app/refdata_prescription.py',
     'PRESCRIPTION_DIRNAME = "prescription"',
     '18 套处方模板                 Task 3      ``data/prescription/*.yaml`` 的加载器与校验'),
    (BE / 'app/refdata_prescription.py',
     'def sync_templates(session: Session) -> int:',
     '的 24 个键里'),
    (BE / 'app/refdata_prescription.py',
     'ReviewStatus("approved")' if False else 'review_status = ReviewStatus(status)',
     None),
    (BE / 'app/db/models/prescription.py',
     'class PrescriptionTemplate(Base):',
     'test_all_fifteen_tables_created'),
    (BE / 'app/db/models/prescription.py',
     '_in_domain(\n            "review_status", REVIEW_STATUSES, "ck_prescription_template_review_status"\n        ),',
     '它是本小节唯一一张'),
    (BE / 'app/db/models/__init__.py',
     'test_all_sixteen_tables_created',
     'test_all_fifteen_tables_created'),
    (BE / 'data/exercises.yaml',
     'energy_expenditure_plus_5min_hiit:',
     'medium **10** 个、low **8** 个，合计 23'),
    (BE / 'data/exercises.yaml',
     '【条目数 24 的口径】',
     '【条目数 23 的口径】'),
    (BE / 'data/exercises.yaml',
     'medium **11** 个、low **8** 个，合计 24',
     '这个 29 字符的名字是本文件最长的 ref'),
    (BE / 'tests/domain/test_prescription_templates.py',
     '"GRN-SPD-NOR-18": "2389C1A03E6ABBCE"',
     '"GRN-SPD-NOR-18": "__PENDING__"'),
    (BE / 'tests/domain/test_prescription_templates.py',
     'def test_sessions_total_is_fifty_four():',
     'assert templates.__all__ == ["ImpactLevel"]'),
    (BE / 'tests/domain/test_prescription_templates.py',
     '"TEMPLATE_LAYERS",\n        "Layer",',
     None),
    (BE / 'tests/test_refdata_prescription.py',
     'EXERCISES_FINGERPRINT = "3DE598AF38631209"',
     'EXERCISES_FINGERPRINT = "63033BBD7F68CC1F"'),
    (BE / 'tests/test_refdata_prescription.py',
     '("is_reachable", "app.domain.prescription.templates"),',
     '_PRESCRIPTION_PUBLIC_BASELINE + ["Template"]'),
    (BE / 'tests/test_refdata_prescription.py',
     'assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 20',
     'assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 7'),
    (BE / 'tests/test_refdata_prescription.py',
     'names + ["__NOT_IN_THE_PUBLIC_FACE__"]',
     None),
    (BE / 'tests/test_refdata_prescription.py',
     'def test_sync_templates_projects_every_template_and_is_idempotent(session):',
     None),
    (BE / 'tests/test_refdata_prescription.py',
     'def test_sync_templates_updates_a_changed_field_in_place(session):',
     'def test_sync_templates_updates_a_changed_field_in_place(session, monkeypatch):'),
    (BE / 'tests/db/test_models.py',
     'def test_all_sixteen_tables_created(session):',
     'def test_all_fifteen_tables_created(session):'),
    (BE / 'tests/db/test_models.py',
     'assert len(Base.metadata.tables) == 16',
     'assert len(Base.metadata.tables) == 15'),
    (BE / 'tests/db/test_models.py',
     '"prescription_template"}',
     '"stratification_result","daily_sync_run","cleaning_log","exercise"}'),
    (BE / 'tests/db/test_models.py',
     '现命中 **6** 处 = **3** 处真断言',
     '现命中 **7** 处'),
    (BE / 'tests/seed/test_generate.py',
     'REFERENCE_TABLES = ("exercise", "prescription_template")',
     'REFERENCE_TABLES = ("exercise",)'),
    (BE / 'tests/seed/test_generate.py',
     'assert REFERENCE_TABLES == ("exercise", "prescription_template"), REFERENCE_TABLES',
     'assert REFERENCE_TABLES == ("exercise",), REFERENCE_TABLES'),
    (ROOT / 'Document/2026-09-28-体育闭环原型-设计spec.md',
     '| **29** | **18 套模板的审校状态',
     None),
    (ROOT / 'Document/2026-09-28-体育闭环原型-设计spec.md',
     '| **31** | **红/黄层 × `speed_flexibility`',
     None),
    (ROOT / 'Document/2026-09-28-体育闭环原型-设计spec.md',
     '### ⚠️ 勘误（Plan 02 Task 3 落地 18 套模板时补',
     None),
]

bad = 0
for path, new, old in CASES:
    b = path.read_bytes()
    # ⚠️ 归一化后再串查：``backend/**`` 的工作树是 CRLF，而本脚本里的多行锚是用 ``\n`` 写的。
    # 不归一化会让**所有跨行的锚**假报 0 命中——本闸门第一次跑就有 3 条这么假红，
    # 那 3 条不是「磁盘未写」，是探针自己的缺陷（硬规矩 #61：查询本身要先被验证有效）。
    t = b.replace(b'\r\n', b'\n').decode('utf-8')
    n = t.count(new)
    o = t.count(old) if old else 0
    ok = (n >= 1) and (o == 0)
    if not ok:
        bad += 1
    print('%-4s %-52s 新串=%d 旧串=%d' % (
        'OK' if ok else 'FAIL', path.name, n, o))
print()
print('闸门判定: %s（%d 条不合格）' % ('PASS' if bad == 0 else 'FAIL', bad))

# 「0 命中」的结论要先用一个已知存在的串验证查询本身有效（硬规矩 #48 升级口径 ③）
sentinel = 'def test_prescription_public_namespace_is_pinned_verbatim():'
print('查询有效性对照: %r 在 test_refdata_prescription.py 里命中 %d 次（必须 >= 1）'
      % (sentinel[:40],
         (BE / 'tests/test_refdata_prescription.py').read_bytes()
         .replace(b'\r\n', b'\n').decode('utf-8').count(sentinel)))

# 缩进/空白敏感的抽查：repr 一行
tpl = (BE / 'app/domain/prescription/templates.py').read_bytes().decode('utf-8').split('\n')
for i, l in enumerate(tpl, 1):
    if l.startswith('    return not (layer is Layer.GREEN'):
        print('repr 抽查 templates.py:%d -> %r' % (i, l))
rp = (BE / 'app/refdata_prescription.py').read_bytes().decode('utf-8').split('\n')
for i, l in enumerate(rp, 1):
    if 'review_status = ReviewStatus(status)' in l:
        print('repr 抽查 refdata_prescription.py:%d -> %r' % (i, l))
print()
for rel in ('backend/app/domain/prescription/templates.py',
            'backend/app/refdata_prescription.py',
            'backend/data/prescription/RED-END-ABN-01.yaml'):
    b = (ROOT / rel).read_bytes()
    print('%-52s bytes=%6d CRLF=%4d sha16(norm)=%s'
          % (rel, len(b), b.count(b'\r\n'),
             hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()[:16].upper()))
