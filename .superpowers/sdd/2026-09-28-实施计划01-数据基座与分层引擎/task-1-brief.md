### Task 1: 后端脚手架与 domain 层纯净性约束

**Files:**
- Create: `.gitignore`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`、`backend/app/domain/__init__.py`、`backend/app/adapters/__init__.py`、`backend/app/pipeline/__init__.py`、`backend/app/db/__init__.py`、`backend/app/seed/__init__.py`
- Test: `backend/tests/architecture/test_domain_purity.py`

**Interfaces:**
- Consumes: 无
- Produces: 可运行的 `pytest`；`app.domain` / `app.adapters` / `app.pipeline` / `app.db` / `app.seed` 五个包

- [ ] **Step 1: 写失败测试 — domain 层纯净性架构约束**

```python
# backend/tests/architecture/test_domain_purity.py
import ast, pathlib

DOMAIN = pathlib.Path(__file__).parents[2] / "app" / "domain"
FORBIDDEN = {"sqlalchemy", "fastapi", "requests", "httpx", "pydantic_settings"}
FORBIDDEN_CALLS = {"datetime.now", "datetime.today", "open"}

def test_domain_has_no_forbidden_imports():
    offenders = []
    for py in DOMAIN.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module.split(".")[0]]
            offenders += [f"{py.name}:{m}" for m in mods if m in FORBIDDEN]
    assert offenders == []

def test_domain_has_no_clock_or_file_access():
    offenders = []
    for py in DOMAIN.rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        offenders += [f"{py.name}:{c}" for c in FORBIDDEN_CALLS if c in src]
    assert offenders == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/architecture -v`
Expected: FAIL — 收集错误，`app/domain` 目录不存在

- [ ] **Step 3: 创建 `.gitignore`（仓库根）**

必须包含：`.venv/`、`__pycache__/`、`*.py[cod]`、`*.egg-info/`、`.pytest_cache/`、`.coverage`、`.superpowers/`、`backend/pe.db`、`backend/pe.db-journal`、`backend/pe.db-wal`、`backend/pe.db-shm`、`backend/data/seed/`（生成的仿真 CSV，可由 `--seed` 复现，不入库）、`node_modules/`、`frontend/dist/`、`.DS_Store`、`Thumbs.db`、`.env`

**不得忽略** `backend/data/national_standard_2014.csv`、`national_norm.csv`、`indicator_ranges.yaml`、`exercise_equivalence.yaml`、`alert_rules.yaml` —— 这些是专家维护的知识资产，必须进版本控制。因此忽略规则须写成 `backend/data/seed/` 而非 `backend/data/`。

- [ ] **Step 4: 创建 `backend/pyproject.toml`**

`[project]` 需 `requires-python = ">=3.11"`，`dependencies` = `fastapi`、`uvicorn[standard]`、`sqlalchemy>=2.0`、`pandas`、`numpy`、`pyyaml`。`[project.optional-dependencies] dev` = `pytest`、`pytest-cov`、`httpx`。`[tool.pytest.ini_options]` 设 `testpaths = ["tests"]`、`pythonpath = ["."]`。

- [ ] **Step 5: 创建五个包的 `__init__.py`**

`app/domain/__init__.py`、`app/adapters/__init__.py`、`app/pipeline/__init__.py`、`app/db/__init__.py`、`app/seed/__init__.py` 与 `app/__init__.py` 均建为空文件。`tests/` 及其子目录**不放** `__init__.py`，也**不建** `conftest.py`——`pyproject.toml` 的 `pythonpath = ["."]` 已让 pytest 能 import `app.*`，本计划没有任何跨测试文件共享的 fixture（各 Task 的夹具都在自己的测试文件内定义）。

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && pip install -e ".[dev]" && pytest tests/architecture -v`
Expected: PASS，2 passed

- [ ] **Step 7: Commit**

```bash
git add .gitignore backend/
git commit -m "chore: 搭建后端脚手架并加入 domain 层纯净性架构测试"
```

---

