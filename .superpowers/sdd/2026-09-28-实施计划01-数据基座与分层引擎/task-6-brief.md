### Task 6: 仿真数据生成器 — 人口学、体测与体成分

**Files:**
- Create: `backend/app/seed/config.py`、`backend/app/seed/population.py`、`backend/app/seed/sections.py`、`backend/app/seed/fitness.py`、`backend/app/seed/body_comp.py`、`backend/app/seed/survey.py`、`backend/app/seed/generate.py`
- Test: `backend/tests/seed/test_generate.py`

**Interfaces:**
- Consumes: Task 2 `raw_from_score`、`ScoredItem`、`Sex`、`age_group_of`
- Produces:
  - `@dataclass SeedConfig`: `students: int = 500`、`weeks: int = 16`、`seed: int = 20250828`、`male_ratio: float = 0.55`、`target_layer_dist: dict[str, float] = {"red": .20, "yellow": .45, "green": .35}`、`teachers: int = 3`、`sections_per_teacher: int = 2`、`section_size: tuple[int, int] = (30, 38)`、`dirty: dict[str, float]`（`missing`/`outlier`/`unit_error`/`duplicate` 比例）
  - `make_population(cfg: SeedConfig, rng: np.random.Generator) -> list[dict]`
  - `make_sections(population: list[dict], cfg: SeedConfig, rng) -> dict[str, list[dict]]` — 返回 `{"course_sections": […], "enrollments": […]}`；同一批学生生成**两套编班**：12 个 `administrative` 行政班（阶段一）+ 3 个 `stratified` 分层班（阶段二：提升班/强化班/拓展班），spec §10.3
  - `latent_profiles(population: list[dict], cfg: SeedConfig, rng) -> dict[int, dict[str, float]]` — 返回 `{student_id: {"fitness":…, "endurance":…, "strength":…, "speedflex":…}}`
  - `make_fitness_tests(population, latents, cfg, rng) -> list[dict]` — 含**两学年**、`week1`/`week8`/`week16` 三时点
  - `make_body_comp(population, latents, cfg, rng) -> list[dict]`
  - `make_survey(population, latents, cfg, rng) -> list[dict]` — 占位 5 维度 × 5 点李克特（spec §10.9）
  - `inject_dirty(records: list[dict], cfg: SeedConfig, rng) -> list[dict]`
  - `build_dataset(cfg: SeedConfig) -> dict[str, list[dict]]` — 键为 `population`/`course_sections`/`enrollments`/`fitness`/`body_comp`/`survey`/`dirty_marks`
  - `write_csv(ds: dict[str, list[dict]], out_dir: pathlib.Path) -> None` — 供 `MockLePaoAdapter` 读取
  - `seed_database(session, cfg: SeedConfig) -> None` — 只写**组织结构**（semester/teacher/student/course_section/enrollment）；体测/体成分/问卷须经适配器与管道流入，不得直接入库，否则绕过清洗与幂等
  - CLI：`python -m app.seed.generate --students 500 --weeks 16 --seed 20250828 [--out-csv DIR]`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/seed/test_generate.py
import numpy as np
from app.seed.config import SeedConfig
from app.seed.population import make_population
from app.seed.fitness import latent_profiles, make_fitness_tests
from app.seed.body_comp import make_body_comp
from app.seed.generate import build_dataset, write_csv

CFG = SeedConfig(students=500, weeks=16, seed=20250828)

def test_population_size_and_sex_ratio():
    pop = make_population(CFG, np.random.default_rng(CFG.seed))
    assert len(pop) == 500
    males = sum(1 for p in pop if p["sex"] == "male")
    assert abs(males / 500 - 0.55) < 0.05
    assert all(18 <= p["age"] <= 22 for p in pop)

def test_same_seed_produces_identical_dataset():
    a = build_dataset(CFG)
    b = build_dataset(CFG)
    assert a == b          # 字节级一致：可复现是研究项目硬要求

def test_different_seed_produces_different_dataset():
    assert build_dataset(CFG) != build_dataset(SeedConfig(**{**CFG.__dict__, "seed": 1}))

