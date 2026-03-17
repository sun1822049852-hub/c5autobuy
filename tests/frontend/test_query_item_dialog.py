from __future__ import annotations

import asyncio

from PySide6.QtCore import Qt
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


class _InlineTaskRunner:
    def submit(self, coroutine_factory, *, on_success=None, on_error=None) -> None:
        try:
            result = asyncio.run(coroutine_factory())
        except Exception as exc:  # pragma: no cover - defensive
            if on_error is not None:
                on_error(str(exc))
            return
        if on_success is not None:
            on_success(result)


class _FakeItemDetailBackendClient:
    def __init__(self) -> None:
        self.parse_calls: list[dict] = []
        self.fetch_calls: list[dict] = []

    async def parse_query_item_url(self, payload: dict) -> dict:
        self.parse_calls.append(dict(payload))
        return {
            "product_url": payload["product_url"],
            "external_item_id": "1380979899390269999",
        }

    async def fetch_query_item_detail(self, payload: dict) -> dict:
        self.fetch_calls.append(dict(payload))
        return {
            "product_url": payload["product_url"],
            "external_item_id": payload["external_item_id"],
            "item_name": "AK-47 | Redline",
            "market_hash_name": "AK-47 | Redline (Field-Tested)",
            "min_wear": 0.1,
            "detail_max_wear": 0.7,
            "last_market_price": 123.45,
        }


def test_new_query_item_dialog_requires_detail_fetch_before_accept(qtbot):
    from app_frontend.app.dialogs.query_item_dialog import QueryItemDialog

    dialog = QueryItemDialog(
        backend_client=_FakeItemDetailBackendClient(),
        task_runner=_InlineTaskRunner(),
    )
    qtbot.addWidget(dialog)
    dialog.product_url_input.setText("https://www.c5game.com/csgo/730/asset/1380979899390269999")

    dialog.accept()

    assert dialog.result() == int(QDialog.DialogCode.Rejected)
    assert dialog.error_label.text() == "请先获取商品详情"


def test_new_query_item_dialog_fetches_and_displays_detail_before_accept(qtbot):
    from app_frontend.app.dialogs.query_item_dialog import QueryItemDialog

    backend_client = _FakeItemDetailBackendClient()
    dialog = QueryItemDialog(
        backend_client=backend_client,
        task_runner=_InlineTaskRunner(),
    )
    qtbot.addWidget(dialog)
    dialog.product_url_input.setText("https://www.c5game.com/csgo/730/asset/1380979899390269999")

    qtbot.mouseClick(dialog.fetch_detail_button, Qt.MouseButton.LeftButton)

    assert backend_client.parse_calls == [
        {
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390269999",
        }
    ]
    assert backend_client.fetch_calls == [
        {
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390269999",
            "external_item_id": "1380979899390269999",
        }
    ]
    assert dialog.item_name_input.text() == "AK-47 | Redline"
    assert dialog.market_hash_name_input.text() == "AK-47 | Redline (Field-Tested)"
    assert dialog.wear_range_input.text() == "0.1 ~ 0.7"
    assert dialog.last_market_price_input.text() == "123.45"

    dialog.accept()

    assert dialog.result() == int(QDialog.DialogCode.Accepted)


def test_new_query_item_dialog_rejects_max_wear_not_greater_than_min_wear(qtbot):
    from app_frontend.app.dialogs.query_item_dialog import QueryItemDialog

    backend_client = _FakeItemDetailBackendClient()
    dialog = QueryItemDialog(
        backend_client=backend_client,
        task_runner=_InlineTaskRunner(),
    )
    qtbot.addWidget(dialog)
    dialog.product_url_input.setText("https://www.c5game.com/csgo/730/asset/1380979899390269999")

    qtbot.mouseClick(dialog.fetch_detail_button, Qt.MouseButton.LeftButton)
    dialog.max_wear_input.setValue(0.1)

    dialog.accept()

    assert dialog.result() == int(QDialog.DialogCode.Rejected)
    assert dialog.error_label.text() == "最大磨损值必须在范围 (0.1, 0.7] 内"


def test_edit_query_item_dialog_rejects_max_wear_above_detail_max_wear(qtbot):
    from app_frontend.app.dialogs.query_item_dialog import QueryItemDialog

    dialog = QueryItemDialog(
        item=_item(
            min_wear=0.1,
            detail_max_wear=0.7,
            max_wear=0.25,
            max_price=100.0,
        )
    )
    qtbot.addWidget(dialog)
    dialog.max_wear_input.setValue(0.8)

    dialog.accept()

    assert dialog.result() == int(QDialog.DialogCode.Rejected)
    assert dialog.error_label.text() == "最大磨损值必须在范围 (0.1, 0.7] 内"
