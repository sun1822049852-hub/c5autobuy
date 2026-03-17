from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)


class QueryModeSettingsDialog(QDialog):
    def __init__(self, *, mode_setting: dict, parent=None) -> None:
        super().__init__(parent)
        self._mode_setting = dict(mode_setting)
        self.setWindowTitle(f"编辑模式参数 - {self._mode_setting.get('mode_type', '')}")

        self.mode_type_label = QLabel(str(self._mode_setting.get("mode_type") or ""))
        self.enabled_checkbox = QCheckBox("启用该模式")
        self.window_enabled_checkbox = QCheckBox("启用时间窗口")
        self.start_hour_input = self._build_int_spin(0, 23)
        self.start_minute_input = self._build_int_spin(0, 59)
        self.end_hour_input = self._build_int_spin(0, 23)
        self.end_minute_input = self._build_int_spin(0, 59)
        self.base_cooldown_min_input = self._build_float_spin(0.0, 9999.0)
        self.base_cooldown_max_input = self._build_float_spin(0.0, 9999.0)
        self.random_delay_enabled_checkbox = QCheckBox("启用随机延迟")
        self.random_delay_min_input = self._build_float_spin(0.0, 9999.0)
        self.random_delay_max_input = self._build_float_spin(0.0, 9999.0)

        self.enabled_checkbox.setChecked(bool(self._mode_setting.get("enabled")))
        self.window_enabled_checkbox.setChecked(bool(self._mode_setting.get("window_enabled")))
        self.start_hour_input.setValue(int(self._mode_setting.get("start_hour", 0)))
        self.start_minute_input.setValue(int(self._mode_setting.get("start_minute", 0)))
        self.end_hour_input.setValue(int(self._mode_setting.get("end_hour", 0)))
        self.end_minute_input.setValue(int(self._mode_setting.get("end_minute", 0)))
        self.base_cooldown_min_input.setValue(float(self._mode_setting.get("base_cooldown_min", 0.0)))
        self.base_cooldown_max_input.setValue(float(self._mode_setting.get("base_cooldown_max", 0.0)))
        self.random_delay_enabled_checkbox.setChecked(bool(self._mode_setting.get("random_delay_enabled")))
        self.random_delay_min_input.setValue(float(self._mode_setting.get("random_delay_min", 0.0)))
        self.random_delay_max_input.setValue(float(self._mode_setting.get("random_delay_max", 0.0)))

        form_layout = QFormLayout()
        form_layout.addRow("模式", self.mode_type_label)
        form_layout.addRow("", self.enabled_checkbox)
        form_layout.addRow("", self.window_enabled_checkbox)
        form_layout.addRow("开始小时", self.start_hour_input)
        form_layout.addRow("开始分钟", self.start_minute_input)
        form_layout.addRow("结束小时", self.end_hour_input)
        form_layout.addRow("结束分钟", self.end_minute_input)
        form_layout.addRow("基础冷却最小", self.base_cooldown_min_input)
        form_layout.addRow("基础冷却最大", self.base_cooldown_max_input)
        form_layout.addRow("", self.random_delay_enabled_checkbox)
        form_layout.addRow("随机延迟最小", self.random_delay_min_input)
        form_layout.addRow("随机延迟最大", self.random_delay_max_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

    def build_payload(self) -> dict[str, float | int | bool]:
        return {
            "enabled": self.enabled_checkbox.isChecked(),
            "window_enabled": self.window_enabled_checkbox.isChecked(),
            "start_hour": self.start_hour_input.value(),
            "start_minute": self.start_minute_input.value(),
            "end_hour": self.end_hour_input.value(),
            "end_minute": self.end_minute_input.value(),
            "base_cooldown_min": self.base_cooldown_min_input.value(),
            "base_cooldown_max": self.base_cooldown_max_input.value(),
            "random_delay_enabled": self.random_delay_enabled_checkbox.isChecked(),
            "random_delay_min": self.random_delay_min_input.value(),
            "random_delay_max": self.random_delay_max_input.value(),
        }

    @staticmethod
    def _build_int_spin(minimum: int, maximum: int) -> QSpinBox:
        field = QSpinBox()
        field.setRange(minimum, maximum)
        return field

    @staticmethod
    def _build_float_spin(minimum: float, maximum: float) -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setRange(minimum, maximum)
        field.setDecimals(3)
        field.setSingleStep(0.1)
        return field
