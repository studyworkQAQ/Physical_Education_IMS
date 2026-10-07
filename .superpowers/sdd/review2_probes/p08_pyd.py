import importlib, sys, os
names = [
 "sqlalchemy.util._collections_cy",
 "sqlalchemy.util._immutabledict_cy",
 "sqlalchemy.engine._processors_cy",
 "sqlalchemy.engine._result_cy",
 "sqlalchemy.engine._row_cy",
 "sqlalchemy.engine._util_cy",
 "sqlalchemy.sql._util_cy",
 "sqlalchemy.sql._cache_key_cy",
]
for n in names:
    try:
        importlib.import_module(n); print("OK   ", n)
    except BaseException as e:
        print("FAIL ", n, "->", str(e)[:90])
print()
print("sys.path:", sys.path)
print()
import subprocess
r = subprocess.run([sys.executable,"-m","pip","show","sqlalchemy"],capture_output=True)
print(r.stdout.decode("utf-8","replace")[:800])
print(r.stderr.decode("utf-8","replace")[:300])
