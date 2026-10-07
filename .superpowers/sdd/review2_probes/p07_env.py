import importlib, sys, os, glob
mods = ["yaml","numpy","pytest","_yaml","sqlalchemy","sqlalchemy.sql._cache_key_cy","pandas"]
for m in mods:
    try:
        importlib.import_module(m)
        print("OK   ", m)
    except BaseException as e:
        print("FAIL ", m, "->", type(e).__name__, str(e)[:120])
print()
sp = r"C:\Python\Lib\site-packages"
print("sqlalchemy pyd files:")
for p in glob.glob(os.path.join(sp,"sqlalchemy","**","*.pyd"), recursive=True):
    print("  ", os.path.relpath(p, sp), os.path.getsize(p))
print()
print("cache_key.py head:")
L = open(os.path.join(sp,"sqlalchemy","sql","cache_key.py"),'rb').read().decode("utf-8","replace").split("\n")
for i,s in enumerate(L[:45],1):
    print(f"{i:>4}|{s}")
