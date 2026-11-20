"""Step 11_2：点阵时钟第二版 —— 时、分、秒（时：第 1、2 列；分：第 4、5 列；秒：第 7、8 列）。

  静的灯，是已经过去的时间；
  正在亮起来的那一颗，是此刻。

编码方式（列、颗都从 1 开始数；颗从上往下数）

【小时】第 1、2 列，日升日落（sunrise-clock 分支），24 小时制
    白天是太阳，夜里是月亮；看它的高度和颜色就知道是什么时候。

          第1列（升）  第2列（落）
    第2颗    12 / 0      12 / 0      ← 正午（太阳）/ 子夜（月亮）：两列同亮
    第3颗    11 / 23      13 / 1
    第4颗    10 / 22      14 / 2
    第5颗     9 / 21      15 / 3
    第6颗     8 / 20      16 / 4
    第7颗     7 / 19      17 / 5
    第8颗     6           18          ← 地平线：日出 / 日落
                （每格左边是太阳的钟点，右边是月亮的钟点）

    太阳：贴近地平线是深橙红，越高越暖、越亮，正午近乎暖白；傍晚比清晨更红一些
    月亮：清冷的蓝白，越高越亮

【分钟、秒】"十位 + 个位"，全部常亮，不再闪烁：

                    分钟（第 4、5 列）          秒（第 7、8 列）
    十位 1–5 颗     第 4 列，白灯 ◆             第 7 列，蓝灯 ■
    第 6 颗         第 4 列，空着               第 7 列，空着
    个位路径        第4列第7、8颗 → 第5列1–8颗   第7列第7、8颗 → 第8列1–8颗
    个位            绿灯 ○                      黄灯 ●

    分钟 = 白灯数 × 10 + 绿灯数
    秒   = 蓝灯数 × 10 + 黄灯数

    第 3 列、第 6 列不用，用来隔开时、分、秒。

【呼吸】
    每一秒里，"下一秒将要亮起的那颗灯"会从黑暗中慢慢亮起来，像吸一口气；
    在整秒的那一刻正好亮足，成为一颗安静的常亮灯。随后下一颗开始呼吸。
    · 平时呼吸的是下一颗黄灯
    · x9 秒时呼吸的是下一颗蓝灯 —— 进位前的那一秒，十位慢慢亮起；整秒时九颗黄灯同时熄灭
    · 59 秒时呼吸的是下一颗分钟灯
    · 小时更慢：下一个钟点的灯用整整一个小时慢慢亮起（一小时一口气），整点时正好亮足
    · 亮度按人眼的感知曲线（smoothstep + gamma 2.2）上升，看起来是匀速、柔和地亮起
    · 熄灭不做渐变：进位就在整秒那一刻干净利落地发生
    分钟不再有闪烁灯，整个画面每秒只有一颗灯在缓缓变化。

         第1列 第2列 │ 第4列 第5列 │ 第7列 第8列
    第1颗  ·     ·   │   ◆     ○   │   ■     ●     （左图 = 15 点 12 分 25 秒）
    第2颗  ·     ·   │   ·     ·   │   ■     ●     时：午后，太阳在第 2 列第 5 颗（高度 3）
    第3颗  ·     ·   │   ·     ·   │   ·     ●     分：1 白 + 2 绿
    第4颗  ·     ·   │   ·     ·   │   ·     ✧     秒：2 蓝 + 5 黄
    第5颗  ·     ☼   │   ·     ·   │   ·     ·     ✧ = 正在呼吸、将在 26 秒亮足的那颗
    第6颗  ·     ·   │   ·     ·   │   ·     ·
    第7颗  ·     ·   │   ○     ·   │   ●     ·
    第8颗  ·     ·   │   ○     ·   │   ●     ·

用法：
    python 11_2_stopwatch.py                   # 时钟（默认）：启动时读取电脑系统时间，从这个时间开始走
    python 11_2_stopwatch.py --stopwatch       # 秒表：从 0 开始计时
    python 11_2_stopwatch.py --start 55        # 秒表：从第 55 秒开始
    python 11_2_stopwatch.py --start 9:55      # 从 9 分 55 秒开始（看分钟进位）
    python 11_2_stopwatch.py --start 10:59:55  # 从 10 时 59 分 55 秒开始（看 10→11 点）
    python 11_2_stopwatch.py --preview         # 不连 BOLT，只在终端预览（可与上面的参数组合）

运行中（输入后按回车）：
    回车   暂停 / 继续（时钟模式下"继续"会重新对准系统时间）
    r      时钟模式：重新对准系统时间；秒表模式：清零重新开始
    q      退出（也可以按 Ctrl+C）
"""
import argparse
import datetime as dt
import threading
import time

