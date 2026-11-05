"""Đọc và thực thi kịch bản click/swipe Quốc chiến từ file JSON."""

import json
import time
from pathlib import Path
from typing import Any


STRATEGY_DIR = Path(__file__).resolve().parent / "battle_strategies"


def list_battle_strategies() -> list[dict[str, str]]:
    """Liệt kê các kịch bản JSON hợp lệ để hiển thị trên giao diện."""
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    strategies = []
    for path in sorted(STRATEGY_DIR.glob("*.json"), key=lambda item: item.name.casefold()):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            name = str(data.get("display_name") or data.get("name") or path.stem).strip()
            description = str(data.get("description") or "").strip()
            steps = data.get("steps")
            if not isinstance(steps, list):
                continue
            strategies.append({
                "name": name,
                "description": description,
                "path": str(path.resolve()),
            })
        except (OSError, UnicodeError, json.JSONDecodeError):
            # Một file hỏng không được làm ảnh hưởng các chiến thuật còn lại.
            continue
    return strategies


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} phải là số nguyên >= {minimum}.")
    return value


def _validate_step(step: Any, index: int) -> dict:
    if not isinstance(step, dict):
        raise ValueError(f"Bước {index}: cấu hình phải là object.")
    action = step.get("type")
    delay = _integer(step.get("delay", 0), f"Bước {index}.delay")
    description = str(step.get("description") or "").strip()

    if action == "click":
        return {
            "type": "click",
            "x": _integer(step.get("x"), f"Bước {index}.x"),
            "y": _integer(step.get("y"), f"Bước {index}.y"),
            "delay": delay,
            "description": description,
        }
    if action == "swipe":
        source = step.get("from")
        target = step.get("to")
        if (
            not isinstance(source, list) or len(source) != 2
            or not isinstance(target, list) or len(target) != 2
        ):
            raise ValueError(
                f"Bước {index}: swipe cần from và to có dạng [x, y]."
            )
        return {
            "type": "swipe",
            "from": [
                _integer(source[0], f"Bước {index}.from[0]"),
                _integer(source[1], f"Bước {index}.from[1]"),
            ],
            "to": [
                _integer(target[0], f"Bước {index}.to[0]"),
                _integer(target[1], f"Bước {index}.to[1]"),
            ],
            "duration": _integer(step.get("duration"), f"Bước {index}.duration", minimum=1),
            "delay": delay,
            "description": description,
        }
    if action == "swipe_path":
        points = step.get("points")
        if not isinstance(points, list) or len(points) < 2:
            raise ValueError(f"Bước {index}: swipe_path cần ít nhất 2 điểm.")
        validated_points = []
        for point_index, point in enumerate(points, start=1):
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError(
                    f"Bước {index}.points[{point_index}]: tọa độ phải có dạng [x, y]."
                )
            validated_points.append([
                _integer(point[0], f"Bước {index}.points[{point_index}][0]"),
                _integer(point[1], f"Bước {index}.points[{point_index}][1]"),
            ])
        return {
            "type": "swipe_path",
            "points": validated_points,
            "repeat": _integer(step.get("repeat", 1), f"Bước {index}.repeat", minimum=1),
            "duration": _integer(step.get("duration"), f"Bước {index}.duration", minimum=1),
            "delay": delay,
            "description": description,
        }
    raise ValueError(
        f"Bước {index}: type không hỗ trợ {action!r}; nhận click, swipe hoặc swipe_path."
    )


