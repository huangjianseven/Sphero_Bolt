"""Step 10：输入一串英文，BOLT 在点阵上一直循环滚动，直到你手动干预。

用法：
    python 10_scroll_text.py                 # 启动后输入文字
    python 10_scroll_text.py "HELLO WORLD"   # 启动后立即开始循环滚动这句

滚动过程中随时可以（输入后按回车）：
    直接输入新文字   立即换成新文字，继续循环滚动
    只按回车         暂停 / 继续
    :color 颜色      立即换颜色：white red orange yellow green cyan blue purple pink
    :speed 数字      立即换速度 1–30（帧/秒），默认 10，越大越快
    :q               退出（也可以按 Ctrl+C）
    摇一摇 BOLT      暂停（再按回车继续）

限制：
    · 只支持英文、数字和常见符号（ASCII 可打印字符），中文无法显示
    · BOLT 一次最多滚动 25 个字符；更长的句子会自动按单词拆成几段，轮流滚动
"""
import math
import sys
import threading
import time

from common import find_bolt
from spherov2.sphero_edu import SpheroEduAPI
from spherov2.types import Color

MAX_CHARS = 25          # spherov2 文档注明：一次最多 25 个字符
FPS_MIN, FPS_MAX = 1, 30
# 估算一段文字滚完的时长：每个字符约 6 列，加上滚入滚出约 8 列，每帧移动 1 列
# 如果出现"没滚完就被打断"或"两遍之间空等太久"，调大或调小 COLS_PER_CHAR
COLS_PER_CHAR = 6
EXTRA_COLS = 8
SHAKE_THRESHOLD = 1.0   # 加速度偏离 1g 超过多少算"摇一摇"

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


# ---------------------------------------------------------------- 文本处理
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


# ---------------------------------------------------------------- 共享状态
class State:
    """主线程（读键盘）只改状态；后台线程（滚动）负责所有 BOLT 操作。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.text = ""          # 当前要滚动的文字
        self.paused = True      # 没有文字时视为暂停
        self.color_name = "white"
        self.fps = 10
        self.gen = 0            # 每次有改动就 +1，滚动线程据此立即切换
        self.quit = False
        self.changed = threading.Event()

    def update(self, **kw):
        with self.lock:
            for k, v in kw.items():
                setattr(self, k, v)
            self.gen += 1
        self.changed.set()

    def snapshot(self):
        with self.lock:
            return self.gen, self.text, self.paused, COLORS[self.color_name], self.fps, self.quit


s = State()


def log(msg: str):
    """在输入提示之外打印一行（后台线程用）。"""
    print(f"\r{msg}\n> ", end="", flush=True)


def accel_deviation(api) -> float:
    a = api.get_acceleration()
    if not a:
        return 0.0
    return abs(math.sqrt(sum(a.get(k, 0) ** 2 for k in "xyz")) - 1.0)


# ---------------------------------------------------------------- 滚动线程
def scroller(api):
    cleared = True
    try:
        while True:
            gen, text, paused, color, fps, quit_ = s.snapshot()
            if quit_:
                return
            if paused or not text:
                if not cleared:
                    api.clear_matrix()
                    cleared = True
                s.changed.wait(0.2)
                s.changed.clear()
                continue

            # 一直循环：滚完最后一段又从第一段开始，直到状态改变
            for chunk in split_text(text):
                if s.gen != gen or s.quit:
                    break
                api.scroll_matrix_text(chunk, color, fps=fps, wait=True)
                cleared = False
                # spherov2 还没实现 wait 参数，这里按估算时长等待；
                # 等待期间一旦有新文字 / 暂停 / 换颜色，立刻跳出
                end = time.time() + scroll_seconds(chunk, fps)
                while time.time() < end and s.gen == gen and not s.quit:
                    if accel_deviation(api) > SHAKE_THRESHOLD:
                        s.update(paused=True)
                        log("检测到摇晃 —— 已暂停（按回车继续）")
                        break
                    time.sleep(0.05)
            if s.gen != gen:
                api.clear_matrix()   # 切换时先清屏，新内容立即开始
                cleared = True
    except Exception as e:
        log(f"⚠️ 滚动线程出错：{e!r}，请按 Ctrl+C 退出后重试")
        s.update(quit=True)


# ---------------------------------------------------------------- 键盘输入（主线程）
def status_line():
    with s.lock:
        state = "暂停" if s.paused or not s.text else "滚动中"
        return f"[{state} | {s.color_name} | 速度 {s.fps}] 当前：{s.text or '（无）'}"


def handle(line: str) -> bool:
    """处理一行输入；返回 False 表示退出。"""
    if line == "":
        with s.lock:
            has_text, paused = bool(s.text), s.paused
        if not has_text:
            print("  先输入一句英文")
        else:
            s.update(paused=not paused)
            print("  ▶ 继续滚动" if paused else "  ⏸ 已暂停（按回车继续）")
        return True

    if line.startswith(":"):
        cmd, _, arg = line[1:].partition(" ")
        cmd, arg = cmd.lower(), arg.strip().lower()
        if cmd in ("q", "quit", "exit"):
            return False
        if cmd == "color":
            if arg in COLORS:
                s.update(color_name=arg)
                print(f"  颜色 → {arg}")
            else:
                print(f"  可选颜色：{' '.join(COLORS)}")
        elif cmd == "speed":
            if arg.isdigit() and FPS_MIN <= int(arg) <= FPS_MAX:
                s.update(fps=int(arg))
                print(f"  速度 → {arg}")
            else:
                print(f"  速度请输入 {FPS_MIN}–{FPS_MAX} 的整数")
        else:
            print("  未知命令。可用：:color  :speed  :q")
        return True

    bad = check_text(line)
    if bad:
        print(f"  ✗ 含有点阵不支持的字符：{' '.join(bad)}  —— 请只用英文、数字和常见符号")
        return True
    chunks = split_text(line)
    if len(chunks) > 1:
        print(f"  超过 {MAX_CHARS} 个字符，分成 {len(chunks)} 段轮流滚动：{chunks}")
    s.update(text=line.strip(), paused=False)
    print(f"  ▶ 开始循环滚动：{line.strip()}")
    return True


def main():
    first = " ".join(sys.argv[1:]).strip()
    if first and check_text(first):
        sys.exit(f"含有点阵不支持的字符：{' '.join(check_text(first))}")

    toy = find_bolt()
    with SpheroEduAPI(toy) as api:
        t = threading.Thread(target=scroller, args=(api,), daemon=True)
        t.start()
        print(__doc__)
        if first:
            handle(first)
        try:
            while not s.quit:
                print(status_line())
                try:
                    line = input("> ").strip()
                except EOFError:
                    break
                if s.quit or not handle(line):
                    break
        except KeyboardInterrupt:
            print()
        finally:
            s.update(quit=True)
            t.join(timeout=3)
            api.clear_matrix()
    print("已停止滚动并断开")


if __name__ == "__main__":
    main()
