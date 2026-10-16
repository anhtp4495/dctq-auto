# DCTQ Auto
1
Python desktop application scaffold for Đại Chiến Tam Quốc running in an Android emulator. It uses ADB APIs for device interaction rather than physical mouse/keyboard input.

## Requirements

- Python 3.11+
- Android emulator with ADB enabled (for example, LDPlayer)
- PySide6 for the Windows desktop GUI

## Setup (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Connect the emulator and verify that ADB can see it, then run:

```powershell
python -m dctq_auto
```

The GUI has three tabs:

- **Nhiệm vụ hằng ngày**: Giao tranh (default 15), Tranh bá (default 6), Điểm danh (enabled by default), and Báo danh quân đoàn (enabled by default).
- **Mưu binh**: Thiết lập mưu binh (enabled by default).
- **Quốc chiến**: empty placeholder for future configuration.

The shared **Bắt đầu** and **Dừng** controls and activity log are below the tabs. Configuration remains in the widgets when switching tabs. The battle counts accept values from 0 to 999, so negative values cannot be entered.

**Important:** The background worker currently checks ADB connectivity and captures one screenshot. It logs the selected configuration but does not perform in-game tasks; game-specific behavior must be implemented after its rules are defined. The Stop button requests a cooperative stop at the next check point and does not forcibly terminate a running thread.

## Layout

- `dctq_auto/gui/`: PySide6 main window and background worker
- `dctq_auto/adb/`: ADB connection and device operations
- `dctq_auto/vision/`: screenshot loading and template matching
- `dctq_auto/automation/`: bot orchestration and state handling
- `dctq_auto/config/`: environment-based settings
- `tests/`: unit tests
