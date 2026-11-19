"""Step 5：读取传感器（姿态、加速度、陀螺仪、罗盘、光照）。

试试：用手转动、摇晃、遮住 BOLT，看读数变化。按 Ctrl+C 结束。
"""
import time

from common import find_bolt
from spherov2.sphero_edu import SpheroEduAPI


def fmt(d):
    if not d:
        return "—"
    return " ".join(f"{k}={v:7.1f}" for k, v in d.items())


toy = find_bolt()
with SpheroEduAPI(toy) as api:
    print("每 0.5 秒刷新一次，Ctrl+C 结束\n")
    try:
        while True:
            print("姿态  ", fmt(api.get_orientation()))
            print("加速度", fmt(api.get_acceleration()))
            print("陀螺仪", fmt(api.get_gyroscope()))
            print("罗盘  ", api.get_compass_direction())
            print("光照  ", api.get_luminosity())
            print("-" * 50)
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass

print("结束")
