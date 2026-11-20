# Sphero_Bolt
接管Sphero_Bolt编程球

## 文档

1. [第一步：取得 Sphero BOLT 的控制权](docs/01-取得控制权方案.md)
2. [Step 1–7 测试报告（2026-11-20）](docs/02-测试报告.md)

## 快速开始

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cd scripts
python 01_scan.py            # 扫描，确认能看到 SB-8EE3
python 02_hello_led.py       # 点亮 LED
python 03_matrix.py          # 点阵文字 / 笑脸
python 04_move.py            # 运动（放在地上！）
python 05_sensors.py         # 读传感器
python 06_keyboard_drive.py  # 键盘遥控
python 07_sound.py           # 带音效的遥控（BOLT 无扬声器，声音由 Mac 播放）
python 08_compass.py         # 罗盘校准，并依次指向 北/东/南/西
caffeinate -i python 09_alarm.py --in 2   # 闹钟测试：2 分钟后响（正式用 --time 08:00）
python 10_scroll_text.py     # 输入英文，在点阵上滚动显示
```

> **Python 版本**：请用 3.10 – 3.12（已验证 3.12.16）。Python 3.15 与 `spherov2 0.12.1` 不兼容。

运行前请关闭 Sphero Edu App（蓝牙同一时间只能连一台主机）。
默认连接 `SB-8EE3`，可用环境变量 `BOLT_NAME` 修改。
