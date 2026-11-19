"""Step 4：运动控制。

⚠️ 把 BOLT 放在地上空旷处，远离桌边、楼梯。随时可按 Ctrl+C 停止。

运行前：让 BOLT 的蓝色后灯朝向你，这样 0° 就是"远离你"的方向。

通过标准：原地转一圈 → 向前滚 → 掉头滚回 → 走一个正方形。
"""
import time

from common import find_bolt
from spherov2.sphero_edu import SpheroEduAPI
from spherov2.types import Color

SPEED = 60          # 0-255，第一次测试保持低速
toy = find_bolt()

with SpheroEduAPI(toy) as api:
    try:
        api.set_main_led(Color(0, 255, 0))
        print("原地转一圈")
        api.spin(360, 1)
        time.sleep(0.5)

        print("向前滚 1.5 秒")
        api.roll(0, SPEED, 1.5)
        time.sleep(0.5)

        print("掉头滚回")
        api.roll(180, SPEED, 1.5)
        time.sleep(0.5)

        print("走正方形")
        for heading in (0, 90, 180, 270):
            api.roll(heading, SPEED, 1)
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\n中断")
    finally:
        api.stop_roll()
        api.set_main_led(Color(0, 0, 0))

print("已停车并断开")
