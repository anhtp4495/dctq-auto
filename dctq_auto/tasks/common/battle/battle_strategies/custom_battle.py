"""Thực thi chiến thuật Giao Tranh được định nghĩa trong file JSON."""

import json
import time
from pathlib import Path
from typing import Any

from .base_battle import BaseBattle


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

    if action == "none":
        return {
            "type": "none",
            "delay": delay,
            "description": description,
        }

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
            "duration": _integer(
                step.get("duration"), f"Bước {index}.duration", minimum=1
            ),
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
                    f"Bước {index}.points[{point_index}]: "
                    "tọa độ phải có dạng [x, y]."
                )
            validated_points.append([
                _integer(
                    point[0], f"Bước {index}.points[{point_index}][0]"
                ),
                _integer(
                    point[1], f"Bước {index}.points[{point_index}][1]"
                ),
            ])

        return {
            "type": "swipe_path",
            "points": validated_points,
            "repeat": _integer(
                step.get("repeat", 1), f"Bước {index}.repeat", minimum=1
            ),
            "duration": _integer(
                step.get("duration"), f"Bước {index}.duration", minimum=1
            ),
            "hold": _integer(step.get("hold", 0), f"Bước {index}.hold"),
            "delay": delay,
            "description": description,
        }

    raise ValueError(
        f"Bước {index}: type không hỗ trợ {action!r}; "
        "nhận none, click, swipe hoặc swipe_path."
    )


def load_strategy(strategy_path: str | Path) -> tuple[dict, list[dict]]:
    """Đọc và xác thực file chiến thuật JSON."""
    if not strategy_path:
        raise ValueError("Chưa cấu hình battle_strategy_path.")

    path = Path(strategy_path).expanduser().resolve()
    if path.suffix.lower() != ".json" or not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file chiến thuật JSON: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Không đọc được JSON chiến thuật {path.name}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Nội dung JSON chiến thuật phải là object.")

    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("Chiến thuật chưa có thao tác nào trong steps.")

    steps = [
        _validate_step(step, index)
        for index, step in enumerate(raw_steps, start=1)
    ]
    return data, steps


class CustomBattle(BaseBattle):
    """Thực thi tuần tự các thao tác click/swipe được khai báo trong JSON."""

    def deploy(self, context) -> bool:
        account = context["account"]
        device = context["device"]
        log = context["log"]

        try:
            data, steps = load_strategy(context.get("battle_strategy_path"))
        except (OSError, ValueError) as exc:
            log(f"[{account.display_name}] Không tải được chiến thuật Giao Tranh: {exc}")
            return False

        strategy_name = str(
            data.get("display_name") or data.get("name")
            or Path(context["battle_strategy_path"]).stem
        )
        total = len(steps)
        log(
            f"[{account.display_name}] Bắt đầu chiến thuật "
            f"'{strategy_name}' ({total} bước)."
        )

        mark_started = context.get("mark_battle_started")
        battle_started = False

        for index, step in enumerate(steps, start=1):
            action = step["type"]
            description = step["description"] or action
            delay = step["delay"]

            if action == "none":
                log(
                    f"[{account.display_name}] Chiến thuật [{index}/{total}]: "
                    f"None — chờ {delay} ms — {description}."
                )
                if delay:
                    time.sleep(delay / 1000)
                continue

            if not battle_started:
                if mark_started:
                    mark_started()
                battle_started = True

            if action == "click":
                x, y = step["x"], step["y"]
                log(
                    f"[{account.display_name}] Chiến thuật [{index}/{total}]: "
                    f"click ({x}, {y}) — {description}."
                )
                device.shell(f"input tap {x} {y}")
                if delay:
                    time.sleep(delay / 1000)
                continue

            if action == "swipe":
                x1, y1 = step["from"]
                x2, y2 = step["to"]
                duration = step["duration"]
                log(
                    f"[{account.display_name}] Chiến thuật [{index}/{total}]: "
                    f"swipe ({x1}, {y1}) -> ({x2}, {y2}) trong "
                    f"{duration} ms — {description}."
                )
                device.shell(
                    f"input swipe {x1} {y1} {x2} {y2} {duration}"
                )
                if delay:
                    time.sleep(delay / 1000)
                continue

            points = step["points"]
            duration = step["duration"]
            hold = step["hold"]
            repeat = step["repeat"]
            segment_total = (len(points) - 1) * repeat
            segment_index = 0
            for repeat_index in range(1, repeat + 1):
                for point_index in range(len(points) - 1):
                    x1, y1 = points[point_index]
                    x2, y2 = points[point_index + 1]
                    segment_index += 1
                    should_hold = hold > 0 and repeat_index == 1 and point_index == 0
                    hold_log = f", giữ {hold} ms" if should_hold else ""
                    log(
                        f"[{account.display_name}] Chiến thuật [{index}/{total}]: "
                        f"swipe_path {segment_index}/{segment_total} "
                        f"(lượt {repeat_index}/{repeat}): ({x1}, {y1}) -> "
                        f"({x2}, {y2}) trong {duration} ms"
                        f"{hold_log} — {description}."
                    )

                    if should_hold:
                        # Giữ pointer DOWN liên tục rồi mới MOVE để game nhận
                        # thao tác nhấn giữ-kéo; các lượt repeat sau không hold.
                        move_count = max(1, min(60, duration // 16))
                        commands = [
                            "sdk=$(getprop ro.build.version.sdk)",
                            'if [ "$sdk" -le 29 ]; then event=event; else event=motionevent; fi',
                            f'input "$event" DOWN {x1} {y1}',
                            f"sleep {hold / 1000:.3f}",
                        ]
                        for move_index in range(1, move_count + 1):
                            ratio = move_index / move_count
                            move_x = round(x1 + (x2 - x1) * ratio)
                            move_y = round(y1 + (y2 - y1) * ratio)
                            commands.append(
                                f'input "$event" MOVE {move_x} {move_y}'
                            )
                            if move_index < move_count:
                                commands.append(
                                    f"sleep {duration / move_count / 1000:.3f}"
                                )
                        commands.append(f'input "$event" UP {x2} {y2}')
                        device.shell("; ".join(commands))
                    else:
                        device.shell(
                            f"input swipe {x1} {y1} {x2} {y2} {duration}"
                        )

                    if delay:
                        time.sleep(delay / 1000)

        log(
            f"[{account.display_name}] Hoàn tất chiến thuật "
            f"'{strategy_name}'."
        )
        return True
