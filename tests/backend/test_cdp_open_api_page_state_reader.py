from __future__ import annotations


def test_extract_partner_info_from_page_state_reads_api_info_json_from_html():
    from app_backend.infrastructure.browser_runtime.cdp_session_reader import extract_partner_info_from_page_state

    payload = extract_partner_info_from_page_state(
        {
            "html": """
            <div id="app">
              {"success":true,"data":{"apiInfo":{"key":"474fee7731124a74bc2c8858f3bf00e6","secret":"8f5c3ca7b154427ebb38003f0b384ab2","ipAllowList":"36.138.220.178"}}}
            </div>
            """,
            "text": "",
            "localStorage": {},
            "sessionStorage": {},
        }
    )

    assert payload is not None
    assert payload["data"]["apiInfo"]["key"] == "474fee7731124a74bc2c8858f3bf00e6"
    assert payload["data"]["apiInfo"]["secret"] == "8f5c3ca7b154427ebb38003f0b384ab2"
    assert payload["data"]["apiInfo"]["ipAllowList"] == "36.138.220.178"


def test_extract_partner_info_from_page_state_reads_static_label_text():
    from app_backend.infrastructure.browser_runtime.cdp_session_reader import extract_partner_info_from_page_state

    payload = extract_partner_info_from_page_state(
        {
            "html": """
            <section>
              <div>API Key</div><div>474fee7731124a74bc2c8858f3bf00e6</div>
              <div>Secret</div><div>8f5c3ca7b154427ebb38003f0b384ab2</div>
              <div>绑定IP</div><div>36.138.220.178</div>
            </section>
            """,
            "text": "",
            "localStorage": {},
            "sessionStorage": {},
        }
    )

    assert payload is not None
    assert payload["data"]["apiInfo"]["key"] == "474fee7731124a74bc2c8858f3bf00e6"
    assert payload["data"]["apiInfo"]["secret"] == "8f5c3ca7b154427ebb38003f0b384ab2"
    assert payload["data"]["apiInfo"]["ipAllowList"] == "36.138.220.178"


def test_extract_partner_info_from_page_state_reads_real_open_api_dom_pairs():
    from app_backend.infrastructure.browser_runtime.cdp_session_reader import extract_partner_info_from_page_state

    payload = extract_partner_info_from_page_state(
        {
            "html": """
            <div class="applied-line mb15">
              <div class="label">app_key:</div>
              <div class="value">474fee7731124a74bc2c8858f3bf00e6</div>
            </div>
            <div class="applied-line mb15">
              <div class="label">app_secret:</div>
              <div class="value">8f5c3ca7b154427ebb38003f0b384ab2</div>
            </div>
            <div class="applied-line mb15">
              <div class="label">IP白名单:</div>
              <div class="value">36.138.220.178</div>
            </div>
            """,
            "text": "",
            "localStorage": {},
            "sessionStorage": {},
        }
    )

    assert payload is not None
    assert payload["data"]["apiInfo"]["key"] == "474fee7731124a74bc2c8858f3bf00e6"
    assert payload["data"]["apiInfo"]["secret"] == "8f5c3ca7b154427ebb38003f0b384ab2"
    assert payload["data"]["apiInfo"]["ipAllowList"] == "36.138.220.178"


def test_extract_partner_info_from_page_state_ignores_unready_open_api_dom():
    from app_backend.infrastructure.browser_runtime.cdp_session_reader import extract_partner_info_from_page_state

    payload = extract_partner_info_from_page_state(
        {
            "html": """
            <div class="open-api-wrap">
              <div class="apply-success-title-box">已开通API功能</div>
            </div>
            """,
            "text": "已开通API功能",
            "pairs": [],
            "openApiReady": False,
            "localStorage": {},
            "sessionStorage": {},
        }
    )

    assert payload is None

