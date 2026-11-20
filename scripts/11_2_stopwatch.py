"""Step 11_2：点阵时钟第二版 —— 十进制秒表（分钟：第 4、5 列；秒：第 7、8 列）。

编码方式（列、颗都从 1 开始数；颗从上往下数）。分钟和秒用同一套规则：

                    分钟（第 4、5 列）          秒（第 7、8 列）
    十位 1–5 颗     第 4 列，紫灯 ◆             第 7 列，蓝灯 ■
    第 6 颗         第 4 列，空着               第 7 列，空着
    个位路径        第4列第7、8颗 → 第5列1–8颗   第7列第7、8颗 → 第8列1–8颗
    个位常亮        绿灯 ○                      黄灯 ●
    闪烁（正在走）   绿灯 ⊙，亮 1 秒、灭 1 秒     黄灯 ✱，亮半秒、灭半秒

    分钟 = 紫灯数 × 10 + 常亮绿灯数
    秒   = 蓝灯数 × 10 + 常亮黄灯数
    分钟的闪烁比秒的慢一倍，两个闪烁灯一眼就能分开。

    第 6 列（以及第 1–3 列）不用，用来隔开分钟和秒。

          第4列 第5列 │ 第7列 第8列
    第1颗   ◆     ○   │   ■     ●       （左图 = 12 分 25 秒）
    第2颗   ·     ⊙   │   ■     ●       分：1 紫 + 2 绿 + 闪烁
    第3颗   ·     ·   │   ·     ●       秒：2 蓝 + 5 黄 + 闪烁
    第4颗   ·     ·   │   ·     ✱
    第5颗   ·     ·   │   ·     ·
    第6颗   ·     ·   │   ·     ·       ← 第 6 颗始终空着
    第7颗   ○     ·   │   ●     ·       ← 个位起点
    第8颗   ○     ·   │   ●     ·

    60 秒  → 秒回到 0，分钟个位 +1
    10 分  → 分钟进位：1 个紫灯，绿灯清零
    60 分  → 全部回到 0（小时以后再加）

用法：
    python 11_2_stopwatch.py                 # 启动即开始计时
    python 11_2_stopwatch.py --start 55      # 从第 55 秒开始（看秒 59→0、分钟 +1）
    python 11_2_stopwatch.py --start 9:55    # 从 9 分 55 秒开始（看分钟 9→10 进位）
    python 11_2_stopwatch.py --start 59:55   # 从 59 分 55 秒开始（看 59:59→0:00）
    python 11_2_stopwatch.py --preview       # 不连 BOLT，只在终端预览

运行中（输入后按回车）：
    回车   暂停 / 继续
    r      清零重新开始
    q      退出（也可以按 Ctrl+C）
"""
import argparse
import threading
import time

OFF = (0, 0, 0)
# 秒
BLUE = (0, 80, 255)          # 秒十位
YELLOW = (255, 200, 0)       # 秒个位（常亮和闪烁同色）
# 分钟（和秒的颜色区分开）
PURPLE = (180, 0, 255)       # 分十位
GREEN = (0, 255, 60)         # 分个位（常亮和闪烁同色）


def make_digit_group(col: int, tens_color, ones_color, blink_period: float):
    """一组"十位 + 个位"显示：用第 col 列和第 col+1 列（列号从 1 开始）。

    坐标用 (x, y)：x 是列、y 是颗，都从 0 开始数（第 7 列 → x=6，第 1 颗 → y=0）。
    """
    x = col - 1
    return {
        "tens_path": [(x, y) for y in range(5)],                       # 第 col 列第 1–5 颗
        "ones_path": [(x, 6), (x, 7)] + [(x + 1, y) for y in range(8)],  # 第 col 列第 7、8 颗 + 第 col+1 列
        "gap": (x, 5),                                                 # 第 col 列第 6 颗：空着
        "tens_color": tens_color,
        "ones_color": ones_color,
        "blink_period": blink_period,   # 闪烁周期（秒）：前一半亮、后一半灭
        "pixels": [(xx, y) for xx in (x, x + 1) for y in range(8)],
    }


