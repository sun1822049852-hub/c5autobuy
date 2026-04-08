async def test_app_bootstrap_route_matches_existing_runtime_and_diagnostics_routes(client, app):
    bootstrap_response = await client.get("/app/bootstrap")
    query_runtime_response = await client.get("/query-runtime/status")
    purchase_runtime_response = await client.get("/purchase-runtime/status")
    diagnostics_response = await client.get("/diagnostics/sidebar")
    capacity_summary_response = await client.get("/query-configs/capacity-summary")
    query_configs_response = await client.get("/query-configs")

    assert bootstrap_response.status_code == 200
    assert query_runtime_response.status_code == 200
    assert purchase_runtime_response.status_code == 200
    assert diagnostics_response.status_code == 200
    assert capacity_summary_response.status_code == 200
    assert query_configs_response.status_code == 200

    payload = bootstrap_response.json()
    assert payload["version"] == app.state.runtime_update_hub.current_version()
    assert payload["query_system"]["configs"] == query_configs_response.json()
    assert payload["query_system"]["capacity_summary"] == capacity_summary_response.json()
    assert payload["query_system"]["runtime_status"] == query_runtime_response.json()
    assert payload["purchase_system"]["runtime_status"] == purchase_runtime_response.json()
    assert payload["purchase_system"]["ui_preferences"] == {
        "selected_config_id": None,
        "updated_at": None,
    }
    assert payload["purchase_system"]["runtime_settings"] == {
        "per_batch_ip_fanout_limit": 1,
        "max_inflight_per_account": 1,
        "updated_at": None,
    }
    diagnostics_summary = diagnostics_response.json()["summary"]
    assert payload["diagnostics"]["summary"]["backend_online"] == diagnostics_summary["backend_online"]
    assert payload["diagnostics"]["summary"]["query_running"] == diagnostics_summary["query_running"]
    assert payload["diagnostics"]["summary"]["purchase_running"] == diagnostics_summary["purchase_running"]
    assert payload["diagnostics"]["summary"]["active_query_config_name"] == diagnostics_summary["active_query_config_name"]
    assert payload["diagnostics"]["summary"]["last_error"] == diagnostics_summary["last_error"]
    assert isinstance(payload["diagnostics"]["summary"]["updated_at"], str)
    assert payload["diagnostics"]["summary"]["updated_at"]
    assert payload["generated_at"] is not None


async def test_app_bootstrap_route_clears_deleted_selected_config(client):
    create_response = await client.post(
        "/query-configs",
        json={
            "name": "查询配置A",
            "description": "用于 bootstrap",
        },
    )
    config_id = create_response.json()["config_id"]

    put_response = await client.put(
        "/purchase-runtime/ui-preferences",
        json={"selected_config_id": config_id},
    )
    delete_response = await client.delete(f"/query-configs/{config_id}")
    bootstrap_response = await client.get("/app/bootstrap")

    assert create_response.status_code == 201
    assert put_response.status_code == 200
    assert delete_response.status_code == 204
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["purchase_system"]["ui_preferences"] == {
        "selected_config_id": None,
        "updated_at": None,
    }


async def test_app_bootstrap_route_matches_non_default_purchase_preferences_and_runtime_settings(client):
    create_response = await client.post(
        "/query-configs",
        json={
            "name": "查询配置A",
            "description": "用于 bootstrap parity",
        },
    )
    config_id = create_response.json()["config_id"]

    ui_preferences_response = await client.put(
        "/purchase-runtime/ui-preferences",
        json={"selected_config_id": config_id},
    )
    runtime_settings_response = await client.put(
        "/runtime-settings/purchase",
        json={
            "per_batch_ip_fanout_limit": 4,
            "max_inflight_per_account": 2,
        },
    )
    bootstrap_response = await client.get("/app/bootstrap")

    assert create_response.status_code == 201
    assert ui_preferences_response.status_code == 200
    assert runtime_settings_response.status_code == 200
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["purchase_system"]["ui_preferences"] == ui_preferences_response.json()
    assert bootstrap_response.json()["purchase_system"]["runtime_settings"] == runtime_settings_response.json()


async def test_app_bootstrap_route_reads_non_zero_runtime_update_hub_version(client, app):
    app.state.runtime_update_hub.publish(
        event="bootstrap-test",
        payload={"source": "test"},
    )

    response = await client.get("/app/bootstrap")

    assert response.status_code == 200
    assert response.json()["version"] == app.state.runtime_update_hub.current_version()
    assert response.json()["version"] > 0
