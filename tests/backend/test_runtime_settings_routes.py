from types import SimpleNamespace


async def test_get_purchase_runtime_settings_returns_default_limit(client):
    response = await client.get("/runtime-settings/purchase")

    assert response.status_code == 200
    assert response.json() == {
        "per_batch_ip_fanout_limit": 1,
        "max_inflight_per_account": 3,
        "updated_at": None,
    }


async def test_put_purchase_runtime_settings_updates_limit(client):
    response = await client.put(
        "/runtime-settings/purchase",
        json={
            "per_batch_ip_fanout_limit": 4,
            "max_inflight_per_account": 2,
        },
    )
    reloaded = await client.get("/runtime-settings/purchase")

    assert response.status_code == 200
    assert response.json()["per_batch_ip_fanout_limit"] == 4
    assert response.json()["max_inflight_per_account"] == 2
    assert response.json()["updated_at"] is not None
    assert reloaded.status_code == 200
    assert reloaded.json()["per_batch_ip_fanout_limit"] == 4
    assert reloaded.json()["max_inflight_per_account"] == 2


async def test_put_purchase_runtime_settings_rejects_limit_below_one(client):
    response = await client.put(
        "/runtime-settings/purchase",
        json={
            "per_batch_ip_fanout_limit": 0,
            "max_inflight_per_account": 1,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "per_batch_ip_fanout_limit 必须大于等于 1"


async def test_put_purchase_runtime_settings_rejects_max_inflight_below_one(client):
    response = await client.put(
        "/runtime-settings/purchase",
        json={
            "per_batch_ip_fanout_limit": 1,
            "max_inflight_per_account": 0,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "max_inflight_per_account 必须大于等于 1"


async def test_get_purchase_runtime_settings_triggers_runtime_full_ensure_when_repository_missing(client, app):
    ensure_calls: list[str] = []

    class FakeRuntimeSettingsRepository:
        def get(self):
            return SimpleNamespace(purchase_settings_json={}, updated_at=None)

    def fake_ensure() -> None:
        ensure_calls.append("called")
        app.state.runtime_settings_repository = FakeRuntimeSettingsRepository()

    delattr(app.state, "runtime_settings_repository")
    app.state.ensure_runtime_full_ready = fake_ensure

    response = await client.get("/runtime-settings/purchase")

    assert response.status_code == 200
    assert response.json() == {
        "per_batch_ip_fanout_limit": 1,
        "max_inflight_per_account": 3,
        "updated_at": None,
    }
    assert ensure_calls == ["called"]
