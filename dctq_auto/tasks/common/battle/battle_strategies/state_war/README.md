# Chiến thuật Quốc chiến

Mỗi file `.json` trong thư mục này là một chiến thuật và sẽ xuất hiện trong danh sách ở tab **Quốc chiến**. Sau khi thêm/sửa file, nhấn nút tải lại danh sách trên giao diện.

## Cấu trúc

```json
{
  "name": "Tên chiến thuật",
  "description": "Mô tả ngắn",
  "steps": [
    {
      "type": "click",
      "x": 500,
      "y": 800,
      "delay": 200,
      "description": "Chọn vị trí võ tướng"
    },
    {
      "type": "swipe",
      "from": [500, 800],
      "to": [900, 500],
      "duration": 1000,
      "delay": 300,
      "description": "Kéo triển khai quân"
    }
  ]
}
```

- `click`: cần `x`, `y`; `delay` là thời gian nghỉ sau thao tác, tính bằng mili giây.
- `swipe`: cần `from`, `to` theo dạng `[x, y]`; `duration` là thời gian rê, tính bằng mili giây; `delay` là thời gian nghỉ sau thao tác.
- Các bước được thực thi tuần tự. Chỉ hỗ trợ `click` và `swipe`.
- Dùng tọa độ theo độ phân giải Android/LDPlayer; kiểm tra tọa độ trước khi chạy thật.

Hiện tại cần mở sẵn màn hình Quốc chiến trong game trước khi chạy chiến thuật. Tọa độ mở/đóng màn hình chưa có trong `regions.json`, nên hai task điều hướng đang là điểm mở rộng an toàn, chưa tự click.
