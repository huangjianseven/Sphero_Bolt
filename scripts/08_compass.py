"""Step 8：罗盘（磁力计）校准，然后让 BOLT 依次转向 北 → 东 → 南 → 西。

为什么之前罗盘是 None：
    spherov2 的 get_compass_direction() 返回的是"校准后得到的北方角度"，
    不是实时罗盘读数。没有校准过，它就一直是 None。

校准时 BOLT 会原地转圈寻找北方：
    ⚠️ 放在地上，远离金属桌腿、电脑、音箱、磁铁等（会干扰磁力计）。
    官方建议：如果效果不好，可以把 BOLT 拿在手里校准。

通过标准：打印出北方角度（0–359），BOLT 依次朝向 N / E / S / W，点阵显示对应字母。
"""
import threading
import time

from common import find_bolt
from spherov2.sphero_edu import SpheroEduAPI
from spherov2.types import Color

CALIBRATE_TIMEOUT = 30   # 秒；spherov2 的 calibrate_compass() 自身没有超时，这里加一层
CYAN = Color(0, 200, 255)
DIRECTIONS = [("N", 0), ("E", 90), ("S", 180), ("W", 270)]


def calibrate_with_timeout(api, timeout):
    """在后台线程里校准，超时返回 False。"""
    done = threading.Event()

    def run():
        try:
            api.calibrate_compass()
        finally:
            done.set()

    threading.Thread(target=run, daemon=True).start()
    return done.wait(timeout)


toy = find_bolt()
with SpheroEduAPI(toy) as api:
    print("校准前罗盘值：", api.get_compass_direction())

    print(f"开始校准（最多 {CALIBRATE_TIMEOUT} 秒），BOLT 会原地转圈……")
    api.set_main_led(Color(255, 120, 0))
    ok = calibrate_with_timeout(api, CALIBRATE_TIMEOUT)
    north = api.get_compass_direction()

    if not ok or north is None:
        api.set_main_led(Color(255, 0, 0))
        time.sleep(1)
        raise SystemExit(
            "校准超时或没有拿到结果。可以试试：\n"
            "  1. 远离金属和电子设备后重试\n"
            "  2. 把 BOLT 拿在手里、保持水平再运行一次\n"
            "  3. 用 Sphero Edu App 的 Auto-Aim 校准一次，确认硬件正常"
        )

    print(f"校准完成：北方 = {north}°（相对于当前 0° 方向）")
    api.set_main_led(Color(0, 255, 0))
    time.sleep(1)

    # 依次朝向四个方向（速度保持 0，只原地转身）
    for letter, offset in DIRECTIONS:
        heading = int(north + offset) % 360
        print(f"朝向 {letter}：heading = {heading}°")
        api.set_heading(heading)
        api.set_matrix_character(letter, CYAN)
        time.sleep(2.5)

    # 最后指向北方
    api.set_heading(int(north) % 360)
    api.set_matrix_character("N", CYAN)
    print("现在指向北方。后续可以用 heading = 北方角度 + 偏移 来按地理方向行驶。")
    time.sleep(2)
    api.clear_matrix()

print("完成，已断开")
