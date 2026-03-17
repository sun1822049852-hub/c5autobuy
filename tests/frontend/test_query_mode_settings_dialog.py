from __future__ import annotations


def _mode_setting(mode_type: str = "new_api", *, enabled: bool = True) -> dict:
    return {
        "mode_setting_id": "m-1",
        "config_id": "cfg-1",
        "mode_type": mode_type,
        "enabled": enabled,
        "window_enabled": True,
        "start_hour": 9,
        "start_minute": 30,
        "end_hour": 18,
        "end_minute": 0,
        "base_cooldown_min": 1.0,
        "base_cooldown_max": 2.0,
        "random_delay_enabled": True,
        "random_delay_min": 0.2,
        "random_delay_max": 0.8,
        "created_at": "2026-03-16T12:00:00",
        "updated_at": "2026-03-16T12:00:00",
    }


def test_query_mode_settings_dialog_builds_payload(qtbot):
    from app_frontend.app.dialogs.query_mode_settings_dialog import QueryModeSettingsDialog

    dialog = QueryModeSettingsDialog(mode_setting=_mode_setting())
    qtbot.addWidget(dialog)

    dialog.enabled_checkbox.setChecked(False)
    dialog.window_enabled_checkbox.setChecked(False)
    dialog.start_hour_input.setValue(10)
    dialog.start_minute_input.setValue(5)
    dialog.end_hour_input.setValue(20)
    dialog.end_minute_input.setValue(15)
    dialog.base_cooldown_min_input.setValue(0.5)
    dialog.base_cooldown_max_input.setValue(1.5)
    dialog.random_delay_enabled_checkbox.setChecked(False)
    dialog.random_delay_min_input.setValue(0.1)
    dialog.random_delay_max_input.setValue(0.4)

    assert dialog.build_payload() == {
        "enabled": False,
        "window_enabled": False,
        "start_hour": 10,
        "start_minute": 5,
        "end_hour": 20,
        "end_minute": 15,
        "base_cooldown_min": 0.5,
        "base_cooldown_max": 1.5,
        "random_delay_enabled": False,
        "random_delay_min": 0.1,
        "random_delay_max": 0.4,
    }
