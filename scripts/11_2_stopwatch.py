"""Step 11_2：点阵时钟第二版 —— 十进制秒表（只用最右边两列）。

编码方式（列、颗都从 1 开始数；颗从上往下数）：

    第 7 列 第 1–5 颗   蓝灯 = 秒数的十位（0–5），从上往下依次点亮
    第 7 列 第 6 颗     空着，用来隔开十位和个位
    个位黄灯的路径（共 10 个位置）：
        第 7 列 第 7 颗 → 第 7 列 第 8 颗 → 第 8 列 第 1 颗 → … → 第 8 列 第 8 颗
    常亮黄灯 = 秒数的个位（0–9），沿路径依次点亮
    闪烁黄灯 = 正在走的这一秒，位于常亮黄灯之后的下一个位置

    秒数 = 蓝灯数 × 10 + 常亮黄灯数

         第7列 第8列
    第1颗  ■     ●          ■ 蓝   ● 常亮黄   ✱ 闪烁黄   · 不亮
    第2颗  ■     ●
    第3颗  ·     ●          （左图 = 25.x 秒：2 蓝 + 5 黄 + 闪烁）
    第4颗  ·     ✱
    第5颗  ·     ·
    第6颗  ·     ·          ← 第 7 列第 6 颗始终空着
    第7颗  ●     ·          ← 个位起点
    第8颗  ●     ·

    0.x 秒  → 第 7 列第 7 颗闪烁
    9.x 秒  → 9 个常亮黄 + 第 8 列第 8 颗闪烁
    10 秒   → 进位：1 个蓝灯 + 第 7 列第 7 颗闪烁（黄灯清零）
    59.x 秒 → 5 个蓝灯 + 9 个常亮黄 + 闪烁
    60 秒   → 回到 0

用法：
    python 11_2_stopwatch.py              # 启动即开始计时
    python 11_2_stopwatch.py --start 55   # 从第 55 秒开始（方便看 59→0）
    python 11_2_stopwatch.py --preview    # 不连 BOLT，只在终端预览

运行中（输入后按回车）：
    回车   暂停 / 继续
    r      清零重新开始
    q      退出（也可以按 Ctrl+C）
"""
import argparse
import threading
import time

# 坐标用 (x, y)：x 是列、y 是颗，都从 0 开始数（第 7 列 → x=6，第 1 颗 → y=0）
TENS_PATH = [(6, y) for y in range(5)]                  # 第 7 列第 1–5 颗
ONES_PATH = [(6, 6), (6, 7)] + [(7, y) for y in range(8)]  # 第 7 列第 7、8 颗 + 第 8 列第 1–8 颗
GAP = (6, 5)                                            # 第 7 列第 6 颗：空着
BLINK_ON_FRACTION = 0.5                                 # 每秒前半秒亮、后半秒灭

OFF = (0, 0, 0)
YELLOW = (255, 200, 0)
BLUE = (0, 80, 255)

PREVIEW_CHARS = {OFF: "·", YELLOW: "●", BLUE: "■"}
ALL_PIXELS = [(x, y) for x in (6, 7) for y in range(8)]


# ---------------------------------------------------------------- 编码
def encode(elapsed: float):
    """把经过的秒数编码成两列像素：返回 {(x, y): 颜色}，y=0 是最上面一颗。"""
    sec = int(elapsed) % 60
    frac = elapsed - int(elapsed)
    tens, ones = divmod(sec, 10)
    blink_on = frac < BLINK_ON_FRACTION

    frame = {p: OFF for p in ALL_PIXELS}
    for p in TENS_PATH[:tens]:                 # 蓝灯：十位
        frame[p] = BLUE
    for p in ONES_PATH[:ones]:                 # 常亮黄灯：个位
        frame[p] = YELLOW
    frame[ONES_PATH[ones]] = YELLOW if blink_on else OFF   # 闪烁：正在走的这一秒
    return frame


def to_device(p, flip: bool = True):
    """人看到的坐标（y=0 在上）→ BOLT 点阵坐标（实测 y=0 在下，见 11_analog_clock.py）。"""
    x, y = p
    return (x, 7 - y) if flip else (x, y)


def preview_text(frame, elapsed: float) -> str:
    sec = int(elapsed) % 60
    tens, ones = divmod(sec, 10)
    blink_pos = ONES_PATH[ones]
    lines = [f"{elapsed:6.1f} 秒   = {tens} 蓝 × 10 + {ones} 黄"]
    for y in range(8):
        cells = []
        for x in (6, 7):
            c = frame[(x, y)]
            cells.append("✱" if (x, y) == blink_pos and c == YELLOW else PREVIEW_CHARS[c])
        lines.append("  " + "  ".join(cells))
    return "\n".join(lines)


# ---------------------------------------------------------------- 秒表状态
class Stopwatch:
    def __init__(self, start: float = 0.0):
        self.lock = threading.Lock()
        self.base = start           # 暂停前累计的秒数
        self.t0 = time.monotonic()  # 本次开始计时的时刻
        self.running = True
        self.quit = False

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
            key = (int(e), e - int(e) < BLINK_ON_FRACTION)
            if key != last:
                last = key
                print("\n" + preview_text(encode(e), e))
            time.sleep(0.02)

    threading.Thread(target=loop, daemon=True).start()
    print("终端预览（左列=第7列 右列=第8列；■ 蓝  ● 常亮黄  ✱ 闪烁黄）")
    keyboard_loop(sw)


def run_bolt(sw: Stopwatch, flip: bool):
    from common import find_bolt
    from spherov2.sphero_edu import SpheroEduAPI
    from spherov2.types import Color

    colors = {rgb: Color(*rgb) for rgb in (OFF, YELLOW, BLUE)}
    toy = find_bolt()
    with SpheroEduAPI(toy) as api:
        api.set_back_led(colors[OFF])     # 关掉刺眼的前后灯
        api.set_front_led(colors[OFF])
        api.clear_matrix()

        def loop():
            shown = {p: OFF for p in ALL_PIXELS}
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
                    sec = int(e) % 60
                    if sec != last_sec:
                        last_sec = sec
                        print(f"\r{e:6.1f} 秒  = {sec // 10} 蓝 + {sec % 10} 黄   ", end="", flush=True)
                    time.sleep(0.02)
            except Exception as ex:
                print(f"\n⚠️ 刷新出错：{ex!r}，请按回车或 Ctrl+C 退出")
                sw.quit = True

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        print("秒表运行中 —— 回车=暂停/继续  r=清零  q=退出")
        try:
            keyboard_loop(sw)
        finally:
            sw.quit = True
            t.join(timeout=2)
            api.clear_matrix()
    print("\n已清屏并断开")


def main():
    p = argparse.ArgumentParser(description="十进制秒表（点阵最右两列）")
    p.add_argument("--start", type=float, default=0.0, help="从第几秒开始，默认 0")
    p.add_argument("--preview", action="store_true", help="不连 BOLT，只在终端预览")
    p.add_argument("--no-flip", action="store_true", help="不做上下翻转（一般不需要）")
    a = p.parse_args()
    sw = Stopwatch(a.start)
    if a.preview:
        run_preview(sw)
    else:
        run_bolt(sw, flip=not a.no_flip)


if __name__ == "__main__":
    main()
