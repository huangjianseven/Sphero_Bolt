"""Step 6：键盘遥控 —— 真正"取得控制权"。

按键：
    ↑ / ↓     加速 / 减速；速度为 0 时按 ↓ → 原地调转 180°，速度保持 0
    ← / →     左转 / 右转 15°
    空格      急停
    A         对准模式：后灯亮，←/→ 只转方向不前进，再按 A 设为新的 0°
    Esc       退出

⚠️ 在地上空旷处使用。macOS 需要在"隐私与安全性 → 辅助功能 / 输入监控"中给终端授权。
"""
import threading
import time

from common import find_bolt
from spherov2.sphero_edu import SpheroEduAPI
from spherov2.types import Color

try:
    from pynput import keyboard
except ImportError:
    raise SystemExit("缺少 pynput，请运行：pip install pynput")

MAX_SPEED = 150
SPEED_STEP = 30
TURN_STEP = 15


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.heading = 0
        self.speed = 0
        self.aiming = False
        self.aim_done = False
        self.quit = False


s = State()


def on_press(key):
    with s.lock:
        if key == keyboard.Key.up and not s.aiming:
            s.speed = min(MAX_SPEED, s.speed + SPEED_STEP)
        elif key == keyboard.Key.down and not s.aiming:
            if s.speed == 0:
                # 已停稳时按 ↓：原地调转 180°，速度保持 0（再按 ↑ 起步）
                s.heading = (s.heading + 180) % 360
            else:
                s.speed = max(0, s.speed - SPEED_STEP)
        elif key == keyboard.Key.left:
            s.heading = (s.heading - TURN_STEP) % 360
        elif key == keyboard.Key.right:
            s.heading = (s.heading + TURN_STEP) % 360
        elif key == keyboard.Key.space:
            s.speed = 0
        elif key == keyboard.Key.esc:
            s.quit = True
            return False
        elif getattr(key, "char", None) in ("a", "A"):
            if s.aiming:
                s.aim_done = True
            s.aiming = not s.aiming
            s.speed = 0


toy = find_bolt()
with SpheroEduAPI(toy) as api:
    api.set_main_led(Color(0, 80, 255))
    print(__doc__)
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    last = None
    try:
        while True:
            with s.lock:
                heading, speed, aiming, quit_ = s.heading, s.speed, s.aiming, s.quit
                aim_done, s.aim_done = s.aim_done, False
            if quit_:
                break

            if aim_done:
                api.reset_aim()            # 当前朝向设为新的 0°
                with s.lock:
                    s.heading = 0
                heading = 0
                api.set_back_led(Color(0, 0, 0))
                api.set_main_led(Color(0, 80, 255))
                print("\n已重新对准")

            if aiming:
                api.set_back_led(Color(0, 0, 255))
                api.set_main_led(Color(0, 0, 0))

            cur = (heading, speed, aiming)
            if cur != last:
                api.set_heading(heading)
                api.set_speed(speed)
                mode = "对准" if aiming else "驾驶"
                print(f"\r[{mode}] 方向 {heading:3d}°  速度 {speed:3d}   ", end="", flush=True)
                last = cur
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        api.stop_roll()
        api.set_main_led(Color(0, 0, 0))
        listener.stop()

print("\n已停车并断开")
