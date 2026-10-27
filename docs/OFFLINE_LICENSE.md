# Quản lý License offline cho DCTQ Auto

## Cơ chế

- App xác minh chữ ký Ed25519 hoàn toàn offline.
- Mỗi file `.lic` được ràng buộc với mã thiết bị và ngày hết hạn.
- Ngày hết hạn được tính bao gồm cả ngày ghi trong License.
- License được lưu tại `%APPDATA%\DCTQAuto\license.lic` trên Windows.
- Không có máy chủ kích hoạt hoặc cơ chế thu hồi từ xa. Muốn khóa License đã cấp, cần cấp bản app mới với quy trình/khóa mới; các License đã ký vẫn có hiệu lực đến ngày hết hạn trên máy được cấp.

## Cài đặt

Cài các phụ thuộc như thông thường:

```powershell
python -m pip install -r requirements.txt
```

## Cấp License thủ công

1. Người dùng mở app và gửi cho bạn mã thiết bị hiển thị trong hộp thoại kích hoạt.
2. Giữ khóa riêng Ed25519 ở nơi an toàn, ngoài repository và ngoài thư mục phát hành app.
3. Chạy lệnh dưới đây, thay mã thiết bị, ngày hết hạn và đường dẫn khóa riêng:

```powershell
python scripts/issue_license.py --device-id "MA_THIET_BI" --expires-on 2026-12-31 --private-key "D:\secure\dctq_auto_license_private_key.pem" --output "khach-hang.lic" --customer "Khach hang"
```

4. Gửi file `khach-hang.lic` cho đúng người dùng. Người dùng chọn file đó trong hộp thoại kích hoạt.

## Bảo mật khóa riêng

- **Không commit, gửi kèm bản build, hoặc chia sẻ khóa riêng cho khách hàng.**
- Nếu khóa riêng bị lộ, người khác có thể tự cấp License giả mà app vẫn chấp nhận. Cần tạo cặp khóa mới, thay khóa công khai trong `dctq_auto/licensing.py`, build và phát hành phiên bản app mới.
- Vì đây là hệ thống offline, không thể thu hồi ngay một License đã cấp hoặc đảm bảo chống sao chép máy ảo/giả mạo định danh phần cứng tuyệt đối.
