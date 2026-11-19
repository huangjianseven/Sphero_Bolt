"""所有测试脚本共用的连接工具。

默认连接名为 SB-8EE3 的 BOLT。如需连接其他球，可以设置环境变量：
    Windows (PowerShell):  $env:BOLT_NAME="SB-XXXX"
    macOS / Linux:         export BOLT_NAME=SB-XXXX
"""
import os
import sys

try:
    from spherov2 import scanner
except ImportError:
    sys.exit("未安装 spherov2，请先运行：pip install -r requirements.txt")

BOLT_NAME = os.environ.get("BOLT_NAME", "SB-8EE3")


def find_bolt(timeout: float = 10.0):
    """扫描并返回目标 BOLT；找不到时给出排查提示并退出。"""
    print(f"正在扫描 {BOLT_NAME}（最多 {timeout:.0f} 秒）……")
    try:
        toy = scanner.find_toy(toy_name=BOLT_NAME, timeout=timeout)
    except scanner.ToyNotFoundError:
        sys.exit(
            f"没找到 {BOLT_NAME}。请检查：\n"
            "  1. BOLT 已唤醒（从充电座拿起或放回再拿起）\n"
            "  2. Sphero Edu App 已关闭或已断开\n"
            "  3. 电脑蓝牙已打开，球离电脑不超过 2 米\n"
            "  4. 先运行 01_scan.py 看看能扫到哪些设备"
        )
    print(f"找到：{toy.name}  地址：{toy.address}")
    return toy