OFF = (0, 0, 0)
# 秒
BLUE = (0, 80, 255)          # 秒十位
YELLOW = (255, 200, 0)       # 秒个位
# 分钟（和秒的颜色区分开）
WHITE = (255, 255, 255)      # 分十位（白：避免和洋红色的小时混淆）
GREEN = (0, 255, 60)         # 分个位
# 小时（和分、秒的颜色区分开）
MAGENTA = (255, 0, 255)      # 小时：洋红

PALETTE = (OFF, YELLOW, BLUE, WHITE, GREEN, MAGENTA)   # 常亮颜色（呼吸中的灯是它们的渐暗版本）

# 呼吸
BREATH_STEPS = 8   # 每秒亮度分 8 档：足够柔和，蓝牙每秒最多多发约 7 条命令
GAMMA = 2.2        # 人眼对亮度的感知近似 gamma 2.2：按它换算，亮起来看着才是"匀速"的


def make_digit_group(col: int, tens_color, ones_color):
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
        "pixels": [(xx, y) for xx in (x, x + 1) for y in range(8)],
    }


MINUTES = make_digit_group(4, WHITE, GREEN)   # 第 4、5 列
SECONDS = make_digit_group(7, BLUE, YELLOW)    # 第 7、8 列
GROUPS = (MINUTES, SECONDS)

# 小时：日升日落（sunrise-clock 分支），24 小时制
# 白天（6–18 点）是太阳，夜里（19–5 点）是月亮。高度表示时刻：
#   太阳：6 点在第 1 列最底（第 8 颗）升起，每小时升一格，12 点到第 2 颗、两列同亮（日在中天），
#         下午移到第 2 列，每小时落一格，18 点落到第 8 颗。
#   月亮：19 点从第 1 列第 7 颗升起，0 点到第 2 颗、两列同亮（子夜），之后在第 2 列落下，5 点到第 7 颗。
# 颜色跟着高度走：贴近地平线是深橙红，越高越亮、越暖白；傍晚比清晨更红一些。月亮是清冷的蓝白。
HOUR_PIXELS = [(x, y) for x in (0, 1) for y in range(8)]

SUN_MORNING = [  # 高度 0（地平线）→ 6（正午）
    (255, 45, 0), (255, 85, 5), (255, 125, 15), (255, 160, 40), (255, 190, 80), (255, 215, 120), (255, 235, 170)]
SUN_EVENING = [(r, int(g * 0.72), int(b * 0.5)) for r, g, b in SUN_MORNING]   # 夕阳更红
MOON = [  # 高度 1 → 6（子夜）：越高越亮
    (30, 55, 160), (40, 70, 185), (55, 90, 210), (70, 110, 230), (90, 130, 245), (120, 155, 255)]

HOUR_GLYPHS = {**{c: "☼" for c in SUN_MORNING + SUN_EVENING}, **{c: "☾" for c in MOON}}

PERIODS = {0: "子夜·月在中天", 1: "夜·月落", 2: "夜·月落", 3: "夜·月落", 4: "夜·月落", 5: "黎明前·月将落",
           6: "日出", 7: "清晨", 8: "清晨", 9: "上午", 10: "上午", 11: "上午", 12: "正午·日在中天",
           13: "午后", 14: "午后", 15: "午后", 16: "傍晚", 17: "傍晚", 18: "日落",
           19: "夜·月升", 20: "夜·月升", 21: "夜·月升", 22: "夜·月升", 23: "夜·月升"}


