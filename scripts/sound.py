"""在电脑上播放声音（BOLT 没有扬声器）。

macOS：用系统自带的 afplay（音效）和 say（语音），不需要额外安装。
其他系统：只在终端里打印提示，不发声。
"""
import platform
import shutil
import subprocess

IS_MAC = platform.system() == "Darwin" and shutil.which("afplay") is not None
SYSTEM_SOUNDS = "/System/Library/Sounds"
# 可用音效：Basso Blow Bottle Frog Funk Glass Hero Morse Ping Pop Purr Sosumi Submarine Tink


def _find_zh_voice():
    """找一个中文语音（如 Tingting），找不到就用系统默认语音。"""
    if not IS_MAC:
        return None
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if "zh_CN" in line:
            return line.split("  ")[0].strip()
    return None


ZH_VOICE = _find_zh_voice()


def sound(name: str = "Glass") -> None:
    """播放系统音效，不阻塞。"""
    if IS_MAC:
        subprocess.Popen(["afplay", f"{SYSTEM_SOUNDS}/{name}.aiff"])
    else:
        print(f"[音效] {name}")


def say(text: str, wait: bool = False) -> None:
    """文字转语音。wait=True 时等说完再继续。"""
    if not IS_MAC:
        print(f"[语音] {text}")
        return
    cmd = ["say"] + (["-v", ZH_VOICE] if ZH_VOICE else []) + [text]
    p = subprocess.Popen(cmd)
    if wait:
        p.wait()
