"""Step 12：声之涟漪 —— 让 BOLT 的点阵随音乐跳动。

  低音是心跳，落在正中；
  人声和乐器在中间两圈起伏；
  整首歌的气息，是最外面那一圈慢慢明暗的光。
  每一记重拍，中心先亮成白色，再荡开一圈涟漪。

画面：8x8 点阵分成 4 圈同心方环（从里到外）

    ┌────────────────┐
    │ 外圈：整体响度   │   ← 变化最慢，像呼吸的氛围光
    │ ┌────────────┐ │
    │ │ 第三圈：中高 │ │   ← 500–2000 Hz：人声、吉他、钢琴的亮部
    │ │ ┌────────┐ │ │
    │ │ │ 第二圈 │ │ │   ← 150–500 Hz：贝斯、人声的厚度
    │ │ │ ┌────┐ │ │ │
    │ │ │ │中心│ │ │ │   ← 40–150 Hz：底鼓、低音，反应最快
    │ │ │ └────┘ │ │ │
    │ │ └────────┘ │ │
    │ └────────────┘ │
    └────────────────┘

颜色：跟着音色慢慢漂移 —— 低音重时偏暖（琥珀、玫红），高音亮时偏冷（紫、青）；
      每一圈比里面一圈冷一点，形成由内而外的渐变。安静下来时，只剩外圈微微呼吸。

为什么是同心方环：BOLT 每改一次点阵都要发一条蓝牙命令（实测约 50 ms），一秒只能发十几条。
      每个方环是一个矩形，一条 set_matrix_fill 就能画完；从外往里叠着画，中心只要 1 条命令，
      最外圈也只要 4 条。最需要快的低音放在中心，所以鼓点几乎是即时的。

声音从哪来：
    python 12_music_pulse.py                       # 默认：用 Mac 的麦克风"听"房间里的音乐
    python 12_music_pulse.py --file 歌.mp3          # 播放这首歌，同时直接分析它（最准、不受环境噪音影响）
    python 12_music_pulse.py --device BlackHole    # 直接"听"电脑播放的声音（需安装 BlackHole 虚拟声卡）
    python 12_music_pulse.py --list-devices        # 列出可用的录音设备
    python 12_music_pulse.py --demo                # 不用任何声音：内置一段 120 BPM 的节奏，用来看效果

不连 BOLT，只在终端里看（终端里会画出彩色的 8x8 方块）：
    python 12_music_pulse.py --demo --preview
    python 12_music_pulse.py --file 歌.mp3 --preview

其他：
    --gain 1.5      灵敏度（默认 1.0）。房间里音乐小声时调大，太容易满就调小
    Ctrl+C          停止

需要：pip install numpy sounddevice（--demo 和 --file 只需要 numpy）
macOS 第一次用麦克风时，要在"系统设置 → 隐私与安全性 → 麦克风"里给终端授权。
"""
import argparse
import colorsys
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from collections import deque

try:
    import numpy as np
except ImportError:
    sys.exit("缺少 numpy，请运行：pip install numpy sounddevice")

SAMPLE_RATE = 44100
BLOCK = 1024                         # 每块约 23 ms
BANDS = [(40, 150), (150, 500), (500, 2000)]   # 中心、第二圈、第三圈对应的频段（Hz）

# 4 圈方环，从中心到外圈；(x1, y1, x2, y2)，两端都包含
RINGS = [(3, 3, 4, 4), (2, 2, 5, 5), (1, 1, 6, 6), (0, 0, 7, 7)]
RING_NAMES = ["中心·低音", "第二圈·中低", "第三圈·中高", "外圈·响度"]

# 每圈的反应速度：attack 越大越快跟上，release 越小落得越慢（单位：每秒）
ATTACK = [40.0, 18.0, 14.0, 3.0]
RELEASE = [7.0, 4.0, 3.5, 0.8]

