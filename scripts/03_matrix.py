"""Step 3：8x8 LED 点阵——滚动文字、单个字符、逐点画图。

通过标准：滚动显示 "HI BOLT" → 显示字符 "A" → 画出一个笑脸。
"""
import time

from common import find_bolt
from spherov2.sphero_edu import SpheroEduAPI
from spherov2.types import Color

WHITE = Color(255, 255, 255)
YELLOW = Color(255, 200, 0)
BLACK = Color(0, 0, 0)

# 8x8 笑脸，1 = 点亮
SMILE = [
    "00111100",
    "01000010",
    "10100101",
    "10000001",
    "10100101",
    "10011001",
    "01000010",
    "00111100",
]

toy = find_bolt()
with SpheroEduAPI(toy) as api:
    print("滚动文字")
    text = "HI BOLT"
    api.scroll_matrix_text(text, WHITE, fps=10, wait=True)
    # 注意：spherov2 目前没有实现 wait 参数，这里手动等待滚动结束
    time.sleep(len(text) * 0.8 + 1)

    print("显示单个字符")
    api.set_matrix_character("A", YELLOW)
    time.sleep(2)

    print("逐点画笑脸")
    api.clear_matrix()
    for y, row in enumerate(SMILE):
        for x, bit in enumerate(row):
            if bit == "1":
                api.set_matrix_pixel(x, y, YELLOW)
    time.sleep(3)
    api.clear_matrix()

print("完成")