def test_two_academic_years_present():
    ds = build_dataset(CFG)
    years = {r["academic_year"] for r in ds["fitness"]}
    assert len(years) >= 2      # 趋势判定需要连续两次体测

def test_three_timepoints_present():
    ds = build_dataset(CFG)
    cur = max(r["academic_year"] for r in ds["fitness"])
    tps = {r["timepoint"] for r in ds["fitness"] if r["academic_year"] == cur}
    assert tps == {"week1", "week8", "week16"}

def test_body_fat_abnormal_rate_in_expected_band():
    ds = build_dataset(CFG)
    pop = {p["student_id"]: p for p in ds["population"]}
    abnormal = sum(1 for r in ds["body_comp"]
        if r["body_fat_pct"] > (20 if pop[r["student_id"]]["sex"] == "male" else 28))
    rate = abnormal / len(ds["body_comp"])
    assert 0.20 <= rate <= 0.50

def test_dirty_data_injected():
    ds = build_dataset(CFG)
    kinds = {e["kind"] for e in ds["dirty_marks"]}
    assert {"missing", "outlier", "unit_error", "duplicate"} <= kinds

def test_two_grouping_modes_coexist():
    # spec §10.3：阶段一行政班 + 阶段二分层班，同一批学生两套编班
    ds = build_dataset(CFG)
    modes = {s["grouping_mode"] for s in ds["course_sections"]}
    assert modes == {"administrative", "stratified"}
    admin = [s for s in ds["course_sections"] if s["grouping_mode"] == "administrative"]
    strat = [s for s in ds["course_sections"] if s["grouping_mode"] == "stratified"]
    assert len(admin) == 12 and len(strat) == 3
    assert {s["name"] for s in strat} == {"提升班", "强化班", "拓展班"}

def test_administrative_section_size_within_bounds():
    ds = build_dataset(CFG)
    admin_ids = {s["section_id"] for s in ds["course_sections"]
                 if s["grouping_mode"] == "administrative"}
    from collections import Counter
    sizes = Counter(e["section_id"] for e in ds["enrollments"]
                    if e["section_id"] in admin_ids)
    assert sizes and all(30 <= n <= 38 for n in sizes.values())

def test_every_student_enrolled_in_both_grouping_modes():
    ds = build_dataset(CFG)
    ids = {p["student_id"] for p in ds["population"]}
    admin_ids = {s["section_id"] for s in ds["course_sections"]
                 if s["grouping_mode"] == "administrative"}
    strat_ids = {s["section_id"] for s in ds["course_sections"]
                 if s["grouping_mode"] == "stratified"}
    in_admin = {e["student_id"] for e in ds["enrollments"] if e["section_id"] in admin_ids}
    in_strat = {e["student_id"] for e in ds["enrollments"] if e["section_id"] in strat_ids}
    assert in_admin == ids and in_strat == ids

def test_survey_has_five_dimensions_on_five_point_scale():
    # spec §10.9 占位量表
    ds = build_dataset(CFG)
    assert ds["survey"]
    for r in ds["survey"]:
        assert len(r["dimensions"]) == 5
        assert all(1 <= v <= 5 for v in r["dimensions"].values())

def test_write_csv_roundtrips_through_adapter(tmp_path):
    from app.adapters.mock_lepao import MockLePaoAdapter
    ds = build_dataset(SeedConfig(students=40, weeks=16, seed=20250828))
    write_csv(ds, tmp_path)
    ad = MockLePaoAdapter(tmp_path)
    assert len(list(ad.fetch_fitness(None))) > 0
    assert len(list(ad.fetch_body_comp(None))) > 0
    assert len(list(ad.fetch_survey(None))) > 0

