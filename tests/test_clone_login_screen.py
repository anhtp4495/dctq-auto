"""Regression tests for Clone login-screen OCR detection."""

from dctq_auto.gui.workers import BotWorker


def test_login_screen_detected_from_form_labels():
    assert BotWorker._is_login_screen(
        "Tên đăng nhập, số điện thoại hoặc email   Mật khẩu   ĐĂNG NHAP"
    )


def test_login_screen_detected_when_ocr_only_reads_navigation_links():
    # Representative noisy OCR from the user's actual login screen.
    text = "v1 4 27 s002 s j as ow dang ky js v a 4 quen mat khau a or wy 9 xa"
    assert BotWorker._is_login_screen(text)


def test_login_screen_rejects_only_one_navigation_hint():
    assert not BotWorker._is_login_screen("dang ky")
    assert not BotWorker._is_login_screen("quen mat khau")


def test_login_screen_rejects_unrelated_game_screen():
    assert not BotWorker._is_login_screen("chien truong ban do phan thuong")



class FakeDevice:
    def __init__(self):
        self.commands = []

    def shell(self, command):
        self.commands.append(command)
        return ""


def test_clear_focused_text_selects_all_then_deletes():
    device = FakeDevice()

    BotWorker._clear_focused_text(device)

    assert device.commands == [
        "input keycombination KEYCODE_CTRL_LEFT KEYCODE_A",
        "input keyevent KEYCODE_DEL",
    ]
