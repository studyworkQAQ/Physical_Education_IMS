import os, sys
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
rel = sys.argv[1]; a = int(sys.argv[2]); b = int(sys.argv[3])
raw = open(os.path.join(ROOT, rel),'rb').read()
L = raw.replace(b"\r\n", b"\n").decode("utf-8").split("\n")
print(f"--- {rel}  bytes={len(raw)} total_lines={len(L)}  showing {a}..{b} ---")
for i in range(a, min(b, len(L))+1):
    print(f"{i:>5}|{L[i-1]}")