def test_indicator_correlation_is_realistic():
    # 潜变量驱动的核心断言：耐力与力量得分应正相关，而非独立随机
    ds = build_dataset(CFG)
    w1 = [r for r in ds["fitness"] if r["timepoint"] == "week1"
          and r["academic_year"] == max(x["academic_year"] for x in ds["fitness"])]
    end = np.array([r["score_endurance_mean"] for r in w1])
    str_ = np.array([r["score_strength_mean"] for r in w1])
    assert np.corrcoef(end, str_)[0, 1] > 0.4
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/seed -v`
Expected: FAIL — `ModuleNotFoundError: app.seed.config`

- [ ] **Step 3: 实现潜变量模型（spec §10.2）**

```text
latent_fitness    ~ N(0, 1)
latent_endurance  = 0.8·latent_fitness + N(0, 0.6)
latent_strength   = 0.7·latent_fitness + N(0, 0.7)
latent_speedflex  = 0.6·latent_fitness + N(0, 0.8)

6 个短板判定项得分 = clip(70 + 15·latent_所属桶 + N(0, 5), 0, 100)
BMI 得分           = 由身高体重分布独立生成后正查评分表
各项原始值         = raw_from_score(得分, 性别, 龄组)
```

`latent_fitness` 的 μ/σ 由 `target_layer_dist` 反推：用二分法调 μ 使生成人群的红/黄/绿比例逼近目标。**该分布断言在 Task 9 落地**（需要分层引擎才能算），本 Task 只保证潜变量与得分生成正确。

- [ ] **Step 4: 实现两学年与三时点**

上学年得分 = 本学年得分 − 趋势项。趋势项按四类比例注入：`持续下滑 20%`、`波动大 15%`、`稳步提升 25%`、`稳定 40%`（写入 `SeedConfig`，可调）。本学年 `week8`/`week16` 相对 `week1` 按实验班/对照班差异化演进——**该差异逻辑属 Plan 03**，本 Task 只做小幅随机漂移并预留 `intervention_effect` 参数位。

- [ ] **Step 5: 实现 `sections.py` 编班（spec §10.3）**

`teachers × sections_per_teacher` 决定阶段一参与的行政班数（默认 3 × 2 = 6 个由任课教师带），另生成 12 个 `administrative` 行政班容纳全部 500 人，每班 30–38 人。阶段二另建 3 个 `stratified` 分层班（提升班/强化班/拓展班），**同一批学生全员二次编入**。注意 `stratified` 编班在本计划中按 `latent_fitness` 三分位近似分配即可——真实的按分层结果编班依赖 Task 9 输出，属计划 04 的阶段二功能。

- [ ] **Step 6: 实现 `survey.py`、`inject_dirty`、`write_csv`、`seed_database` 与 CLI**

`survey.py`：5 维度（运动乐趣、运动能力自信、健康认知、同伴互动、教师评价）× 5 点李克特，总分与 `latent_fitness` 弱正相关（相关系数约 0.3）。

`inject_dirty`：按 `cfg.dirty` 比例注入四类脏数据（spec §10.7：缺失 3–5%、异常值 0.5%、量纲错误 0.3%、重复 1%），每处注入记一条 `dirty_marks` 供 Task 5 清洗测试交叉验证。

**`duplicate` 注入必须是逐字复制整行（Ruling 52）**：不得改动被复制行的任何字段，尤其不得让两条同 `(student_no, batch_key)` 的行带**不同的 `tested_on`**。理由：Task 5 的体测去重键不含 `tested_on`，「保留后者」按**输入顺序**判定而非按日期；若两行日期不同，胜出的可能是较早的测量，而 `reason` 只能如实记录两个日期、无法声称「取最新」。逐字复制使这一歧义在原型数据里根本不出现。

**注入范围按数据源区分（Ruling 34）**：`missing` / `outlier` / `unit_error` **只注入 `fitness` 与 `body_comp`**；`survey` 只允许注入 `duplicate`（同一 `student_no` + `filled_on` 两行）。
理由：适配器契约声明的是 `total: float`、`dimensions: dict[str, float]`，**没有 `None` 的位置**；空白问卷单元格会让 `MockLePaoAdapter` 抛 `ValueError` 并在 Task 10 的抽取阶段中断整条管道。而放宽适配器（返回 `None`）违反契约，兜底成 `0.0` / `{}` 则会凭空造出「对体育毫无兴趣」的学生——那正是 Ruling 21 禁止的静默捏造。所以**适配器保持严格是对的，约束落在生产方**。第一批不需要 `clean_survey`：问卷无数值清洗需求，重复由 Ruling 24 的 `uq_interest_survey_student_semester_filled_on` + `repo.upsert` 兜住。待 spec §14 #15 的真实量表到位、且问卷进入 Plan 03/04 的分析路径时再评估是否需要。

**注入列白名单（Ruling 44，承重）**：`missing` / `outlier` / `unit_error` 三类**只允许作用于测量列**，即 `height_cm`、`weight_kg`、`vital_capacity_ml`、`sprint_50m_s`、`sit_and_reach_cm`、`standing_jump_cm`、`strength_count`、`distance_run_s`、`muscle_mass_kg`、`body_fat_pct`、`smi`。**严禁作用于任何日期列**（`tested_on`、`measured_on`、`filled_on`）与标识列（`student_no`、`batch_key`）。

理由：Ruling 41 已让适配器**无条件**校验并归一化记录侧日期，空日期会在抽取阶段抛 `ValueError`。若 `inject_dirty` 随机挑列置空而挑中 `tested_on`，一次本该被记进 `cleaning_log` 的「缺失」就会**升级成整条日批处理中断**——spec §11.1 的原则是数据质量问题「不抛异常、不中断批次」，而日期缺失属于结构性无法安放（Ruling 43），两者不可混淆。因此白名单必须写死在生成器里，并由一条测试钉住：**注入后 `dirty_marks` 里不得出现任何日期列或标识列**。

`write_csv`：把 `fitness`/`body_comp`/`survey` **三类**写成 `MockLePaoAdapter` 约定的 CSV。

- **`students.csv` 在 Plan 01 有意不产出（Ruling 37）**：`fetch_students` 在第一批只属于契约、不被任何管道阶段消费，组织结构由 `seed_database` 建立。`MockLePaoAdapter` 对缺失文件 yield 空，`test_missing_file_yields_empty_for_every_source` 已钉住该行为，故不写它不会崩。Task 6 的 brief 须明写这一点，避免实现者以为漏了。
- 文件名与列序**从 `app/adapters/base.py` 导入契约常量**，不得从 `mock_lepao.py` 导入、也不得在 Task 6 里手抄第二份（Ruling 36 已把 8 个契约常量移到 `base.py`，正是为了让生产方依赖契约模块而非某个实现）。
- `batch_key` 一律用 `base.make_batch_key(academic_year, timepoint)` 构造，**不得手拼字符串**（Ruling 35：格式只能有一个所有者，读写两侧都成立）。
- 日期列一律写零填充的 `YYYY-MM-DD`，**不得带时间部分**（Ruling 38：`since` 是排他的 ISO 日期过滤，带 `T` 后缀会让恰等于水位线的记录被永久重复抽取）。
- JSON 列序列化一律用 `json.dumps(..., ensure_ascii=False, allow_nan=False)`。**`allow_nan=False` 是承重的**：`json.dumps` 缺省 `allow_nan=True` 会写出非标准字面量 `NaN`，而 `json.loads` 缺省又接受它，于是一个 NaN 能原样写盘、原样读回、全程零报错，最后在与任何阈值比较时恒为假（Ruling 39 的生产方一侧；消费方一侧由 `mock_lepao` 的 `isfinite` 检查兜住）。

`seed_database`：**只写组织结构**（semester/teacher/student/course_section/enrollment）。体测/体成分/问卷必须经适配器与管道流入，不得直接入库——否则绕过了清洗与幂等，管道就测不到真实路径。

CLI 缺省行为（无 `--out-csv` 时）：调用 `seed_database` 把组织结构写入 `backend/pe.db`，同时把三类 CSV 写入 `backend/data/seed/`，并在控制台打印人数、男女比、两学年体测条数与脏数据注入计数摘要。`--out-csv DIR` 仅改 CSV 输出路径，不改入库行为。

- [ ] **Step 7: 运行测试确认通过**

Run: `cd backend && pytest tests/seed -v`
Expected: PASS，13 passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/seed/ backend/tests/seed/
git commit -m "feat: 潜变量驱动的高保真仿真数据生成器，含两套编班、占位量表与四类脏数据注入"
```

---

