import inspect
from coverage.results import Numbers
print("signature:", inspect.signature(Numbers.__init__))
n = Numbers(n_files=1, n_statements=441, n_excluded=0, n_missing=2,
            n_branches=120, n_partial_branches=0, n_missing_branches=0)
print("pc_covered      =", n.pc_covered)
print("pc_covered_str  =", n.pc_covered_str)
print("pc_str_covered  =", getattr(n, "pc_str_covered", "n/a"))
n2 = Numbers(n_files=1, n_statements=441, n_excluded=0, n_missing=0,
             n_branches=120, n_partial_branches=0, n_missing_branches=0)
print("baseline (Miss 0) pc_covered =", n2.pc_covered, " str =", n2.pc_covered_str)
n3 = Numbers(n_files=1, n_statements=42, n_excluded=0, n_missing=9,
             n_branches=6, n_partial_branches=0, n_missing_branches=6)
print("my MB4 scoped TOTAL 42/9/6 (BrPart0, missing-branch 6) ->", n3.pc_covered, n3.pc_covered_str)