def load_battle_strategy(strategy_path: str | Path) -> tuple[dict, list[dict]]:
    """Đọc và xác thực kịch bản; chỉ cho phép JSON trong battle_strategies."""
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(strategy_path).expanduser().resolve()
    try:
        path.relative_to(STRATEGY_DIR.resolve())
    except ValueError as exc:
        raise ValueError("File chiến thuật phải nằm trong battle_strategies.") from exc
    if path.suffix.lower() != ".json" or not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file chiến thuật: {path.name}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được JSON chiến thuật {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Nội dung JSON chiến thuật phải là object.")
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("Chiến thuật chưa có thao tác nào trong steps.")
    steps = [_validate_step(step, index) for index, step in enumerate(raw_steps, start=1)]
    return data, steps


def get_battle_step_progress_label(step: dict, index: int | None = None) -> str:
    """Dùng nguyên mô tả trong JSON làm nhãn tiến trình."""
    return str(step.get("description") or "")


def _wait(worker, seconds: float) -> bool:
    deadline = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < deadline:
        if not worker._wait_if_paused():
            return False
        time.sleep(min(0.05, deadline - time.monotonic()))
    return worker._wait_if_paused()


def run_battle_strategy(worker, device, strategy_path: str | Path) -> bool:
    """Thực thi tuần tự click/swipe và cập nhật riêng từng bước lên tiến trình."""
    data, steps = load_battle_strategy(strategy_path)
    strategy_name = str(data.get("name") or Path(strategy_path).stem)
    total = len(steps)
    worker.log_message.emit(
        f"Quốc chiến: chạy chiến thuật '{strategy_name}' ({total} thao tác)."
    )
    worker._emit_overall_progress(0, total, f"Chiến thuật: {strategy_name}")
    worker._emit_task_progress("Bắt đầu", "running", 0, 1)
    worker._emit_task_progress("Bắt đầu", "done", 1, 1)

    for index, step in enumerate(steps, start=1):
        progress_label = get_battle_step_progress_label(step, index)
        if not worker._wait_if_paused():
            worker.log_message.emit("Quốc chiến: đã dừng theo yêu cầu.")
            worker._emit_task_progress(
                progress_label, "stopped", 0, 1
            )
            return False

        worker._emit_task_progress(progress_label, "running", 0, 1)
        description = step["description"] or f"{step['type']} ({index}/{total})"
        try:
            if step["type"] == "click":
                x, y = step["x"], step["y"]
                worker.log_message.emit(
                    f"Quốc chiến [{index}/{total}]: click ({x}, {y}) — {description}."
                )
                device.shell(f"input tap {x} {y}")
                if step["delay"] and not _wait(worker, step["delay"] / 1000):
                    worker.log_message.emit("Quốc chiến: đã dừng theo yêu cầu.")
                    worker._emit_task_progress(progress_label, "stopped", 0, 1)
                    return False
            elif step["type"] == "swipe":
                x1, y1 = step["from"]
                x2, y2 = step["to"]
                duration = step["duration"]
                worker.log_message.emit(
                    f"Quốc chiến [{index}/{total}]: swipe ({x1}, {y1}) -> "
                    f"({x2}, {y2}) trong {duration} ms — {description}."
                )
                device.shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")
                if step["delay"] and not _wait(worker, step["delay"] / 1000):
                    worker.log_message.emit("Quốc chiến: đã dừng theo yêu cầu.")
                    worker._emit_task_progress(progress_label, "stopped", 0, 1)
                    return False
            else:
                points = step["points"]
                duration = step["duration"]
                repeat = step["repeat"]
                segment_total = (len(points) - 1) * repeat
                segment_index = 0
                for repeat_index in range(1, repeat + 1):
                    for point_index in range(len(points) - 1):
                        if not worker._wait_if_paused():
                            worker.log_message.emit("Quốc chiến: đã dừng theo yêu cầu.")
                            worker._emit_task_progress(progress_label, "stopped", 0, 1)
                            return False
                        x1, y1 = points[point_index]
                        x2, y2 = points[point_index + 1]
                        segment_index += 1
                        worker.log_message.emit(
                            f"Quốc chiến [{index}/{total}]: swipe path "
                            f"{segment_index}/{segment_total} (lượt {repeat_index}/{repeat}): "
                            f"({x1}, {y1}) -> ({x2}, {y2}) trong {duration} ms — {description}."
                        )
                        device.shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")
                        if step["delay"] and not _wait(worker, step["delay"] / 1000):
                            worker.log_message.emit("Quốc chiến: đã dừng theo yêu cầu.")
                            worker._emit_task_progress(progress_label, "stopped", 0, 1)
                            return False
        except Exception:
            worker._emit_task_progress(progress_label, "failed", 0, 1)
            raise

        worker._emit_task_progress(progress_label, "done", 1, 1)
        worker._emit_overall_progress(index, total, f"Quốc chiến: {index}/{total}")

    worker.log_message.emit(f"Quốc chiến: hoàn tất chiến thuật '{strategy_name}'.")
    worker._emit_task_progress("Kết thúc", "running", 0, 1)
    worker._emit_task_progress("Kết thúc", "done", 1, 1)
    return True
