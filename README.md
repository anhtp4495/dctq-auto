# DCTQ Auto

Python desktop application scaffold for Đại Chiến Tam Quốc running in an Android emulator. It uses ADB APIs for device interaction rather than physical mouse/keyboard input.

## Requirements

- Python 3.11 or newer (the current setup can use Python 3.13)
- Android emulator with ADB enabled (for example, LDPlayer)
- PySide6 for the Windows desktop GUI

## Setup (Windows Command Prompt / CMD)

Open **Command Prompt** and change to the project directory:

```bat
cd /d I:\work\dctq-auto
py --version
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

You do not need to activate the virtual environment; the commands above call its Python executable directly.

If `copy .env.example .env` reports that the destination already exists, keep your existing `.env` file rather than overwriting your settings.

## Run without connecting a device

Start the GUI using the command above. Trong dropdown **Thiết bị**, chọn **Chạy thử (không cần thiết bị)** để chạy thử mà không kết nối ADB hoặc điều khiển game. Dropdown này cũng liệt kê các thiết bị ADB online sau khi nhấn **Quét ADB**.

Chế độ chạy thử thực hiện luồng nhiệm vụ đã cấu hình trên GUI: Giao tranh, Tranh bá, điểm danh, báo danh quân đoàn, đóng góp KNB, thăm dò lãnh địa, Lưu Ly Tháp (có thể chọn số lần và mua lượt bằng KNB) và thiết lập mưu binh. Nhật ký/tiến trình thể hiện các bước chạy thử; đây chưa phải gameplay thật và không xác nhận thao tác nào đã xảy ra trong game. Có thể thử tạm dừng, tiếp tục và dừng hẳn.

## Connect the Android emulator

Choose **ADB (chuẩn bị thiết bị)** in the GUI to use ADB. Make sure ADB is enabled in the emulator. In CMD, check that ADB can see the device:

```bat
adb devices
```

If the emulator requires connecting to a local ADB endpoint, use the address and port configured by your emulator, for example:

```bat
adb connect 127.0.0.1:5555
adb devices
```

If you use an explicit device serial, set `ADB_SERIAL` in the `.env` file, for example:

```dotenv
ADB_SERIAL=127.0.0.1:5555
```

The address and port above are only an example; use the endpoint shown by your emulator. If `adb` is not recognized, add the Android SDK platform-tools directory (or your emulator's ADB directory) to PATH, or run the emulator's `adb.exe` by its full path.

## Run the GUI

From the project directory in CMD:

```bat
.venv\Scripts\python.exe -m dctq_auto
```

The GUI has three tabs:

- **Nhiệm vụ hằng ngày**: Giao tranh (default 15), Tranh bá (default 6), Điểm danh (enabled by default), and Báo danh quân đoàn (enabled by default).
- **Mưu binh**: Thiết lập mưu binh (enabled by default).
- **Quốc chiến**: empty placeholder for future configuration.

The shared **Bắt đầu** and **Dừng** controls and activity log are below the tabs. Configuration remains in the widgets when switching tabs. Số trận Giao tranh nhận từ 1 đến 60; Tranh bá từ 1 đến 15.

**Important:** ADB mode currently checks ADB connectivity and captures one screenshot; it does not perform real in-game tasks yet. Chế độ chạy thử không điều khiển game thật. The **Dừng hẳn** button requests a cooperative stop at the next check point and does not forcibly terminate a running thread.

## Layout

- `dctq_auto/gui/`: PySide6 main window and background worker
- `dctq_auto/adb/`: ADB connection and device operations
- `dctq_auto/vision/`: screenshot loading and template matching
- `dctq_auto/automation/`: bot orchestration and state handling
- `dctq_auto/config/`: environment-based settings
- `tests/`: unit tests