MINUTES = make_digit_group(4, PURPLE, GREEN, blink_period=2.0)   # 第 4、5 列
SECONDS = make_digit_group(7, BLUE, YELLOW, blink_period=1.0)    # 第 7、8 列
GROUPS = (MINUTES, SECONDS)
ALL_PIXELS = MINUTES["pixels"] + SECONDS["pixels"]


# ---------------------------------------------------------------- 编码
def split_time(elapsed: float):
    """累计秒数 → (分 0–59, 秒 0–59)。"""
    total = int(elapsed)
    return (total // 60) % 60, total % 60


def draw_group(frame, g, value: int, elapsed: float):
    """把 0–59 的数值按"十位 + 个位 + 闪烁"画进 frame。"""
    tens, ones = divmod(value, 10)
    for p in g["tens_path"][:tens]:
        frame[p] = g["tens_color"]
    for p in g["ones_path"][:ones]:
        frame[p] = g["ones_color"]
    blink_on = (elapsed % g["blink_period"]) < g["blink_period"] / 2
    frame[g["ones_path"][ones]] = g["ones_color"] if blink_on else OFF


def encode(elapsed: float):
    """把经过的时间编码成像素：返回 {(x, y): 颜色}，y=0 是最上面一颗。"""
    minutes, seconds = split_time(elapsed)
    frame = {p: OFF for p in ALL_PIXELS}
    draw_group(frame, MINUTES, minutes, elapsed)
    draw_group(frame, SECONDS, seconds, elapsed)
    return frame


def to_device(p, flip: bool = True):
    """人看到的坐标（y=0 在上）→ BOLT 点阵坐标（实测 y=0 在下，见 11_analog_clock.py）。"""
    x, y = p
    return (x, 7 - y) if flip else (x, y)


def describe(elapsed: float) -> str:
    m, s = split_time(elapsed)
    return (f"{m:2d} 分 {s:2d} 秒 = 分[{m // 10} 紫 + {m % 10} 绿]"
            f"  秒[{s // 10} 蓝 + {s % 10} 黄]")


def preview_text(frame, elapsed: float) -> str:
    minutes, seconds = split_time(elapsed)
    blinks = {MINUTES["ones_path"][minutes % 10]: "⊙", SECONDS["ones_path"][seconds % 10]: "✱"}
    chars = {OFF: "·", PURPLE: "◆", GREEN: "○", BLUE: "■", YELLOW: "●"}
    lines = [f"累计 {elapsed:7.1f} 秒   " + describe(elapsed)]
    for y in range(8):
        row = []
        for x in (3, 4, None, 6, 7):
            if x is None:
                row.append("│")
                continue
            c = frame[(x, y)]
            row.append(blinks[(x, y)] if (x, y) in blinks and c != OFF else chars[c])
        lines.append("  " + "  ".join(row))
    return "\n".join(lines)


def parse_start(text: str) -> float:
    """--start 支持 "55"（秒）或 "9:55"（分:秒）。"""
    if ":" in text:
        m, s = text.split(":", 1)
        return int(m) * 60 + float(s)
    return float(text)


# ---------------------------------------------------------------- 秒表状态
class Stopwatch:
    def __init__(self, start: float = 0.0, running: bool = True):
        self.lock = threading.Lock()
        self.start = start          # 命令行 --start 指定的起点
        self.base = start           # 暂停前累计的秒数
        self.t0 = time.monotonic()  # 本次开始计时的时刻
        self.running = running
        self.quit = False

    def restart_from(self, start: float):
        """把计时基准重设到 start，并从现在开始走。

        连接 BOLT 要花几秒（实测约 6 秒）；在连接、清屏、画好起始画面之后再调用，
        这几秒就不会被算进秒表。
        """
        with self.lock:
            self.base = start
            self.t0 = time.monotonic()
            self.running = True

    def elapsed(self) -> float:
        with self.lock:
            if self.running:
                return self.base + time.monotonic() - self.t0
            return self.base

    def toggle(self) -> bool:
        with self.lock:
            if self.running:
                self.base += time.monotonic() - self.t0
                self.running = False
            else:
                self.t0 = time.monotonic()
                self.running = True
            return self.running

    def reset(self):
        with self.lock:
            self.base = 0.0
            self.t0 = time.monotonic()


def keyboard_loop(sw: Stopwatch):
    """主线程：读键盘命令。"""
    while not sw.quit:
        try:
            cmd = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd == "":
            print("▶ 继续" if sw.toggle() else "⏸ 暂停（回车继续）")
        elif cmd == "r":
            sw.reset()
            print("↺ 已清零")
        elif cmd in ("q", "quit", "exit"):
            break
        else:
            print("命令：回车=暂停/继续  r=清零  q=退出")
    sw.quit = True


# ---------------------------------------------------------------- 运行
def run_preview(sw: Stopwatch):
    def loop():
        last = None
        while not sw.quit:
            e = sw.elapsed()
            key = (int(e), e - int(e) < 0.5)
            if key != last:
                last = key
                print("\n" + preview_text(encode(e), e))
            time.sleep(0.02)

    threading.Thread(target=loop, daemon=True).start()
    print("终端预览（第4、5列 │ 第7、8列；◆ 紫=分十位  ○ 绿=分个位  ⊙ 分闪烁  ■ 蓝=秒十位  ● 黄=秒个位  ✱ 秒闪烁）")
    keyboard_loop(sw)


def run_bolt(sw: Stopwatch, flip: bool):
    from common import find_bolt
    from spherov2.sphero_edu import SpheroEduAPI
    from spherov2.types import Color

    colors = {rgb: Color(*rgb) for rgb in (OFF, YELLOW, BLUE, PURPLE, GREEN)}
    toy = find_bolt()
    with SpheroEduAPI(toy) as api:
        api.set_back_led(colors[OFF])     # 关掉刺眼的前后灯
        api.set_front_led(colors[OFF])
        api.clear_matrix()

        # 先把起始画面画好（如 --start 55 要点亮 11 颗灯，要花一点时间），
        # 画完再开始计时：蓝牙连接和初始绘制的时间都不计入秒表
        initial = encode(sw.start)
        for p, c in initial.items():
            if c != OFF:
                x, y = to_device(p, flip)
                api.set_matrix_pixel(x, y, colors[c])
        print("秒表运行中 —— 回车=暂停/继续  r=清零  q=退出")
        print(f"连接完成，从 {split_time(sw.start)[0]} 分 {sw.start % 60:.1f} 秒开始计时")
        sw.restart_from(sw.start)

        def loop():
            shown = dict(initial)
            last_sec = None
            try:
                while not sw.quit:
                    e = sw.elapsed()
                    frame = encode(e)
                    # 只发送变化的像素：平时每秒 1–2 条蓝牙命令
                    for p, c in frame.items():
                        if c != shown[p]:
                            x, y = to_device(p, flip)
                            api.set_matrix_pixel(x, y, colors[c])
                            shown[p] = c
                    sec = int(e)
                    if sec != last_sec:
                        last_sec = sec
                        # 点阵上显示的分、秒，以及各颜色灯的数量
                        print(f"\r{describe(e)}   ", end="", flush=True)
                    time.sleep(0.02)
            except Exception as ex:
                print(f"\n⚠️ 刷新出错：{ex!r}，请按回车或 Ctrl+C 退出")
                sw.quit = True

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        try:
            keyboard_loop(sw)
        finally:
            sw.quit = True
            t.join(timeout=2)
            api.clear_matrix()
    print("\n已清屏并断开")


def main():
    p = argparse.ArgumentParser(description="十进制秒表（分钟：第 4、5 列；秒：第 7、8 列）")
    p.add_argument("--start", type=parse_start, default=0.0,
                   help='起始时间：秒数如 55，或 分:秒 如 9:55，默认 0')
    p.add_argument("--preview", action="store_true", help="不连 BOLT，只在终端预览")
    p.add_argument("--no-flip", action="store_true", help="不做上下翻转（一般不需要）")
    a = p.parse_args()
    if a.preview:
        run_preview(Stopwatch(a.start))
    else:
        # 连 BOLT 时先不走表，等连接和初始画面完成后由 run_bolt 启动
        run_bolt(Stopwatch(a.start, running=False), flip=not a.no_flip)


if __name__ == "__main__":
    main()
