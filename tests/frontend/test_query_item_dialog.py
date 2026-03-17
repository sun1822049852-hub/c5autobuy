from __future__ import annotations

from PySide6.QtWidgets import QDialog


def _item(**overrides) -> dict:
    payload = {
        "query_item_id": "item-1",
        "config_id": "cfg-1",
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
        "max_wear": 0.25,
        "max_price": 100.0,
    }
    payload.update(overrides)
    return payload


def test_new_query_item_dialog_rejects_empty_product_url(qtbot):
    from app_frontend.app.dialogs.query_item_dialog import QueryItemDialog

    dialog = QueryItemDialog()
    qtbot.addWidget(dialog)
    dialog.product_url_input.clear()

    dialog.accept()

    assert dialog.result() == int(QDialog.DialogCode.Rejected)
    assert hasattr(dialog, "error_label")
    assert dialog.error_label.text() == "商品 URL 不能为空"


def test_new_query_item_dialog_rejects_out_of_range_max_wear(qtbot):
    from app_frontend.app.dialogs.query_item_dialog import QueryItemDialog

    dialog = QueryItemDialog()
    qtbot.addWidget(dialog)
    dialog.product_url_input.setText("https://www.c5game.com/csgo/730/asset/1380979899390262222")
    dialog.max_wear_input.setValue(1.2)

    dialog.accept()

    assert dialog.result() == int(QDialog.DialogCode.Rejected)
    assert dialog.error_label.text() == "最大磨损必须在 0 到 1 之间"


def test_new_query_item_dialog_rejects_non_positive_max_price(qtbot):
    from app_frontend.app.dialogs.query_item_dialog import QueryItemDialog

    dialog = QueryItemDialog()
    qtbot.addWidget(dialog)
    dialog.product_url_input.setText("https://www.c5game.com/csgo/730/asset/1380979899390263333")
    dialog.max_price_input.setValue(0.0)

    dialog.accept()

    assert dialog.result() == int(QDialog.DialogCode.Rejected)
    assert dialog.error_label.text() == "最高价格必须大于 0"


def test_edit_query_item_dialog_builds_threshold_only_payload(qtbot):
    from app_frontend.app.dialogs.query_item_dialog import QueryItemDialog

    dialog = QueryItemDialog(item=_item(max_wear=None, max_price=None))
    qtbot.addWidget(dialog)

    payload = dialog.build_payload()

    assert payload == {
        "max_wear": None,
        "max_price": None,
    }
