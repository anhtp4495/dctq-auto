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

The GUI has four tabs:

- **Nhiệm vụ hằng ngày**: Giao tranh (default 15), Tranh bá (default 6), Điểm danh (enabled by default), and Báo danh quân đoàn (enabled by default).
- **Mưu binh**: Thiết lập mưu binh (enabled by default).
- **Quốc chiến**: placeholder for future configuration.
- **Clone**: chọn file TXT chứa tài khoản và bật/tắt Đăng nhập, Điểm danh, Báo danh quân đoàn, Nhận túi phúc, Đăng xuất. Mỗi dòng file TXT có dạng `username|password`; dòng trống và dòng bắt đầu bằng `#` được bỏ qua. Mật khẩu được giữ trong bộ nhớ khi đọc file và không được ghi vào nhật ký. File chứa mật khẩu dạng văn bản thuần nên cần được bảo vệ.

The shared **Bắt đầu**, **Tạm dừng**, **Dừng hẳn** controls and activity log are below the tabs. Configuration remains in the widgets when switching tabs. Số trận Giao tranh nhận từ 1 đến 60; Tranh bá từ 1 đến 15.

**Important:** Các nhiệm vụ Clone hiện mới có giao diện, đọc/kiểm tra danh sách tài khoản và mô phỏng thứ tự chạy. Trong chế độ ADB, ứng dụng chưa tự đăng nhập, điểm danh, báo danh quân đoàn, nhận túi phúc hoặc đăng xuất. ADB mode của các tab hiện tại cũng chỉ kiểm tra kết nối và chụp screenshot; chưa thực hiện gameplay thật. Chế độ chạy thử không điều khiển game thật. The **Dừng hẳn** button requests a cooperative stop at the next check point and does not forcibly terminate a running thread.

## Layout

- `dctq_auto/gui/`: PySide6 main window and background worker
- `dctq_auto/adb/`: ADB connection and device operations
- `dctq_auto/vision/`: screenshot loading and template matching
- `dctq_auto/automation/`: bot orchestration and state handling
- `dctq_auto/config/`: environment-based settings
- `tests/`: unit tests

## Build a single Windows EXE

Build on Windows (the EXE is platform-specific). From the repository folder, install dependencies if needed, then run:

```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
build_windows.bat
```

When the build completes, the executable is created at `dist\DCTQ-Auto.exe`. You can copy that EXE to another Windows machine. The first launch may take longer because PyInstaller extracts bundled files.

The EXE does not include an Android emulator. ADB mode still requires an emulator/device and a usable `adb.exe` available to the application (for example, through PATH). The current ADB mode only connects and captures a screenshot; it does not perform real in-game tasks yet. Build and test the EXE on Windows; a successful build has not been verified by this repository change.


## Chụp và đánh dấu tọa độ nút Clone

Hai script hỗ trợ khảo sát giao diện bằng tay; chúng **chỉ chụp/đọc ảnh và lưu tọa độ, không tự bấm nút trong game**. Chạy lệnh từ thư mục gốc repo sau khi cài requirements.

1. Mở LDPlayer và đưa game đến màn hình muốn khảo sát. Kiểm tra serial bằng `adb devices`.
2. Chụp màn hình:

   ```bat
   .venv\\Scripts\\python.exe scripts\\capture_screen.py --serial emulator-5554
   ```

   Ảnh mặc định được lưu trong `artifacts/screenshots/`. Nếu serial của máy là địa chỉ/port khác, thay `emulator-5554` bằng serial thực tế.

3. Mở ảnh để chọn tâm từng nút. Ví dụ với màn hình đăng nhập:

   ```bat
   .venv\\Scripts\\python.exe scripts\\analyze_screen.py --image artifacts\\screenshots\\emulator-5554_YYYYMMDD_HHMMSS.png --screen login
   ```

   Nhấp chuột vào tâm mỗi nút, nhấn **ESC** để kết thúc chọn điểm, sau đó nhập tên tương ứng (ví dụ `username`, `password`, `login_button`). Dùng tên màn hình khác như `main` để lưu nhóm tọa độ khác.

4. Kết quả được lưu vào `dctq_auto/tasks/clone/locations.json`. Mỗi nút có tọa độ tỷ lệ `x`/`y` trong khoảng 0..1 để dễ quy đổi độ phân giải, kèm `x_px`/`y_px` tham chiếu pixel trên ảnh gốc. Mỗi lần phân tích, nhóm màn hình có cùng tên sẽ được cập nhật.

Lưu ý: cửa sổ phân tích cần môi trường desktop có hỗ trợ OpenCV GUI. Tọa độ ban đầu phải được kiểm tra trực quan trước khi dùng cho bất kỳ thao tác tự động nào.
