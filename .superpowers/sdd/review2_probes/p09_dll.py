import os, glob, shutil, tempfile, importlib.util, time, sys
sp = r"C:\Python\Lib\site-packages\sqlalchemy"
print("=== mtimes of sqlalchemy pyd ===")
for p in sorted(glob.glob(os.path.join(sp,"**","*.pyd"), recursive=True)):
    st = os.stat(p)
    print("  %-60s %10d  %s" % (os.path.relpath(p, sp), st.st_size, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))))
src = os.path.join(sp,"sql","_cache_key_cy.cp311-win_amd64.pyd")
tmp = os.path.join(tempfile.gettempdir(), "rv2_ck")
os.makedirs(tmp, exist_ok=True)
dst = os.path.join(tmp, "_cache_key_cy.cp311-win_amd64.pyd")
shutil.copy2(src, dst)
print("\ncopied to", dst, os.path.getsize(dst))
try:
    spec = importlib.util.spec_from_file_location("ck_probe", dst)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    print("LOAD FROM TEMP: OK ->", m)
except BaseException as e:
    print("LOAD FROM TEMP: FAIL ->", type(e).__name__, str(e)[:160])
