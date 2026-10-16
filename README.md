# DCTQ Auto

Python automation scaffold for Đại Chiến Tam Quốc running in an Android emulator. It uses ADB APIs for device interaction rather than physical mouse/keyboard input.

## Requirements

- Python 3.11+
- Android emulator with ADB enabled (for example, LDPlayer)

## Setup

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Connect the emulator and verify that ADB can see it, then run:

```powershell
python -m dctq_auto
```

The initial entry point connects to the device and saves a screenshot to `artifacts/screenshots/current_screen.png`. Game-specific state handling is not implemented yet.

## Layout

- `dctq_auto/adb/`: ADB connection and device operations
- `dctq_auto/vision/`: screenshot loading and template matching
- `dctq_auto/automation/`: bot orchestration and state handling
- `dctq_auto/config/`: environment-based settings
- `tests/`: unit tests
