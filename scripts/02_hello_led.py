"""Step 2：连接并点亮 LED（Hello World）。

通过标准：点阵变蓝 → 前灯绿、后灯红 → 点阵依次红/绿/蓝闪烁。
"""
import time

from common import find_bolt
from spherov2.sphero_edu import SpheroEduAPI
from spherov2.types import Color

toy = find_bolt()
with SpheroEduAPI(toy) as api:
    print("已连接，点阵变蓝")
    api.set_main_led(Color(r=0, g=0, b=255))
    time.sleep(2)

    print("前灯绿，后灯红")
    api.set_front_led(Color(r=0, g=255, b=0))
    api.set_back_led(Color(r=255, g=0, b=0))
    time.sleep(2)

    print("红 / 绿 / 蓝 轮换")
    for c in (Color(255, 0, 0), Color(0, 255, 0), Color(0, 0, 255)) * 2:
        api.set_main_led(c)
        time.sleep(0.5)

print("完成，已断开")
