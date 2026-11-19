"""Step 7：给 BOLT 配上声音（声音从 Mac 播放）。

效果：
    1. 开机：说"你好，我是 BOLT"，点阵滚动 HI
    2. 键盘遥控，每个动作都有音效：
         ↑ 加速 → Tink      ↓ 减速 → Pop
         速度为 0 时按 ↓ → 自动掉头 180° 并起步 → Submarine
         ← / → 转向 → Morse   空格 急停 → Basso + 点阵闪红
         Esc 退出 → 说"再见"
    3. 摇晃 / 被拿起 / 撞到东西（加速度突变）→ 说"哎呀"，点阵显示 !
       （用加速度判断，不依赖 spherov2 的碰撞事件，避开那个数据包解析报错）

想让声音像是从球那边发出来：把 Mac 的声音输出切到一个放在附近的蓝牙音箱。
⚠️ 在地上空旷处使用。
"""
import math
import threading
import time

from common import find_bolt
from sound import ZH_VOICE, IS_MAC, say, sound
from spherov2.sphero_edu import SpheroEduAPI
from spherov2.types import Color

try:
    from pynput import keyboard
except ImportError:
    raise SystemExit("缺少 pynput，请运行：pip install pynput")

MAX_SPEED = 150
SPEED_STEP = 30
TURN_STEP = 15
SHAKE_THRESHOLD = 1.0   # 加速度偏离 1g 超过这个值就算"摇晃"（单位 g），太灵敏就调大
SHAKE_COOLDOWN = 3.0    # 两次"哎呀"之间至少间隔几秒

BLUE = Color(0, 80, 255)
RED = Color(255, 0, 0)
YELLOW = Color(255, 200, 0)
WHITE = Color(255, 255, 255)


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.heading = 0
        self.speed = 0
        self.quit = False
        self.events = []     # 键盘线程放事件，主线程处理（只在主线程里操作 BOLT）


s = State()


def on_press(key):
    with s.lock:
        if key == keyboard.Key.up:
            s.speed = min(MAX_SPEED, s.speed + SPEED_STEP)
            s.events.append("up")
        elif key == keyboard.Key.down:
            if s.speed == 0:
                # 遥控车式倒车：已停稳时按 ↓，掉头 180° 并起步
                s.heading = (s.heading + 180) % 360
                s.speed = SPEED_STEP
                s.events.append("uturn")
            else:
                s.speed = max(0, s.speed - SPEED_STEP)
                s.events.append("down")
        elif key == keyboard.Key.left:
            s.heading = (s.heading - TURN_STEP) % 360
            s.events.append("turn")
        elif key == keyboard.Key.right:
            s.heading = (s.heading + TURN_STEP) % 360
            s.events.append("turn")
        elif key == keyboard.Key.space:
            s.speed = 0
            s.events.append("stop")
        elif key == keyboard.Key.esc:
            s.quit = True
            return False


def accel_deviation(api):
    """返回当前加速度大小与 1g 的偏差；读不到时返回 0。"""
    a = api.get_acceleration()
    if not a:
        return 0.0
    mag = math.sqrt(a.get("x", 0) ** 2 + a.get("y", 0) ** 2 + a.get("z", 0) ** 2)
    return abs(mag - 1.0)


if not IS_MAC:
    print("提示：当前不是 macOS，声音只会以文字形式打印在终端里。")
else:
    print(f"语音：{ZH_VOICE or '系统默认（没找到中文语音，可在系统设置→辅助功能→朗读内容里下载 Tingting）'}")

toy = find_bolt()
with SpheroEduAPI(toy) as api:
    # 1. 开机问候
    api.set_main_led(BLUE)
    sound("Hero")
    time.sleep(0.8)
    say("你好，我是 BOLT")
    api.scroll_matrix_text("HI", WHITE, fps=10, wait=True)
    time.sleep(3)
    api.set_main_led(BLUE)

    print(__doc__)
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    last = None
    last_shake = 0.0
    try:
        while True:
            with s.lock:
                heading, speed, quit_ = s.heading, s.speed, s.quit
                events, s.events = s.events, []
            if quit_:
                break

            # 2. 键盘音效
            for ev in events:
                if ev == "up":
                    sound("Tink")
                elif ev == "down":
                    sound("Pop")
                elif ev == "uturn":
                    sound("Submarine")
                elif ev == "turn":
                    sound("Morse")
                elif ev == "stop":
                    sound("Basso")
                    api.set_main_led(RED)
                    time.sleep(0.3)
                    api.set_main_led(BLUE)

            cur = (heading, speed)
            if cur != last:
                api.set_heading(heading)
                api.set_speed(speed)
                print(f"\r方向 {heading:3d}°  速度 {speed:3d}   ", end="", flush=True)
                last = cur

            # 3. 摇晃检测
            now = time.time()
            if now - last_shake > SHAKE_COOLDOWN and accel_deviation(api) > SHAKE_THRESHOLD:
                last_shake = now
                say("哎呀")
                api.set_matrix_character("!", YELLOW)
                print("\n检测到摇晃 / 碰撞")
                time.sleep(0.6)
                api.set_main_led(BLUE)

            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        api.stop_roll()
        listener.stop()
        api.set_main_led(Color(0, 0, 0))
        say("再见", wait=True)

print("\n已停车并断开")
