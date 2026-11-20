"""Step 10：输入一串英文，让 BOLT 在点阵上滚动显示。

用法：
    python 10_scroll_text.py                 # 交互模式：一直连着，输入一句显示一句
    python 10_scroll_text.py "HELLO WORLD"   # 只显示这一句，然后退出

交互模式下的命令：
    :color 颜色    换颜色，可选：white red orange yellow green cyan blue purple pink
    :speed 数字    滚动速度 1–30（帧/秒），默认 10，数字越大越快
    :repeat 次数   每句话滚动几遍，默认 1
    :q             退出（也可以按 Ctrl+C）

限制：
    · 只支持英文、数字和常见符号（ASCII 可打印字符），中文无法显示
    · BOLT 一次最多滚动 25 个字符；更长的句子会自动按单词拆成几段，依次显示
"""
import sys
import time

from common import find_bolt
from spherov2.sphero_edu import SpheroEduAPI
from spherov2.types import Color

MAX_CHARS = 25          # spherov2 文档注明：一次最多 25 个字符
FPS_MIN, FPS_MAX = 1, 30
# 估算滚动时长：每个字符约 6 列，加上滚入滚出约 8 列，每帧移动 1 列
COLS_PER_CHAR = 6
EXTRA_COLS = 8

COLORS = {
    "white": Color(255, 255, 255),
    "red": Color(255, 0, 0),
    "orange": Color(255, 120, 0),
    "yellow": Color(255, 220, 0),
    "green": Color(0, 255, 0),
    "cyan": Color(0, 220, 255),
    "blue": Color(0, 80, 255),
    "purple": Color(160, 0, 255),
    "pink": Color(255, 60, 160),
}


def check_text(text: str):
    """返回不支持的字符列表（非 ASCII 可打印字符）。"""
    return sorted({c for c in text if not (32 <= ord(c) <= 126)})


def split_text(text: str, limit: int = MAX_CHARS):
    """把长句按单词拆成不超过 limit 个字符的几段；单个超长单词直接硬切。"""
    chunks, cur = [], ""
    for word in text.split():
        while len(word) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(word[:limit])
            word = word[limit:]
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= limit:
            cur += " " + word
        else:
            chunks.append(cur)
            cur = word
    if cur:
        chunks.append(cur)
    return chunks


def scroll_seconds(chunk: str, fps: int) -> float:
    return (len(chunk) * COLS_PER_CHAR + EXTRA_COLS) / fps + 0.5


def show(api, text: str, color: Color, fps: int, repeat: int):
    bad = check_text(text)
    if bad:
        print(f"  ✗ 含有点阵不支持的字符：{' '.join(bad)}  —— 请只用英文、数字和常见符号")
        return
    chunks = split_text(text)
    if not chunks:
        return
    if len(chunks) > 1:
        print(f"  超过 {MAX_CHARS} 个字符，分成 {len(chunks)} 段：{chunks}")
    for r in range(repeat):
        for chunk in chunks:
            print(f"  ▶ {chunk}")
            api.scroll_matrix_text(chunk, color, fps=fps, wait=True)
            # spherov2 还没实现 wait 参数，这里按估算时长等待，避免下一段把这一段打断
            time.sleep(scroll_seconds(chunk, fps))
    api.clear_matrix()


def interactive(api):
    color_name, fps, repeat = "white", 10, 1
    print(__doc__)
    while True:
        try:
            line = input(f"[{color_name} / 速度 {fps} / {repeat} 遍] 输入英文 > ").strip()
        except EOFError:
            break
        if not line:
            continue
        if line.startswith(":"):
            cmd, _, arg = line[1:].partition(" ")
            cmd, arg = cmd.lower(), arg.strip().lower()
            if cmd in ("q", "quit", "exit"):
                break
            elif cmd == "color":
                if arg in COLORS:
                    color_name = arg
                else:
                    print(f"  可选颜色：{' '.join(COLORS)}")
            elif cmd == "speed":
                if arg.isdigit() and FPS_MIN <= int(arg) <= FPS_MAX:
                    fps = int(arg)
                else:
                    print(f"  速度请输入 {FPS_MIN}–{FPS_MAX} 的整数")
            elif cmd == "repeat":
                if arg.isdigit() and 1 <= int(arg) <= 10:
                    repeat = int(arg)
                else:
                    print("  次数请输入 1–10 的整数")
            else:
                print("  未知命令。可用：:color  :speed  :repeat  :q")
            continue
        show(api, line, COLORS[color_name], fps, repeat)


def main():
    one_shot = " ".join(sys.argv[1:]).strip()
    if one_shot and check_text(one_shot):
        sys.exit(f"含有点阵不支持的字符：{' '.join(check_text(one_shot))}")

    toy = find_bolt()
    with SpheroEduAPI(toy) as api:
        try:
            if one_shot:
                show(api, one_shot, COLORS["white"], 10, 1)
            else:
                interactive(api)
        except KeyboardInterrupt:
            print()
        finally:
            api.clear_matrix()
    print("已断开")


if __name__ == "__main__":
    main()
