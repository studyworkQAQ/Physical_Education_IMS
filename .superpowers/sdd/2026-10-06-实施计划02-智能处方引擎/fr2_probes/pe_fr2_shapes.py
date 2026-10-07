# -*- coding: utf-8 -*-
"""核实 _dotted 的四种还原不出的形态，其 node.func 到底是什么 AST 节点。"""
import ast

SRCS = ['f()()', 'table[0]()', 'getattr(x, "now")()',
        '__import__("datetime").datetime.now()', '__import__("os").listdir(".")',
        'eval("...")', '_f("x")']


def shape(n):
    if isinstance(n, ast.Attribute):
        return "ast.Attribute(value=%s)" % shape(n.value)
    return "ast." + type(n).__name__


for s in SRCS:
    call = ast.parse(s).body[0].value
    print("%-40s node.func = %s" % (s, shape(call.func)))

print()
FORBIDDEN_IO = ("read_csv", "read_excel", "read_json", "read_parquet",
                "csv.reader", "csv.DictReader", ".read_text", ".read_bytes", "Path(",
                "import os", "os.listdir", "os.walk", "__file__",
                "json.load", "pickle.load")
for probe in ['__import__("os").listdir(".")', 'import os\nos.listdir(".")']:
    print("探针 %-36r 命中的 FORBIDDEN_IO 子串 = %s"
          % (probe, [t for t in FORBIDDEN_IO if t in probe]))
