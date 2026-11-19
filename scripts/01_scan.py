"""Step 1：扫描附近所有 Sphero 设备。

通过标准：输出中出现  BOLT  SB-8EE3  <地址>
"""
from common import BOLT_NAME
from spherov2 import scanner

print("扫描 10 秒……")
toys = scanner.find_toys(timeout=10)

if not toys:
    print("一个都没扫到：确认 BOLT 已唤醒、App 已关闭、电脑蓝牙已开启。")
for t in toys:
    mark = "  <== 就是它" if t.name == BOLT_NAME else ""
    print(f"{type(t).__name__:10s} {t.name:10s} {t.address}{mark}")
