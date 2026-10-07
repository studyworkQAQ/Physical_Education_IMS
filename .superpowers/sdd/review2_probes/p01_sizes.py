import hashlib, os
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
FILES = [
 r"backend\app\refdata_prescription.py",
 r"backend\app\domain\prescription\__init__.py",
 r"backend\app\domain\prescription\templates.py",
 r"backend\app\domain\prescription\exercises.py",
 r"backend\app\db\models\prescription.py",
 r"backend\app\db\models\__init__.py",
 r"backend\app\db\models\_shared.py",
 r"backend\app\db\session.py",
 r"backend\app\refdata.py",
 r"backend\data\exercises.yaml",
 r"backend\data\exercise_equivalence.yaml",
 r"backend\tests\test_refdata_prescription.py",
 r"backend\tests\domain\test_prescription_templates.py",
 r"backend\tests\architecture\test_domain_purity.py",
 r"backend\tests\architecture\test_layering.py",
 r"backend\tests\db\test_models.py",
 r"backend\tests\seed\test_generate.py",
 r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-review-package.md",
 r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\progress.md",
 r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-report.md",
 r".superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-2-brief.md",
 r"Document\2026-09-28-体育闭环原型-设计spec.md",
 r"Document\2026-10-06-实施计划02-智能处方引擎.md",
]
print(f"{'path':<80}{'bytes':>9}{'lines(lf)':>11}{'crlf':>7}{'bare_lf':>9}  sha256[:16]")
for f in FILES:
    p = os.path.join(ROOT, f)
    if not os.path.exists(p):
        print(f"{f:<80} MISSING")
        continue
    b = open(p,'rb').read()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n")
    print(f"{f:<80}{len(b):>9}{lf:>11}{crlf:>7}{lf-crlf:>9}  {hashlib.sha256(b).hexdigest()[:16]}")
