async def test_get_purchase_runtime_settings_returns_default_limit(client):
    response = await client.get("/runtime-settings/purchase")

    assert response.status_code == 200
    assert response.json() == {
        "per_batch_ip_fanout_limit": 1,
        "updated_at": None,
    }


async def test_put_purchase_runtime_settings_updates_limit(client):
    response = await client.put(
        "/runtime-settings/purchase",
        json={"per_batch_ip_fanout_limit": 4},
    )
    reloaded = await client.get("/runtime-settings/purchase")

    assert response.status_code == 200
    assert response.json()["per_batch_ip_fanout_limit"] == 4
    assert response.json()["updated_at"] is not None
    assert reloaded.status_code == 200
    assert reloaded.json()["per_batch_ip_fanout_limit"] == 4


async def test_put_purchase_runtime_settings_rejects_limit_below_one(client):
    response = await client.put(
        "/runtime-settings/purchase",
        json={"per_batch_ip_fanout_limit": 0},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "per_batch_ip_fanout_limit 必须大于等于 1"
