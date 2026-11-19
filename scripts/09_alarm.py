"""Step 9：BOLT 闹钟 —— 到点 Mac 播放音乐，BOLT 闪灯提醒。

用法（建议用 caffeinate 启动，防止 Mac 闲置睡眠）：
    caffeinate -i python 09_alarm.py --in 2                 # 测试：2 分钟后响
    caffeinate -i python 09_alarm.py --time 08:00           # 每天 8:00
    caffeinate -i python 09_alarm.py --time 08:00 --weekdays --music ~/Music/wake.mp3

关闹钟：
    · 拿起 BOLT 摇一摇（加速度检测）
    · 或者在电脑上按任意键（需要 pynput 的输入监控权限）
    不关的话：每轮响 RING_MINUTES 分钟，停 SNOOZE_MINUTES 分钟后再响，最多 MAX_ROUNDS 轮。

设计要点：
    · 等待期间不连 BOLT，整晚不耗它的电
    · 到点先放音乐，再连 BOLT；就算 BOLT 连不上，音乐照样响
    · BOLT 默认放在充电座上 → 只闪灯不移动；不在座上时可加 --move 让它原地转圈
"""
import argparse
import datetime as dt
import math
import os
import subprocess
import sys
import threading
import time

from common import BOLT_NAME
from sound import IS_MAC, say, sound
from spherov2 import scanner
from spherov2.sphero_edu import SpheroEduAPI
from spherov2.types import Color

RING_MINUTES = 3        # 每轮最多响几分钟
SNOOZE_MINUTES = 5      # 没关闹钟时，隔几分钟再响
MAX_ROUNDS = 3          # 最多响几轮
SHAKE_THRESHOLD = 1.0   # 加速度偏离 1g 超过多少算"摇一摇"
CONNECT_TRIES = 3       # 连 BOLT 的重试次数

COLORS = [Color(255, 0, 0), Color(255, 160, 0), Color(255, 255, 0),
          Color(0, 255, 0), Color(0, 120, 255), Color(180, 0, 255)]


# ---------------------------------------------------------------- 参数与时间
def parse_args():
    p = argparse.ArgumentParser(description="Sphero BOLT 闹钟")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--time", help="每天的闹钟时间，如 08:00")
    g.add_argument("--in", dest="in_minutes", type=float, help="测试用：N 分钟后响一次")
    p.add_argument("--music", help="音乐文件路径（mp3 / m4a / aiff / wav）；不填就用系统音效 + 语音")
    p.add_argument("--volume", type=int, default=60, help="响铃时的 Mac 音量 0–100，默认 60")
    p.add_argument("--weekdays", action="store_true", help="只在周一到周五响")
    p.add_argument("--move", action="store_true", help="让 BOLT 原地转圈（BOLT 不在充电座上时才用）")
    a = p.parse_args()
    if a.music:
        a.music = os.path.expanduser(a.music)
        if not os.path.isfile(a.music):
            p.error(f"找不到音乐文件：{a.music}")
    return a


def next_alarm(hhmm: str, weekdays: bool, now: dt.datetime) -> dt.datetime:
    h, m = map(int, hhmm.split(":"))
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t <= now:
        t += dt.timedelta(days=1)
    while weekdays and t.weekday() >= 5:
        t += dt.timedelta(days=1)
    return t


def wait_until(t: dt.datetime):
    print(f"下次闹钟：{t:%Y-%m-%d %H:%M}（{['周一','周二','周三','周四','周五','周六','周日'][t.weekday()]}）")
    while True:
        left = (t - dt.datetime.now()).total_seconds()
        if left <= 0:
            return
        print(f"\r  还剩 {int(left // 3600):02d}:{int(left % 3600 // 60):02d}:{int(left % 60):02d}   ",
              end="", flush=True)
        time.sleep(min(left, 1 if left < 60 else 30))


# ---------------------------------------------------------------- Mac 音量与音乐
def get_volume():
    if not IS_MAC:
        return None
    try:
        out = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return int(out)
    except Exception:
        return None


def set_volume(v):
    if IS_MAC and v is not None:
        subprocess.run(["osascript", "-e", f"set volume output volume {v}"], timeout=5)


class Music:
    """在后台循环播放音乐，直到 stop()。"""

    def __init__(self, path):
        self.path = path
        self.stop_event = threading.Event()
        self.proc = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        first = True
        while not self.stop_event.is_set():
            if not IS_MAC:
                print("\n[闹钟] 叮铃铃——起床啦！")
                self.stop_event.wait(5)
                continue
            if self.path:
                self.proc = subprocess.Popen(["afplay", self.path])
            else:
                sound("Glass")
                time.sleep(0.6)
                if first:
                    say("早上好，该起床了")
                    first = False
                self.proc = subprocess.Popen(["afplay", "/System/Library/Sounds/Hero.aiff"])
            while self.proc.poll() is None and not self.stop_event.is_set():
                time.sleep(0.2)
            if self.proc.poll() is None:
                self.proc.terminate()
            self.stop_event.wait(0.5)

    def stop(self):
        self.stop_event.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.thread.join(timeout=3)


