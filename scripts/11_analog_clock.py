"""Step 11：BOLT 指针时钟 —— 在 8x8 点阵上用模拟指针显示系统时间。

画面布局：
    · 外圈（最外一圈 28 个点）：秒针 —— 一个红点沿外圈顺时针走，60 秒一圈
    · 外圈的 12 / 3 / 6 / 9 点位置：暗白色刻度
    · 内部 6x6：分针（青色，长）和时针（橙色，短），从中心指出
    · 秒针红点每秒在"亮红 / 暗红"之间切换一次，像钟表的"嘀嗒"
    外圈只有 28 个点，红点大约每 2 秒前进一格；亮暗切换保证每一秒都能看到变化。
    前灯、后灯（主板上的蓝灯）全程关闭，不刺眼。

用法：
    python 11_analog_clock.py               # 在 BOLT 上显示，Ctrl+C 退出
    python 11_analog_clock.py --rotate 90   # 画面方向不对时旋转：0 / 90 / 180 / 270
    python 11_analog_clock.py --preview     # 不连 BOLT，只在终端里预览画面
    python 11_analog_clock.py --no-flip     # 不做上下翻转（一般不需要）

建议：让 BOLT 的点阵正对着你看；如果 12 点方向不在上方，用 --rotate 调整。
"""
import argparse
import datetime as dt
import math
import time

CENTER = 3.5                 # 8x8 点阵的几何中心在 4 个中心像素之间
MINUTE_LEN = 2.9             # 分针长度（像素）；< 3 保证不压到外圈秒针
HOUR_LEN = 1.9               # 时针长度

# 颜色用 (r, g, b) 元组表示，连 BOLT 时再转成 Color
OFF = (0, 0, 0)
SECOND = (255, 0, 0)         # 秒针：亮红（偶数秒）
SECOND_DIM = (60, 0, 0)      # 秒针：暗红（奇数秒）
MINUTE = (0, 200, 255)       # 分针：青
HOUR = (255, 120, 0)         # 时针：橙
MARK = (40, 40, 40)          # 刻度：暗白
PREVIEW_CHARS = {OFF: "·", SECOND: "S", SECOND_DIM: "s", MINUTE: "M", HOUR: "H", MARK: "+"}


# ---------------------------------------------------------------- 几何
def angle_of(x: float, y: float) -> float:
    """像素中心相对点阵中心的角度：12 点方向为 0°，顺时针增加。"""
    return math.degrees(math.atan2(x - CENTER, CENTER - y)) % 360


# 外圈 28 个像素，按顺时针（从 12 点开始）排序
RING = sorted(
    [(x, y) for y in range(8) for x in range(8) if x in (0, 7) or y in (0, 7)],
    key=lambda p: angle_of(*p),
)
# 刻度：外圈上 12 / 3 / 6 / 9 点各两个像素
MARKS = [(3, 0), (4, 0), (7, 3), (7, 4), (3, 7), (4, 7), (0, 3), (0, 4)]


def ring_pixel(deg: float):
    """外圈上最接近指定角度的像素。"""
    def dist(p):
        d = abs(angle_of(*p) - deg) % 360
        return min(d, 360 - d)
    return min(RING, key=dist)


def hand_pixels(deg: float, length: float):
    """从中心沿 deg 方向画一根长 length 的指针，返回经过的像素。"""
    rad = math.radians(deg)
    dx, dy = math.sin(rad), -math.cos(rad)
    pts = []
    steps = [0.5 + 0.25 * i for i in range(int((length - 0.5) / 0.25) + 1)] + [length]  # 末端一定取到
    for t in steps:
        x = math.floor(CENTER + t * dx + 0.5)
        y = math.floor(CENTER + t * dy + 0.5)
        x, y = min(max(x, 1), 6), min(max(y, 1), 6)   # 限制在内部 6x6
        if (x, y) not in pts:
            pts.append((x, y))
    return pts


