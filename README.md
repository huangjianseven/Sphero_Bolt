# Sphero_Bolt
接管Sphero_Bolt编程球

## 文档

1. [第一步：取得 Sphero BOLT 的控制权](docs/01-取得控制权方案.md)

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
```

运行前请关闭 Sphero Edu App（蓝牙同一时间只能连一台主机）。
默认连接 `SB-8EE3`，可用环境变量 `BOLT_NAME` 修改。