# ---------------------------------------------------------------- BOLT
def connect_bolt():
    for i in range(1, CONNECT_TRIES + 1):
        print(f"\n连接 {BOLT_NAME}（第 {i}/{CONNECT_TRIES} 次）……")
        try:
            toy = scanner.find_toy(toy_name=BOLT_NAME, timeout=10)
            print(f"  扫描到 {toy.name}")
            return toy
        except scanner.ToyNotFoundError:
            print("  没扫到")
        except Exception as e:
            print(f"  出错：{e!r}")
    return None


def accel_deviation(api):
    a = api.get_acceleration()
    if not a:
        return 0.0
    return abs(math.sqrt(sum(a.get(k, 0) ** 2 for k in "xyz")) - 1.0)


def bolt_show(api, dismissed: threading.Event, deadline: float, move: bool, label: str):
    """BOLT 灯光秀，直到被摇晃、按键或超时。返回 True 表示被关掉。"""
    api.scroll_matrix_text(label, Color(255, 255, 255), fps=10, wait=True)
    time.sleep(len(label) * 0.8 + 1)
    i = 0
    while time.time() < deadline and not dismissed.is_set():
        api.set_main_led(COLORS[i % len(COLORS)])
        if move and i % 10 == 0:
            api.spin(360, 1)
        if accel_deviation(api) > SHAKE_THRESHOLD:
            print("\n检测到摇晃 —— 闹钟关闭")
            dismissed.set()
            break
        if i % 40 == 39:
            api.scroll_matrix_text("WAKE UP", Color(255, 255, 255), fps=10, wait=True)
            time.sleep(7)
        i += 1
        time.sleep(0.25)
    if dismissed.is_set():
        api.set_main_led(Color(0, 255, 0))
        time.sleep(1.5)
    api.set_main_led(Color(0, 0, 0))
    return dismissed.is_set()


# ---------------------------------------------------------------- 响铃一次（含多轮）
def ring(args):
    dismissed = threading.Event()

    listener = None
    try:
        from pynput import keyboard
        listener = keyboard.Listener(on_press=lambda k: dismissed.set())
        listener.start()
    except Exception as e:
        print(f"（键盘关闹钟不可用：{e!r}，请摇 BOLT 关闭）")

    old_volume = get_volume()
    try:
        for rnd in range(1, MAX_ROUNDS + 1):
            print(f"\n===== 闹钟响了！第 {rnd}/{MAX_ROUNDS} 轮  {dt.datetime.now():%H:%M:%S} =====")
            set_volume(args.volume)
            music = Music(args.music)
            music.start()
            deadline = time.time() + RING_MINUTES * 60

            bolt_ok = False
            toy = connect_bolt()
            if toy:
                try:
                    with SpheroEduAPI(toy) as api:
                        bolt_ok = True
                        print(f"  ✅ 已连接并接管 BOLT（摇一摇关闹钟）")
                        bolt_show(api, dismissed, deadline, args.move, dt.datetime.now().strftime("%H:%M"))
                except Exception as e:
                    print(f"  ⚠️ 连接后控制出错：{e!r}")
            if not bolt_ok:
                print("  ❌ 没连上 BOLT —— 只用 Mac 音乐提醒（按任意键关闭）")

            while time.time() < deadline and not dismissed.is_set():
                time.sleep(0.2)
            music.stop()

            if dismissed.is_set():
                say("早上好，祝你今天顺利")
                print("闹钟已关闭。")
                return
            if rnd < MAX_ROUNDS:
                print(f"没有关闹钟，{SNOOZE_MINUTES} 分钟后再响")
                end = time.time() + SNOOZE_MINUTES * 60
                while time.time() < end and not dismissed.is_set():
                    time.sleep(0.5)
                if dismissed.is_set():
                    print("闹钟已在稍后提醒期间关闭。")
                    return
        print("已响满最多轮数，本次闹钟结束。")
    finally:
        set_volume(old_volume)
        if listener:
            listener.stop()


# ---------------------------------------------------------------- 主程序
def main():
    args = parse_args()
    print(f"BOLT 闹钟  目标：{BOLT_NAME}  音乐：{args.music or '系统音效 + 语音'}  音量：{args.volume}")
    if not IS_MAC:
        print("提示：当前不是 macOS，只会在终端打印提醒。")

    try:
        if args.in_minutes is not None:
            wait_until(dt.datetime.now() + dt.timedelta(minutes=args.in_minutes))
            ring(args)
            return
        while True:
            wait_until(next_alarm(args.time, args.weekdays, dt.datetime.now()))
            ring(args)
            time.sleep(61)   # 避免同一分钟内重复触发
    except KeyboardInterrupt:
        print("\n已退出闹钟")
        sys.exit(0)


if __name__ == "__main__":
    main()