def hour_number(total_seconds: int) -> int:
    """24 小时制的钟点，0–23。"""
    return (total_seconds // 3600) % 24


def sky(total_seconds: int):
    """返回 (天体, 高度 0–6, 所在列 ['L'/'R'/'LR'])。"""
    h = hour_number(total_seconds)
    if 6 <= h <= 18:
        height, body, side = 6 - abs(h - 12), "sun", ("L" if h < 12 else "R" if h > 12 else "LR")
    else:
        hh = h if h >= 12 else h + 24          # 19…29，24 = 子夜
        height, body, side = 6 - abs(hh - 24), "moon", ("L" if hh < 24 else "R" if hh > 24 else "LR")
    return body, height, side


def hour_frame(total_seconds: int):
    """小时部分的画面：{(x, y): 颜色}。"""
    frame = {p: OFF for p in HOUR_PIXELS}
    body, height, side = sky(total_seconds)
    y = 7 - height                               # 高度 0 = 第 8 颗，高度 6 = 第 2 颗
    if body == "sun":
        color = (SUN_MORNING if hour_number(total_seconds) <= 12 else SUN_EVENING)[height]
    else:
        color = MOON[height - 1]
    for x, s in ((0, "L"), (1, "R")):
        if s in side:
            frame[(x, y)] = color
    return frame


def hour_text(total_seconds: int) -> str:
    body, height, _ = sky(total_seconds)
    return f"{PERIODS[hour_number(total_seconds)]}，{'太阳' if body == 'sun' else '月亮'}高度 {height}/6"

ALL_PIXELS = HOUR_PIXELS + MINUTES["pixels"] + SECONDS["pixels"]


# ---------------------------------------------------------------- 编码
def split_time(elapsed: float):
    """累计秒数 → (时 0–11, 分 0–59, 秒 0–59)。小时按 12 小时制，0 点和 12 点都是 0。"""
    total = int(elapsed)
    return (total // 3600) % 12, (total // 60) % 60, total % 60


def draw_group(frame, g, value: int):
    """把 0–59 的数值按"十位 + 个位"画进 frame（全部常亮）。"""
    tens, ones = divmod(value, 10)
    for p in g["tens_path"][:tens]:
        frame[p] = g["tens_color"]
    for p in g["ones_path"][:ones]:
        frame[p] = g["ones_color"]


def steady_frame(whole_seconds: int):
    """某一整秒时的静止画面：只有常亮灯，没有呼吸。"""
    hours, minutes, seconds = split_time(whole_seconds)
    frame = {p: OFF for p in ALL_PIXELS}
    frame.update(hour_frame(whole_seconds))    # 小时（见上面的小时模块）
    draw_group(frame, MINUTES, minutes)
    draw_group(frame, SECONDS, seconds)
    return frame


def breath_level(frac: float) -> float:
    """一秒之内的"吸气"亮度：0 → 1。

    先把这一秒切成 BREATH_STEPS 档，再用 smoothstep 让开头和结尾都放缓（像呼吸），
    最后按 gamma 换成 LED 的实际亮度，让人眼看到的是均匀、柔和的变亮。
    """
    q = int(frac * BREATH_STEPS) / BREATH_STEPS
    eased = q * q * (3 - 2 * q)
    return eased ** GAMMA


def dim(color, level: float):
    return tuple(int(round(c * level)) for c in color)


HOUR_BREATH_STEPS = 30   # 一小时分 30 档：每 2 分钟才变一次亮度，几乎不占蓝牙


def hour_breath_level(frac: float) -> float:
    """一小时之内的"吸气"亮度：0 → 1。曲线和秒的呼吸一样，只是慢了 3600 倍。"""
    q = int(frac * HOUR_BREATH_STEPS) / HOUR_BREATH_STEPS
    eased = q * q * (3 - 2 * q)
    return eased ** GAMMA


def brighter(a, b):
    return a if sum(a) >= sum(b) else b


def encode(elapsed: float):
    """把经过的时间编码成像素：返回 {(x, y): 颜色}，y=0 是最上面一颗。

    当前整秒的常亮画面 + "下一整秒将要新亮起的灯"按呼吸亮度慢慢浮现。
    整秒那一刻，呼吸的灯正好亮足；该熄灭的灯（比如进位时的九颗黄灯）在那一刻同时熄灭。
    """
    now = int(elapsed)
    frame = steady_frame(now)
    upcoming = steady_frame(now + 1)
    level = breath_level(elapsed - now)
    if level > 0:
        for p, c in upcoming.items():
            if c != OFF and frame[p] == OFF:
                frame[p] = dim(c, level)
    # 小时的呼吸：下一个钟点将要新亮起的灯，用一整个小时慢慢亮起来
    hour_start = now - now % 3600
    current_h, next_h = hour_frame(now), hour_frame(hour_start + 3600)
    h_level = hour_breath_level((elapsed - hour_start) / 3600)
    if h_level > 0:
        for p, c in next_h.items():
            if sum(c) > sum(current_h.get(p, OFF)):      # 比现在更亮的灯，才需要慢慢亮起
                frame[p] = brighter(frame[p], dim(c, h_level))
    return frame


def breathing_pixels(elapsed: float):
    """此刻正在呼吸的灯（预览、测试用）。"""
    now = int(elapsed)
    a, b = steady_frame(now), steady_frame(now + 1)
    return [p for p in ALL_PIXELS if a[p] == OFF and b[p] != OFF]


def to_device(p, flip: bool = True):
    """人看到的坐标（y=0 在上）→ BOLT 点阵坐标（实测 y=0 在下，见 11_analog_clock.py）。"""
    x, y = p
    return (x, 7 - y) if flip else (x, y)


def describe(elapsed: float) -> str:
    h, m, s = split_time(elapsed)
    return (f"{hour_number(int(elapsed)):2d} 时 {m:2d} 分 {s:2d} 秒 = 时[{hour_text(int(elapsed))}]"
            f"  分[{m // 10} 白 + {m % 10} 绿]"
            f"  秒[{s // 10} 蓝 + {s % 10} 黄]")


def preview_text(frame, elapsed: float) -> str:
    chars = {OFF: "·", WHITE: "◆", GREEN: "○", BLUE: "■", YELLOW: "●", MAGENTA: "▲", **HOUR_GLYPHS}
    level = breath_level(elapsed - int(elapsed))
    glyph = "·" if level < 0.02 else "∘" if level < 0.25 else "✧" if level < 0.7 else "✦"
    lines = [f"累计 {elapsed:7.1f} 秒   " + describe(elapsed)]
    for y in range(8):
        row = []
        for x in (0, 1, None, 3, 4, None, 6, 7):
            if x is None:
                row.append("│")
                continue
            c = frame.get((x, y), OFF)
            row.append(chars.get(c, glyph))   # 不在常亮色表里的，就是正在呼吸的灯
        lines.append("  " + "  ".join(row))
    return "\n".join(lines)


def parse_start(text: str) -> float:
    """--start 支持 "55"（秒）、"9:55"（分:秒）或 "10:59:55"（时:分:秒）。"""
    parts = text.split(":")
    if not 1 <= len(parts) <= 3:
        raise argparse.ArgumentTypeError("格式应为 秒、分:秒 或 时:分:秒")
    total = 0.0
    for part in parts[:-1]:
        total = (total + int(part)) * 60
    return total + float(parts[-1])


def now_seconds() -> float:
    """当前系统时间折算成从 0 点开始的秒数（含小数）。"""
    n = dt.datetime.now()
    return n.hour * 3600 + n.minute * 60 + n.second + n.microsecond / 1e6


# ---------------------------------------------------------------- 批量刷新
FULL_GRID = [(x, y) for x in range(8) for y in range(8)]


def plan_updates(target, shown):
    """把"当前画面 → 目标画面"的变化合并成尽量少的矩形填充命令。

    BOLT 每条点阵命令都要单独走一次蓝牙（实测每条几十毫秒）。逐颗更新时，整点要改 30 颗左右，
    会超过 1 秒，导致漏显一秒（见 11_2 测试报告 7.1）。这里按列找"目标颜色相同的连续一段"，
    用一条 set_matrix_fill 画完；左右相邻两列如果是完全相同的一段，再合并成一个矩形。
    目标颜色相同、本来就已经是这个颜色的像素也可以顺带覆盖，结果不变，但能把段连得更长。

    返回 [(x1, x2, y1, y2, 颜色), ...]，坐标是"人看到的坐标"（y=0 在上），两端都包含。
    """
    runs = []
    for x in range(8):
        covered = set()
        for y in range(8):
            if y in covered or target.get((x, y), OFF) == shown.get((x, y), OFF):
                continue
            c = target.get((x, y), OFF)
            y1 = y
            while y1 - 1 >= 0 and (y1 - 1) not in covered and target.get((x, y1 - 1), OFF) == c:
                y1 -= 1
            y2 = y
            while y2 + 1 <= 7 and target.get((x, y2 + 1), OFF) == c:
                y2 += 1
            covered.update(range(y1, y2 + 1))
            runs.append([x, x, y1, y2, c])
    # 相邻列的同一段（同样的上下端、同样颜色）合并成矩形
    runs.sort(key=lambda r: (r[2], r[3], r[4], r[0]))
    merged = []
    for r in runs:
        last = merged[-1] if merged else None
        if last and last[2:] == r[2:] and last[1] + 1 == r[0]:
            last[1] = r[0]
        else:
            merged.append(r)
    # 先发"点亮"的命令，再发"熄灭"的：新的数字先出现，旧的随后消失，整点时读数不会出现空白
    merged.sort(key=lambda r: r[4] == OFF)
    return [tuple(r) for r in merged]


def apply_update(api, cmd, colors, flip, state):
    """执行一条合并后的命令；不支持 set_matrix_fill 时自动退回逐颗绘制。"""
    x1, x2, y1, y2, c = cmd
    (dx1, dy1), (dx2, dy2) = to_device((x1, y1), flip), to_device((x2, y2), flip)
    if (x1, y1) == (x2, y2) or not state.get("fill_ok", True):
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                dx, dy = to_device((x, y), flip)
                api.set_matrix_pixel(dx, dy, colors[c])
        return
    try:
        api.set_matrix_fill(dx1, dy1, dx2, dy2, colors[c])
    except AttributeError:
        state["fill_ok"] = False          # 老版本 spherov2 没有 set_matrix_fill
        apply_update(api, cmd, colors, flip, state)


# ---------------------------------------------------------------- 秒表状态
class Stopwatch:
    def __init__(self, start: float = 0.0, running: bool = True, follow_clock: bool = False):
        self.lock = threading.Lock()
        self.follow_clock = follow_clock  # 时钟模式：起点取系统时间
        if follow_clock:
            start = now_seconds()
        self.start = start          # 命令行 --start 指定的起点
        self.base = start           # 暂停前累计的秒数
        self.t0 = time.monotonic()  # 本次开始计时的时刻
        self.running = running
        self.quit = False
        # 状态版本号：清零、暂停/继续、重设起点时 +1。
        # 刷新线程每发一条蓝牙命令前都会检查它，发现变了就丢掉正在画的旧帧，立刻改画新状态。
        self.version = 0

    def restart_from(self, start: float):
        """把计时基准重设到 start，并从现在开始走。

        连接 BOLT 要花几秒（实测约 6 秒）；在连接、清屏、画好起始画面之后再调用，
        这几秒就不会被算进秒表。
        """
        with self.lock:
            self.base = start
            self.t0 = time.monotonic()
            self.running = True
            self.version += 1

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
                if self.follow_clock:
                    self.base = now_seconds()   # 时钟不该"暂停后慢几分钟"：继续时直接对准系统时间
                self.t0 = time.monotonic()
                self.running = True
            self.version += 1
            return self.running

    def reset(self):
        """秒表模式：清零；时钟模式：重新对准系统时间。"""
        with self.lock:
            self.base = now_seconds() if self.follow_clock else 0.0
            self.t0 = time.monotonic()
            self.version += 1


def help_line(sw: Stopwatch) -> str:
    r_text = "重新对时" if sw.follow_clock else "清零"
    return f"命令：回车=暂停/继续  r={r_text}  q=退出"


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
            print("↺ 已重新对准系统时间" if sw.follow_clock else "↺ 已清零")
        elif cmd in ("q", "quit", "exit"):
            break
        else:
            print(help_line(sw))
    sw.quit = True


# ---------------------------------------------------------------- 运行
def run_preview(sw: Stopwatch):
    def loop():
        last = None
        while not sw.quit:
            e = sw.elapsed()
            key = int(e * 4)          # 每 0.25 秒打印一次，能看到呼吸的过程
            if key != last:
                last = key
                print("\n" + preview_text(encode(e), e))
            time.sleep(0.02)

    threading.Thread(target=loop, daemon=True).start()
    print("终端预览（第1、2列 │ 第4、5列 │ 第7、8列；▲ 洋红=时  ◆ 白=分十位  ○ 绿=分个位"
          "  ■ 蓝=秒十位  ● 黄=秒个位  ∘ ✧ ✦ = 正在呼吸、慢慢亮起的灯）")
    keyboard_loop(sw)


def run_bolt(sw: Stopwatch, flip: bool):
    from common import find_bolt
    from spherov2.sphero_edu import SpheroEduAPI
    from spherov2.types import Color

    class ColorCache(dict):
        """呼吸会用到很多渐暗的颜色，用到哪个就创建哪个。"""
        def __missing__(self, rgb):
            self[rgb] = Color(*rgb)
            return self[rgb]

    colors = ColorCache()
    toy = find_bolt()
    with SpheroEduAPI(toy) as api:
        api.set_back_led(colors[OFF])     # 关掉刺眼的前后灯
        api.set_front_led(colors[OFF])
        api.clear_matrix()

        # 先把起始画面画好（如 --start 55 要点亮 11 颗灯，要花一点时间），
        # 画完再开始计时：蓝牙连接和初始绘制的时间都不计入秒表
        if sw.follow_clock:
            sw.start = now_seconds()      # 时钟模式：用连接完成这一刻的系统时间
        fill_state = {}
        initial = encode(sw.start)
        blank = {p: OFF for p in FULL_GRID}
        for cmd in plan_updates(initial, blank):
            apply_update(api, cmd, colors, flip, fill_state)
        if sw.follow_clock:
            # 画初始画面也要时间，时钟模式下直接对齐到画完这一刻的系统时间
            sw.start = now_seconds()
        print("运行中 —— " + help_line(sw))
        h, m, s = split_time(sw.start)
        print(f"连接完成，从 {h} 时 {m} 分 {s} 秒开始计时")
        sw.restart_from(sw.start)

        def loop():
            shown = {p: initial.get(p, OFF) for p in FULL_GRID}   # 点阵上实际显示的内容
            last_sec = None
            cmd_time = 0.05      # 一条蓝牙命令的耗时，运行中不断实测更新（指数平均）
            try:
                while not sw.quit:
                    version = sw.version
                    e = sw.elapsed()
                    target = e
                    if sw.running:
                        # 准时进位：估算"下一个整秒的画面"要发几条命令、要多久，
                        # 提前这么一点开始发，让变化正好落在整秒上（而不是晚几十到几百毫秒）
                        boundary = int(e) + 1
                        n_next = len(plan_updates(encode(boundary), shown))
                        lead = min(0.35, (n_next + 1) / 2 * cmd_time)
                        if boundary - e <= lead:
                            target = boundary
                    tick = int(target)
                    frame = encode(target)
                    finished = True
                    for cmd in plan_updates(frame, shown):
                        # 计时和刷新解耦：一旦状态变了（清零/暂停）或时间已经越过了这一帧对应的整秒，
                        # 就放弃这一帧剩下的命令，回到循环开头直接画最新的画面
                        # （呼吸亮度的小台阶不打断，只有整秒才打断，保证进位准时）
                        if sw.quit or sw.version != version or int(sw.elapsed()) > tick:
                            finished = False
                            break
                        t_cmd = time.monotonic()
                        apply_update(api, cmd, colors, flip, fill_state)
                        cmd_time = 0.8 * cmd_time + 0.2 * min(0.3, time.monotonic() - t_cmd)
                        x1, x2, y1, y2, c = cmd
                        for x in range(x1, x2 + 1):
                            for y in range(y1, y2 + 1):
                                shown[(x, y)] = c
                    sec = tick
                    if finished and sec != last_sec:
                        last_sec = sec
                        # 只有整帧画完才打印，日志和点阵上实际显示的一致
                        print(f"\r{describe(target)}   ", end="", flush=True)
                    time.sleep(0.01)
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
    p = argparse.ArgumentParser(description="点阵时、分、秒（时：第 1、2 列；分：第 4、5 列；秒：第 7、8 列）")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--stopwatch", action="store_true", help="秒表模式：从 0 开始计时")
    g.add_argument("--start", type=parse_start, default=None,
                   help="秒表模式：从指定时间开始，如 55、9:55、10:59:55")
    g.add_argument("--now", action="store_true", help=argparse.SUPPRESS)  # 旧参数：时钟现在是默认模式
    p.add_argument("--preview", action="store_true", help="不连 BOLT，只在终端预览")
    p.add_argument("--no-flip", action="store_true", help="不做上下翻转（一般不需要）")
    a = p.parse_args()

    # 默认是时钟：一启动就读取电脑的系统时间
    clock_mode = not a.stopwatch and a.start is None
    start = 0.0 if a.start is None else a.start
    sw = Stopwatch(start, running=a.preview, follow_clock=clock_mode)
    if clock_mode:
        h24 = int(sw.start // 3600)
        print(f"已读取系统时间 {h24:02d}:{int(sw.start % 3600 // 60):02d}:{int(sw.start % 60):02d}"
              f"（点阵按 24 小时日升日落显示{'' if a.preview else '；连上 BOLT 后会再对一次时'}）")
    else:
        h, m, s_ = split_time(start)
        print(f"秒表模式：从 {h} 时 {m} 分 {s_} 秒开始")

    if a.preview:
        run_preview(sw)
    else:
        # 连 BOLT 时先不走表，等连接和初始画面完成后由 run_bolt 启动
        run_bolt(sw, flip=not a.no_flip)


if __name__ == "__main__":
    main()
