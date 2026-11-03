"""Giao diện cấu hình chạy lần lượt các tài khoản clone."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QGroupBox,
    QButtonGroup,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from dctq_auto.tasks.common.accounts import load_accounts
from dctq_auto.tasks.clone.step_registry import get_clone_step_registry
from dctq_auto.tasks.common.battle.battle_config import BattleConfig


class CloneTab(QWidget):
    """Chọn file tài khoản và các nhiệm vụ cần thực hiện cho mỗi tài khoản."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        step_registry = get_clone_step_registry()
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        intro = QLabel(
            "Chạy lần lượt các tài khoản trong file INI. Tài khoản ở [DisabledAccounts] "
            "được giữ trong danh sách nhưng sẽ không chạy."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        file_row = QHBoxLayout()
        self.account_file_combo = QComboBox()
        self.account_file_combo.setMinimumContentsLength(12)
        self.account_file_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.account_file_combo.setToolTip("Chọn file tài khoản đã dùng trước đây")
        self.account_file_combo.currentIndexChanged.connect(self._update_account_status)
        self.account_file_combo.currentIndexChanged.connect(self._show_selected_file_path)
        self.account_file_combo.activated.connect(self._show_selected_file_path)
        file_row.addWidget(self.account_file_combo, 1)
        self.browse_button = QPushButton("Chọn file…")
        self.browse_button.clicked.connect(self._browse_file)
        file_row.addWidget(self.browse_button)
        layout.addLayout(file_row)

        self.account_status = QLabel("Chưa chọn file tài khoản.")
        self.account_status.setWordWrap(True)
        layout.addWidget(self.account_status)

        tasks_label = QLabel("Nhiệm vụ cho mỗi tài khoản")
        tasks_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(tasks_label)

        phuc_loi_group = QGroupBox("Hoạt động - Phúc lợi")
        phuc_loi_layout = QVBoxLayout(phuc_loi_group)
        self.clone_daily_check_in = QCheckBox(
            step_registry.get_display_name_by_config_key("clone_daily_check_in", "Điểm danh")
        )
        self.clone_daily_check_in.setChecked(True)
        self.clone_receive_quoc_van = QCheckBox(
            step_registry.get_display_name_by_config_key(
                "clone_receive_quoc_van", "Nhận lễ bao quốc vận"
            )
        )
        self.clone_receive_quoc_van.setChecked(False)
        phuc_loi_layout.addWidget(self.clone_receive_quoc_van)
        phuc_loi_layout.addWidget(self.clone_daily_check_in)
        layout.addWidget(phuc_loi_group)

        guild_group = QGroupBox("Quân đoàn")
        guild_layout = QVBoxLayout(guild_group)
        self.clone_guild_check_in = QCheckBox(
            step_registry.get_display_name_by_config_key(
                "clone_guild_check_in", "Báo danh quân đoàn"
            )
        )
        self.clone_guild_check_in.setChecked(True)
        self.clone_receive_lucky_bag = QCheckBox(
            step_registry.get_display_name_by_config_key(
                "clone_receive_lucky_bag", "Nhận túi phúc"
            )
        )
        self.clone_receive_lucky_bag.setChecked(True)
        self.clone_guild_fortune = QCheckBox(
            step_registry.get_display_name_by_config_key(
                "clone_guild_fortune", "Cầu vận quân đoàn (5 lần)"
            )
        )
        self.clone_guild_donate_knb = QCheckBox(
            step_registry.get_display_name_by_config_key(
                "clone_guild_donate_knb", "Đóng góp KNB"
            )
        )
        self.clone_guild_donate_rations = QCheckBox(
            step_registry.get_display_name_by_config_key(
                "clone_guild_donate_rations", "Đóng góp Lương Thảo"
            )
        )
        for checkbox in (
            self.clone_guild_check_in,
            self.clone_receive_lucky_bag,
            self.clone_guild_fortune,
            self.clone_guild_donate_knb,
            self.clone_guild_donate_rations,
        ):
            guild_layout.addWidget(checkbox)
        layout.addWidget(guild_group)

        shop_group = QGroupBox("Cửa hàng")
        shop_layout = QVBoxLayout(shop_group)
        self.clone_buy_fortune_lot = QCheckBox(
            step_registry.get_display_name_by_config_key(
                "clone_buy_fortune_lot", "Cửa hàng Danh Vọng - Mua quẻ lành"
            )
        )
        shop_layout.addWidget(self.clone_buy_fortune_lot)
        layout.addWidget(shop_group)
        war_group = QGroupBox("Chiến tranh")
        war_layout = QVBoxLayout(war_group)
        self.clone_quan_su_giao_tranh = QCheckBox(
            step_registry.get_display_name_by_config_key(
                "clone_quan_su_giao_tranh", "Chiến tranh - Giao tranh"
            )
        )
        war_layout.addWidget(self.clone_quan_su_giao_tranh)

        battle_count_row = QHBoxLayout()
        battle_count_row.addWidget(QLabel("Số trận:"))
        self.clone_battle_count = QSpinBox()
        self.clone_battle_count.setRange(1, 60)
        self.clone_battle_count.setValue(6)
        self.clone_battle_count.setKeyboardTracking(False)
        battle_count_row.addWidget(self.clone_battle_count)
        battle_count_row.addStretch(1)
        war_layout.addLayout(battle_count_row)

        self.clone_battle_mode_group = QButtonGroup(self)
        self.clone_battle_mode_group.setExclusive(True)
        self.clone_battle_mode_time_limit = QCheckBox("Thời gian tối đa")
        self.clone_battle_mode_fast = QCheckBox("Nhanh 1 cờ")
        self.clone_battle_mode_normal = QCheckBox("Bình thường")
        self.clone_battle_mode_group.addButton(self.clone_battle_mode_fast, 1)
        self.clone_battle_mode_group.addButton(self.clone_battle_mode_normal, 2)
        self.clone_battle_mode_group.addButton(self.clone_battle_mode_time_limit, 3)
        self.clone_battle_mode_time_limit.setChecked(True)

        battle_mode_row = QHBoxLayout()
        battle_mode_row.addWidget(QLabel("Chế độ:"))
        battle_mode_row.addWidget(self.clone_battle_mode_time_limit)
        self.clone_battle_time_limit = QSpinBox()
        self.clone_battle_time_limit.setRange(1, 180)
        self.clone_battle_time_limit.setValue(45)
        self.clone_battle_time_limit.setSuffix(" giây")
        self.clone_battle_time_limit.setKeyboardTracking(False)
        battle_mode_row.addWidget(self.clone_battle_time_limit)
        battle_mode_row.addStretch(1)
        war_layout.addLayout(battle_mode_row)

        battle_mode_fast_row = QHBoxLayout()
        battle_mode_fast_row.addSpacing(47)
        battle_mode_fast_row.addWidget(self.clone_battle_mode_fast)
        battle_mode_fast_row.addStretch(1)
        war_layout.addLayout(battle_mode_fast_row)

        battle_mode_normal_row = QHBoxLayout()
        battle_mode_normal_row.addSpacing(47)
        battle_mode_normal_row.addWidget(self.clone_battle_mode_normal)
        battle_mode_normal_row.addStretch(1)
        war_layout.addLayout(battle_mode_normal_row)

        self.clone_battle_mode_time_limit.toggled.connect(
            self.clone_battle_time_limit.setEnabled
        )
        self.clone_battle_time_limit.setEnabled(True)

        self.clone_battle_mode_hint = QLabel()
        self.clone_battle_mode_hint.setWordWrap(True)
        self.clone_battle_mode_hint.setStyleSheet("color: #777;")
        war_layout.addWidget(self.clone_battle_mode_hint)

        battle_mode_hints = {
            1: "Chỉ cần thắng trận là kết thúc.",
            2: "Giao tranh đến khi tiêu diệt hết mục tiêu.",
            3: "Giới hạn thời gian trận giao tranh.",
        }
        for mode_id, hint in battle_mode_hints.items():
            self.clone_battle_mode_group.button(mode_id).toggled.connect(
                lambda checked, text=hint: (
                    self.clone_battle_mode_hint.setText(text) if checked else None
                )
            )
        self.clone_battle_mode_hint.setText(
            battle_mode_hints[self.clone_battle_mode_group.checkedId()]
        )

        self.clone_quan_su_tranh_ba = QCheckBox(
            step_registry.get_display_name_by_config_key(
                "clone_quan_su_tranh_ba", "Chiến tranh - Tranh Bá"
            )
        )
        war_layout.addWidget(self.clone_quan_su_tranh_ba)

        ranked_battle_count_row = QHBoxLayout()
        ranked_battle_count_label = QLabel("Số trận:")
        ranked_battle_count_row.addWidget(ranked_battle_count_label)
        self.clone_ranked_battle_count = QSpinBox()
        self.clone_ranked_battle_count.setRange(1, 15)
        self.clone_ranked_battle_count.setValue(6)
        self.clone_ranked_battle_count.setKeyboardTracking(False)
        ranked_battle_count_row.addWidget(self.clone_ranked_battle_count)
        ranked_battle_count_row.addStretch(1)
        war_layout.addLayout(ranked_battle_count_row)

        self.clone_ranked_battle_refill = QCheckBox(
            "Mua lượt Tranh Bá (KNB)"
        )
        self.clone_ranked_battle_refill.setChecked(False)

        ranked_battle_refill_row = QHBoxLayout()
        ranked_battle_refill_row.addSpacing(47)
        ranked_battle_refill_row.addWidget(self.clone_ranked_battle_refill)
        ranked_battle_refill_row.addStretch(1)
        war_layout.addLayout(ranked_battle_refill_row)

        self.clone_ranked_battle_mode_group = QButtonGroup(self)
        self.clone_ranked_battle_mode_group.setExclusive(True)
        self.clone_ranked_battle_mode_time_limit = QCheckBox("Thời gian tối đa")
        self.clone_ranked_battle_mode_fast = QCheckBox("Nhanh 1 cờ")
        self.clone_ranked_battle_mode_normal = QCheckBox("Bình thường")
        self.clone_ranked_battle_mode_group.addButton(self.clone_ranked_battle_mode_fast, 1)
        self.clone_ranked_battle_mode_group.addButton(self.clone_ranked_battle_mode_normal, 2)
        self.clone_ranked_battle_mode_group.addButton(self.clone_ranked_battle_mode_time_limit, 3)
        self.clone_ranked_battle_mode_time_limit.setChecked(True)

        ranked_battle_time_row = QHBoxLayout()
        ranked_battle_mode_label = QLabel("Chế độ:")
        ranked_battle_time_row.addWidget(ranked_battle_mode_label)
        ranked_battle_time_row.addWidget(self.clone_ranked_battle_mode_time_limit)
        self.clone_ranked_battle_time_limit = QSpinBox()
        self.clone_ranked_battle_time_limit.setRange(1, 180)
        self.clone_ranked_battle_time_limit.setValue(45)
        self.clone_ranked_battle_time_limit.setSuffix(" giây")
        self.clone_ranked_battle_time_limit.setKeyboardTracking(False)
        ranked_battle_time_row.addWidget(self.clone_ranked_battle_time_limit)
        ranked_battle_time_row.addStretch(1)
        war_layout.addLayout(ranked_battle_time_row)

        ranked_battle_fast_row = QHBoxLayout()
        ranked_battle_fast_row.addSpacing(47)
        ranked_battle_fast_row.addWidget(self.clone_ranked_battle_mode_fast)
        ranked_battle_fast_row.addStretch(1)
        war_layout.addLayout(ranked_battle_fast_row)

        ranked_battle_normal_row = QHBoxLayout()
        ranked_battle_normal_row.addSpacing(47)
        ranked_battle_normal_row.addWidget(self.clone_ranked_battle_mode_normal)
        ranked_battle_normal_row.addStretch(1)
        war_layout.addLayout(ranked_battle_normal_row)

        self.clone_ranked_battle_mode_time_limit.toggled.connect(
            self.clone_ranked_battle_time_limit.setEnabled
        )
        self.clone_ranked_battle_time_limit.setEnabled(True)

        self.clone_ranked_battle_mode_hint = QLabel()
        self.clone_ranked_battle_mode_hint.setWordWrap(True)
        self.clone_ranked_battle_mode_hint.setStyleSheet("color: #777;")
        war_layout.addWidget(self.clone_ranked_battle_mode_hint)

        ranked_battle_mode_hints = {
            1: "Chỉ cần thắng trận là kết thúc.",
            2: "Tranh Bá đến khi tiêu diệt hết mục tiêu.",
            3: "Giới hạn thời gian trận Tranh Bá.",
        }
        for mode_id, hint in ranked_battle_mode_hints.items():
            self.clone_ranked_battle_mode_group.button(mode_id).toggled.connect(
                lambda checked, text=hint: (
                    self.clone_ranked_battle_mode_hint.setText(text)
                    if checked else None
                )
            )
        self.clone_ranked_battle_mode_hint.setText(
            ranked_battle_mode_hints[self.clone_ranked_battle_mode_group.checkedId()]
        )


        layout.addWidget(war_group)

        self.clone_quoc_chien = QCheckBox(
            step_registry.get_display_name_by_config_key("clone_quoc_chien", "Quốc chiến")
        )
        layout.addWidget(self.clone_quoc_chien)
        self.clone_reward_guild = QCheckBox(
            step_registry.get_display_name_by_config_key(
                "clone_reward_guild", "Nhận Thưởng - Quân Đoàn"
            )
        )
        layout.addWidget(self.clone_reward_guild)

        layout.addStretch(1)
        # Giữ đủ chiều rộng tối thiểu cho các điều khiển; nếu cửa sổ hẹp,
        # người dùng có thể cuộn ngang để thấy các checkbox bị khuất.
        page.setMinimumWidth(layout.minimumSize().width())
        scroll_area.setWidget(page)
        outer_layout.addWidget(scroll_area)

    def _browse_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn danh sách tài khoản",
            str(Path.home()),
            "INI files (*.ini);;All files (*)",
        )
        if filename:
            self.add_account_file(filename)

    def add_account_file(self, filename: str) -> None:
        """Add a selected account file to the dropdown, keeping paths unique."""
        filename = str(Path(filename).expanduser().resolve())
        index = self.account_file_combo.findData(filename)
        if index < 0:
            self.account_file_combo.addItem(Path(filename).name, filename)
            index = self.account_file_combo.count() - 1
        self.account_file_combo.setCurrentIndex(index)

    def set_account_files(self, filenames: list[str], selected: str = "") -> None:
        """Restore previously used file paths from application settings."""
        self.account_file_combo.blockSignals(True)
        self.account_file_combo.clear()
        seen = set()
        for filename in filenames:
            if not filename:
                continue
            path = str(Path(filename).expanduser())
            if path not in seen:
                self.account_file_combo.addItem(Path(path).name, path)
                seen.add(path)
        if selected:
            path = str(Path(selected).expanduser())
            index = self.account_file_combo.findData(path)
            if index < 0:
                self.account_file_combo.addItem(path, path)
                index = self.account_file_combo.count() - 1
            self.account_file_combo.setCurrentIndex(index)
        elif self.account_file_combo.count():
            self.account_file_combo.setCurrentIndex(0)
        self.account_file_combo.blockSignals(False)
        self._update_account_status()

    def _show_selected_file_path(self, *_args) -> None:
        filename = self.account_file()

    def account_file(self) -> str:
        value = self.account_file_combo.currentData()
        return str(value or self.account_file_combo.currentText()).strip()

    def account_files(self) -> list[str]:
        return [
            str(self.account_file_combo.itemData(index) or self.account_file_combo.itemText(index))
            for index in range(self.account_file_combo.count())
        ]

    def _update_account_status(self, *_args) -> None:
        filename = self.account_file()
        if not filename:
            self.account_status.setText("Chưa chọn file tài khoản.")
            return
        try:
            accounts = load_accounts(filename)
        except FileNotFoundError:
            self.account_status.setText("Chưa tìm thấy file. Hãy kiểm tra đường dẫn.")
        except (OSError, UnicodeError, ValueError) as exc:
            self.account_status.setText(str(exc))
        else:
            enabled = sum(account.enabled for account in accounts)
            disabled = len(accounts) - enabled
            self.account_status.setText(
                f"Đã đọc {len(accounts)} tài khoản: {enabled} bật, {disabled} vô hiệu hóa."
            )

    def current_config(self) -> dict:
        """Lấy cấu hình clone; không đưa mật khẩu vào cấu hình hoặc nhật ký."""
        return {
            "clone_mode": True,
            "clone_account_file": self.account_file(),
            "clone_login": True,
            "clone_daily_check_in": self.clone_daily_check_in.isChecked(),
            "clone_receive_quoc_van": self.clone_receive_quoc_van.isChecked(),
            "clone_guild_check_in": self.clone_guild_check_in.isChecked(),
            "clone_receive_lucky_bag": self.clone_receive_lucky_bag.isChecked(),
            "clone_guild_fortune": self.clone_guild_fortune.isChecked(),
            "clone_guild_donate_knb": self.clone_guild_donate_knb.isChecked(),
            "clone_guild_donate_rations": self.clone_guild_donate_rations.isChecked(),
            "clone_buy_fortune_lot": self.clone_buy_fortune_lot.isChecked(),
            "clone_quan_su_giao_tranh": self.clone_quan_su_giao_tranh.isChecked(),
            "battle_config": BattleConfig(
                battle_count=self.clone_battle_count.value(),
                mode={
                    1: "fast",
                    2: "normal",
                    3: "time_limit",
                }[self.clone_battle_mode_group.checkedId()],
                time_limit_seconds=self.clone_battle_time_limit.value(),
                refill=True,
            ),
            "clone_quan_su_tranh_ba": self.clone_quan_su_tranh_ba.isChecked(),
            "ranked_battle_config": BattleConfig(
                battle_count=self.clone_ranked_battle_count.value(),
                mode={
                    1: "fast",
                    2: "normal",
                    3: "time_limit",
                }[self.clone_ranked_battle_mode_group.checkedId()],
                time_limit_seconds=self.clone_ranked_battle_time_limit.value(),
                refill=self.clone_ranked_battle_refill.isChecked(),
            ),
            "clone_quoc_chien": self.clone_quoc_chien.isChecked(),
            "clone_reward_guild": self.clone_reward_guild.isChecked(),
            "clone_logout": True,
        }