# 刷新的优先级：每圈两次重画之间至少隔多久（秒）。中心随时可画；越往外越"沉稳"。
# 例外：颜色变化很大（比如涟漪经过、重拍变白）时立刻重画。
MIN_INTERVAL = [0.0, 0.15, 0.3, 1.0]
MIN_CHANGE = [0.06, 0.12, 0.12, 0.06]   # 变化小于这个比例就先不画（细微的抖动不值得占用蓝牙）
RIPPLE_MIN_STRENGTH = 0.7   # 只有够强的重拍才荡开涟漪（每一拍都会让中心变白）
RIPPLE_MIN_GAP = 0.9        # 两次涟漪之间至少隔多久（秒）
RIPPLE_RINGS = 3            # 涟漪荡到第三圈为止；外圈留给安静的氛围光
BIG_CHANGE = 0.30        # 某个颜色通道变化超过 30% 就算"很大"

HUE_WARM = 15.0      # 低音重时的基础色相（琥珀红）
HUE_COOL = 195.0     # 高音亮时的基础色相（青）
HUE_STEP_PER_RING = 22.0   # 每往外一圈，色相往"冷"的方向偏一点
GAMMA = 2.2


# ================================================================ 声音分析
class Analyzer:
    """把一块块音频变成：三个频段的力度、整体响度、音色明暗、重拍时刻。"""

    def __init__(self, sr=SAMPLE_RATE, block=BLOCK, gain=1.0):
        self.sr, self.block, self.gain = sr, block, gain
        self.window = np.hanning(block)
        freqs = np.fft.rfftfreq(block, 1 / sr)
        self.band_idx = [(freqs >= lo) & (freqs < hi) for lo, hi in BANDS]
        self.freqs = freqs
        self.peaks = [1e-6] * (len(BANDS) + 1)      # 自动增益：记住最近的峰值，响度自适应
        self.bass_hist = deque(maxlen=int(sr / block * 1.0))   # 最近 1 秒的低音能量
        self.lock = threading.Lock()
        self.raw = [0.0] * 4          # 0–1：三个频段 + 整体响度
        self.centroid = 0.5           # 0（暗/低沉）–1（亮/尖锐）
        self.last_beat = -1.0
        self.beat_strength = 0.0
        self.silent = True

    def process(self, samples, t):
        x = np.asarray(samples, dtype=np.float64)
        if x.ndim > 1:
            x = x.mean(axis=1)
        if len(x) < self.block:
            x = np.pad(x, (0, self.block - len(x)))
        x = x[: self.block] * self.gain
        rms = float(np.sqrt(np.mean(x ** 2)))
        spec = np.abs(np.fft.rfft(x * self.window))
        energies = [float(np.sqrt(np.mean(spec[idx] ** 2))) if idx.any() else 0.0 for idx in self.band_idx]
        values = energies + [rms]

        # 自动增益：峰值慢慢衰减（约 6 秒减半），所以无论音量大小都能用满亮度
        decay = 0.5 ** (self.block / self.sr / 6.0)
        levels = []
        for i, v in enumerate(values):
            self.peaks[i] = max(v, self.peaks[i] * decay, 1e-6)
            levels.append(min(1.0, v / self.peaks[i]))

        silent = rms < 0.004           # 噪声门：太小声就当作安静
        total = spec.sum()
        centroid_hz = float((spec * self.freqs).sum() / total) if total > 0 else 500.0
        centroid = min(1.0, max(0.0, (math.log2(max(centroid_hz, 200)) - math.log2(200)) / (math.log2(6000) - math.log2(200))))

        # 重拍：低音能量明显高于最近一秒的平均值，且距上一拍至少 0.28 秒
        bass = energies[0]
        mean_bass = (sum(self.bass_hist) / len(self.bass_hist)) if self.bass_hist else bass
        self.bass_hist.append(bass)
        beat = (not silent and len(self.bass_hist) > 10 and bass > 1.45 * mean_bass
                and bass > 0.3 * self.peaks[0] and t - self.last_beat > 0.28)

        with self.lock:
            self.raw = [0.0] * 4 if silent else levels
            self.silent = silent
            self.centroid = 0.97 * self.centroid + 0.03 * centroid   # 音色慢慢漂移
            if beat:
                self.last_beat = t
                self.beat_strength = min(1.0, bass / max(self.peaks[0], 1e-6))

    def snapshot(self):
        with self.lock:
            return list(self.raw), self.centroid, self.last_beat, self.beat_strength, self.silent


# ================================================================ 声音来源
def feed_samples(analyzer, samples, sr, stop, t0):
    """按真实时间把一段音频一块块喂给分析器（用于 --file 和 --demo）。"""
    n = len(samples)
    pos = 0
    while not stop.is_set() and pos < n:
        target = t0 + pos / sr
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        analyzer.process(samples[pos: pos + BLOCK], time.monotonic())
        pos += BLOCK
    stop.set()