def render(now: dt.datetime):
    """返回 {(x, y): 颜色}，包含全部 64 个像素。"""
    frame = {(x, y): OFF for y in range(8) for x in range(8)}
    for p in MARKS:
        frame[p] = MARK
    hour_deg = (now.hour % 12 + now.minute / 60) * 30
    minute_deg = (now.minute + now.second / 60) * 6
    # 先画长的分针，再把短的时针叠在上面：两针重合时，分针伸出去的部分仍然看得见
    for p in hand_pixels(minute_deg, MINUTE_LEN):
        frame[p] = MINUTE
    for p in hand_pixels(hour_deg, HOUR_LEN):
        frame[p] = HOUR
    frame[ring_pixel(now.second * 6)] = SECOND if now.second % 2 == 0 else SECOND_DIM
    return frame


def rotate(p, quarter_turns: int):
    """把像素坐标顺时针旋转 quarter_turns 个 90°。"""
    x, y = p
    for _ in range(quarter_turns % 4):
        x, y = 7 - y, x
    return x, y


def to_device(p, quarter_turns: int, flip: bool = True):
    """把"人看到的坐标"（y=0 在最上面）换成 BOLT 点阵的坐标。

    实测（2026-11-20 照片）：BOLT 的 set_matrix_pixel 的 y 轴和我们以为的相反，
    y=0 在下面。不翻转的话，整个画面上下颠倒：秒针看起来逆时针走，分针指反方向。
    """
    x, y = rotate(p, quarter_turns)
    return (x, 7 - y) if flip else (x, y)


def preview_text(frame) -> str:
    return "\n".join(
        " ".join(PREVIEW_CHARS.get(frame[(x, y)], "?") for x in range(8)) for y in range(8)
    )


# ---------------------------------------------------------------- 运行
def run_preview():
    print("终端预览（S/s=秒针亮/暗 M=分针 H=时针 +=刻度），Ctrl+C 退出")
    last = None
    try:
        while True:
            now = dt.datetime.now()
            if now.second != last:
                last = now.second
                print(f"\n{now:%H:%M:%S}\n{preview_text(render(now))}")
            time.sleep(0.05)
    except KeyboardInterrupt:
        print()


def run_bolt(quarter_turns: int, flip: bool = True):
    from common import find_bolt
    from spherov2.sphero_edu import SpheroEduAPI
    from spherov2.types import Color

    cache = {}

    def color(rgb):
        if rgb not in cache:
            cache[rgb] = Color(*rgb)
        return cache[rgb]

    toy = find_bolt()
    with SpheroEduAPI(toy) as api:
        print("指针时钟运行中（红=秒 青=分 橙=时，红点每秒亮暗切换），Ctrl+C 退出")
        # 关掉前灯和后灯（主板上的蓝灯），只用点阵显示
        api.set_back_led(color(OFF))
        api.set_front_led(color(OFF))
        api.clear_matrix()
        shown = {(x, y): OFF for y in range(8) for x in range(8)}
        last_sec = None
        try:
            while True:
                now = dt.datetime.now()
                if now.second != last_sec:
                    last_sec = now.second
                    frame = render(now)
                    # 只发送有变化的像素：每条命令都要走蓝牙，整屏重画太慢
                    changed = [p for p in frame if frame[p] != shown[p]]
                    for p in changed:
                        x, y = to_device(p, quarter_turns, flip)
                        api.set_matrix_pixel(x, y, color(frame[p]))
                        shown[p] = frame[p]
                    print(f"\r{now:%H:%M:%S}  更新 {len(changed):2d} 个像素   ", end="", flush=True)
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            api.clear_matrix()
            api.set_back_led(color(OFF))
            api.set_front_led(color(OFF))
    print("\n已清屏并断开")


def main():
    p = argparse.ArgumentParser(description="BOLT 指针时钟")
    p.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270],
                   help="画面顺时针旋转角度，用来把 12 点方向转到上方")
    p.add_argument("--preview", action="store_true", help="不连 BOLT，只在终端里预览")
    p.add_argument("--no-flip", action="store_true",
                   help="不做上下翻转（默认会翻转，以适配 BOLT 点阵 y 轴朝上的坐标）")
    a = p.parse_args()
    if a.preview:
        run_preview()
    else:
        run_bolt(a.rotate // 90, flip=not a.no_flip)


if __name__ == "__main__":
    main()
