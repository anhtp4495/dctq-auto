# Chiến thuật Quốc chiến

Mỗi file `.json` trong thư mục này là một chiến thuật và sẽ xuất hiện trong danh sách ở tab **Quốc chiến**. Sau khi thêm/sửa file, nhấn nút tải lại danh sách trên giao diện.

Thư mục: `common/battle/battle_strategies/state_war/`.

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
    },
    {
      "type": "swipe_path",
      "points": [[100, 200], [300, 400], [500, 200]],
      "repeat": 2,
      "duration": 300,
      "delay": 100,
      "description": "Di chuyển theo đường"
    },
    {
      "type": "none",
      "delay": 500,
      "description": "Chờ"
    }
  ]
}
```

- `click`: cần `x`, `y`; `delay` là thời gian nghỉ sau thao tác, tính bằng mili giây.
- `swipe`: cần `from`, `to` theo dạng `[x, y]`; `duration` là thời gian rê; `delay` là thời gian nghỉ sau thao tác.
- `swipe_path`: cần ít nhất hai điểm trong `points`; `repeat` là số lượt lặp, `duration` là thời gian rê mỗi đoạn và `delay` là thời gian nghỉ sau mỗi đoạn.
- `none`: chỉ chờ theo `delay`, không thực hiện thao tác chạm.
- Các bước được thực thi tuần tự. Tất cả thời gian tính bằng mili giây.
- Dùng tọa độ theo độ phân giải Android/LDPlayer; kiểm tra tọa độ trước khi chạy thật.

Hiện tại cần mở sẵn màn hình Quốc chiến trong game trước khi chạy chiến thuật.