def make_demo(seconds=120, sr=SAMPLE_RATE, bpm=120):
    """内置的一段节奏：底鼓、军鼓、踩镲，加上缓慢变化的和弦。"""
    t = np.arange(int(seconds * sr)) / sr
    beat = 60 / bpm
    phase = t % beat
    kick = np.sin(2 * np.pi * (55 + 90 * np.exp(-phase * 30)) * phase) * np.exp(-phase * 9)
    bar_phase = t % (beat * 2)
    snare_t = (bar_phase - beat) % (beat * 2)
    snare = np.random.default_rng(1).normal(0, 1, len(t)) * np.exp(-snare_t * 25) * 0.35
    hat_t = t % (beat / 2)
    hat = np.random.default_rng(2).normal(0, 1, len(t)) * np.exp(-hat_t * 80) * 0.08
    hat = hat - np.convolve(hat, np.ones(8) / 8, mode="same")       # 只留高频
    chord_root = 220 * 2 ** (np.floor(t / (beat * 8)) % 4 * 3 / 12)
    chord = sum(np.sin(2 * np.pi * chord_root * r * t) for r in (1, 1.26, 1.5)) * 0.07
    chord *= 0.6 + 0.4 * np.sin(2 * np.pi * t / 16)
    swell = 0.55 + 0.45 * np.sin(2 * np.pi * t / 32) ** 2           # 整体有起伏
    return ((kick * 0.8 + snare + hat + chord) * swell * 0.5).astype(np.float32)


def load_audio_file(path):
    """读取音频文件为单声道 float 数组。WAV 直接读；其他格式在 macOS 上用自带的 afconvert 转成 WAV。"""
    tmp = None
    if not path.lower().endswith(".wav"):
        if not shutil.which("afconvert"):
            sys.exit("非 WAV 文件需要 macOS 自带的 afconvert 转换；请先转成 .wav 再试")
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@44100", path, tmp], check=True)
        path = tmp
    with wave.open(path, "rb") as w:
        sr, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        data = w.readframes(n)
    if tmp:
        os.unlink(tmp)
    if width != 2:
        sys.exit("只支持 16 位 WAV；可以用：afconvert -f WAVE -d LEI16 输入 输出.wav")
    x = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768
    return x.reshape(-1, ch).mean(axis=1), sr


def start_source(args, analyzer, stop):
    """启动声音来源，返回一个停止函数。"""
    if args.demo:
        samples = make_demo()
        t0 = time.monotonic()
        threading.Thread(target=feed_samples, args=(analyzer, samples, SAMPLE_RATE, stop, t0), daemon=True).start()
        print("声音来源：内置 120 BPM 演示节奏（不发出声音）")
        return lambda: None

    if args.file:
        samples, sr = load_audio_file(os.path.expanduser(args.file))
        analyzer.__init__(sr=sr, gain=args.gain)
        player = None
        if shutil.which("afplay"):
            player = subprocess.Popen(["afplay", os.path.expanduser(args.file)])
        t0 = time.monotonic()
        threading.Thread(target=feed_samples, args=(analyzer, samples, sr, stop, t0), daemon=True).start()
        print(f"声音来源：{args.file}（{len(samples) / sr:.0f} 秒）" + ("，正在播放" if player else "，未播放（没有 afplay）"))
        return lambda: player and player.poll() is None and player.terminate()

    try:
        import sounddevice as sd
    except Exception as e:
        sys.exit(f"用麦克风需要 sounddevice：pip install sounddevice（{e!r}）\n也可以先用 --demo 或 --file 试试")
    device = args.device
    if device is not None and device.isdigit():
        device = int(device)

    def callback(indata, frames, time_info, status):
        analyzer.process(indata[:, 0].copy(), time.monotonic())

    stream = sd.InputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK, channels=1, device=device, callback=callback)
    stream.start()
    name = sd.query_devices(stream.device)["name"] if not isinstance(stream.device, (list, tuple)) else device
    print(f"声音来源：录音设备「{name}」—— 对着音乐，让它听见")
    return stream.close


