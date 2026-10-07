"""P4 — Minor 5：daily.py:226/:228 两个「均值」是不是截断值。"""
base = (20.48, 20.85)
after = (20.89, 21.18)
mb = (base[0] + base[1]) / 2
ma = (after[0] + after[1]) / 2

print("=== 基线（daily.py:226）===")
print(" 样本            = %r" % (base,))
print(" 求和            = %r" % (base[0] + base[1],))
print(" 真均值          = %r" % mb)
print(" round(mb, 2)    = %r" % round(mb, 2))
print(" 截断 int(*100)/100 = %r" % (int(mb * 100) / 100))
print(" '%%.2f' 格式化   = %r" % ("%.2f" % mb))
print(" 源码印的值      = 20.66")
print(" 源码值 == round()? %s ; == 截断? %s ; == %%.2f? %s"
      % (20.66 == round(mb, 2), 20.66 == int(mb * 100) / 100,
         "20.66" == "%.2f" % mb))
print(" 组内极差        = %r" % (base[1] - base[0],))

print()
print("=== 本 Task 之后（daily.py:228）===")
print(" 样本            = %r" % (after,))
print(" 求和            = %r" % (after[0] + after[1],))
print(" 真均值          = %r" % ma)
print(" round(ma, 2)    = %r" % round(ma, 2))
print(" 截断 int(*100)/100 = %r" % (int(ma * 100) / 100))
print(" '%%.2f' 格式化   = %r" % ("%.2f" % ma))
print(" 源码印的值      = 21.03")
print(" 源码值 == round()? %s ; == 截断? %s ; == %%.2f? %s"
      % (21.03 == round(ma, 2), 21.03 == int(ma * 100) / 100,
         "21.03" == "%.2f" % ma))
print(" 组内极差        = %r" % (after[1] - after[0],))

print()
print("=== 同行其余三个数（派单说评审者核过自洽，我再核一遍）===")
d = ma - mb
print(" 差 ma - mb      = %r -> 源码印 +0.37 s ; round(d,2)==0.37? %s" % (d, round(d, 2) == 0.37))
pct = d / mb * 100
print(" 百分比 d/mb*100 = %r -> 源码印 +1.8%% ; round(pct,1)==1.8? %s" % (pct, round(pct, 1) == 1.8))
r = 60 / 21.18
print(" 60/21.18        = %r -> 源码印 2.83x ; round(r,2)==2.83? %s" % (r, round(r, 2) == 2.83))

print()
print("=== 派单那句「21.035 的 round() 是 21.04」===")
print(" round(21.035, 2)          = %r" % round(21.035, 2))
print(" 但 ma 的真值是 %r（float）; ma == 21.035 ? %s" % (ma, ma == 21.035))
print(" 21.035.hex() = %s ; ma.hex() = %s" % ((21.035).hex(), ma.hex()))
print(" round(20.665, 2) = %r" % round(20.665, 2))
print(" mb.hex() = %s ; 20.665.hex() = %s" % (mb.hex(), (20.665).hex()))