# ================================================================ 画面
def hsv(h_deg, s, v):
    r, g, b = colorsys.hsv_to_rgb((h_deg % 360) / 360, s, v)
    return r, g, b


def mix_white(rgb, w):
    return tuple(c + (1 - c) * w for c in rgb)


def to_led(rgb, level):
    """把 0–1 的颜色和亮度，按人眼感知（gamma）换成 0–255 的 LED 值，并做量化，减少无谓的刷新。"""
    q = round(level * 12) / 12            # 亮度分 12 档
    return tuple(int(round(255 * c * q ** GAMMA)) for c in rgb)


class Painter:
    """根据声音状态，算出 4 圈此刻的颜色。所有动态都按真实时间计算，与刷新速度无关。"""

    def __init__(self):
        self.level = [0.0] * 4
        self.last_t = time.monotonic()
        self.flashes = deque(maxlen=4)       # 每一拍：中心变白 (时间, 强度)
        self.ripples = deque(maxlen=4)       # 强拍：向外荡开的涟漪 (开始时间, 强度)
        self.seen_beat = -1.0
        self.last_ripple = -10.0

    def colors(self, analyzer, t):
        raw, centroid, last_beat, strength, silent = analyzer.snapshot()
        dt = max(1e-3, min(0.2, t - self.last_t))
        self.last_t = t
        for i in range(4):
            target = raw[i]
            rate = ATTACK[i] if target > self.level[i] else RELEASE[i]
            self.level[i] += (target - self.level[i]) * (1 - math.exp(-rate * dt))

        if last_beat != self.seen_beat and last_beat > 0:
            self.seen_beat = last_beat
            self.flashes.append((last_beat, 0.6 + 0.4 * strength))   # 再轻的重拍也要看得见
            if strength >= RIPPLE_MIN_STRENGTH and last_beat - self.last_ripple >= RIPPLE_MIN_GAP:
                self.last_ripple = last_beat
                self.ripples.append((last_beat, strength))

        base_hue = HUE_WARM + 360 - (HUE_WARM + 360 - HUE_COOL) * centroid   # 暖 → 冷，途经玫红、紫、蓝
        out = []
        for i in range(4):
            hue = base_hue - HUE_STEP_PER_RING * i
            v = 0.07 + 0.93 * self.level[i] ** 1.3           # 留一点底光，画面永远不全黑
            white = 0.0
            if i == 0:
                for tb, s in self.flashes:                    # 每一拍：中心先变白，再慢慢回到原来的颜色
                    if t >= tb:
                        pulse = s * math.exp(-(t - tb) / 0.2)
                        v = min(1.0, v + 0.5 * pulse)
                        white = max(white, pulse)
            elif i < RIPPLE_RINGS:
                for tb, s in self.ripples:                    # 强拍：涟漪从中心向外，每圈晚 0.1 秒到达
                    dt_r = t - tb - 0.1 * i
                    if dt_r >= 0:
                        v = min(1.0, v + 0.55 * s * math.exp(-dt_r / 0.22))
            if silent and i == 3:                             # 安静时：外圈慢慢呼吸
                v = 0.08 + 0.06 * (0.5 + 0.5 * math.sin(t * 2 * math.pi / 5))
            sat = 0.95 - 0.25 * (1 - self.level[i])           # 弱的时候更淡雅，强的时候更饱和
            rgb = mix_white(hsv(hue, sat, 1.0), round(white * 4) / 4)
            out.append(to_led(rgb, v))
        return out


# ================================================================ 输出：终端预览
def run_preview(analyzer, painter, stop):
    """在终端里画彩色 8x8（真彩色 ANSI），每秒约 25 帧。"""
    print("\n" * 9, end="")
    try:
        while not stop.is_set():
            cols = painter.colors(analyzer, time.monotonic())
            grid = [[None] * 8 for _ in range(8)]
            for i in range(3, -1, -1):                       # 从外往里叠着画，和 BOLT 上一样
                x1, y1, x2, y2 = RINGS[i]
                for y in range(y1, y2 + 1):
                    for x in range(x1, x2 + 1):
                        grid[y][x] = cols[i]
            lines = ["".join(f"\x1b[38;2;{r};{g};{b}m██" for r, g, b in row) + "\x1b[0m" for row in grid]
            raw, _, _, _, silent = analyzer.snapshot()
            bars = "  ".join(f"{n.split('·')[1]} {'▮' * int(v * 8):<8}" for n, v in zip(RING_NAMES, raw))
            print("\x1b[9A" + "\n".join(lines) + f"\n{'（安静）' if silent else bars}\x1b[K")
            time.sleep(0.04)
    except KeyboardInterrupt:
        pass


# ================================================================ 输出：BOLT
def run_bolt(analyzer, painter, stop, start):
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
        api.set_back_led(color((0, 0, 0)))
        api.set_front_led(color((0, 0, 0)))
        api.clear_matrix()
        start()       # 连上 BOLT 之后才开始放歌 / 开始听，开头几秒不会错过
        print("已连接 —— 开始播放音乐吧（Ctrl+C 停止）")
        shown = [None] * 4
        drawn_at = [0.0] * 4
        frames, cmds, t_stat = 0, 0, time.monotonic()

        def due(i, c, now):
            """这一圈现在要不要重画：有变化，并且（到了它的最短间隔，或者变化很大）。"""
            if shown[i] is None:
                return True
            if c == shown[i]:
                return False
            change = max(abs(a - b) for a, b in zip(c, shown[i])) / 255
            waited = now - drawn_at[i]
            return (change >= BIG_CHANGE                                   # 大变化：立刻画
                    or (waited >= MIN_INTERVAL[i] and change >= MIN_CHANGE[i])   # 到了间隔，且变化明显
                    or waited >= 2.0)                                      # 小变化积累：最多 2 秒补画一次

        try:
            while not stop.is_set():
                now = time.monotonic()
                cols = painter.colors(analyzer, now)
                # 找到最外面一圈"该重画"的，从它开始往里重画（外圈的填充会盖住里面）
                outer = max((i for i in range(4) if due(i, cols[i], now)), default=-1)
                # 外圈的填充会盖住里面几圈，所以里面几圈必须跟着重画
                for i in range(outer, -1, -1):
                    x1, y1, x2, y2 = RINGS[i]
                    api.set_matrix_fill(x1, 7 - y1, x2, 7 - y2, color(cols[i]))   # 方环上下对称，翻转不影响
                    shown[i] = cols[i]
                    drawn_at[i] = time.monotonic()
                    cmds += 1
                    if i > 0:
                        # 画外圈要好几条命令；每画完一圈，就用最新的声音更新里面几圈的颜色，鼓点不掉拍
                        latest = painter.colors(analyzer, time.monotonic())
                        cols = latest[:i] + cols[i:]
                frames += 1
                if outer < 0:
                    time.sleep(0.01)
                now = time.monotonic()
                if now - t_stat >= 5:
                    print(f"\r刷新 {frames / (now - t_stat):4.1f} 帧/秒，蓝牙命令 {cmds / (now - t_stat):4.1f} 条/秒   ",
                          end="", flush=True)
                    frames, cmds, t_stat = 0, 0, now
        except KeyboardInterrupt:
            pass
        finally:
            api.clear_matrix()
    print("\n已清屏并断开")


# ================================================================ 主程序
def main():
    p = argparse.ArgumentParser(description="声之涟漪：BOLT 点阵随音乐跳动")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--file", help="播放并分析这个音频文件（mp3 / m4a / wav …）")
    src.add_argument("--demo", action="store_true", help="用内置的 120 BPM 节奏演示")
    src.add_argument("--device", help="录音设备的名字或编号（默认：系统默认麦克风）")
    p.add_argument("--list-devices", action="store_true", help="列出录音设备")
    p.add_argument("--gain", type=float, default=1.0, help="灵敏度，默认 1.0")
    p.add_argument("--preview", action="store_true", help="不连 BOLT，只在终端预览")
    a = p.parse_args()

    if a.list_devices:
        import sounddevice as sd
        print(sd.query_devices())
        return

    analyzer = Analyzer(gain=a.gain)
    painter = Painter()
    stop = threading.Event()
    closers = []

    def start():
        closers.append(start_source(a, analyzer, stop))

    try:
        if a.preview:
            start()
            run_preview(analyzer, painter, stop)
        else:
            run_bolt(analyzer, painter, stop, start)
    finally:
        stop.set()
        for close in closers:
            close()


if __name__ == "__main__":
    main()
