from app_backend.infrastructure.proxy.value_objects import normalize_proxy_input, render_proxy_url


def test_empty_proxy_normalizes_to_direct():
    normalized = normalize_proxy_input(proxy_mode="direct", proxy_url="")

    assert normalized is None


def test_full_proxy_url_with_auth_is_preserved():
    normalized = normalize_proxy_input(
        proxy_mode="custom",
        proxy_url="http://user:pass@127.0.0.1:8080",
    )

    assert normalized == "http://user:pass@127.0.0.1:8080"


def test_proxy_host_and_port_without_scheme_normalize_to_http():
    normalized = normalize_proxy_input(
        proxy_mode="custom",
        proxy_url="127.0.0.1:8080",
    )

    assert normalized == "http://127.0.0.1:8080"


def test_proxy_auth_host_and_port_without_scheme_normalize_to_http():
    normalized = normalize_proxy_input(
        proxy_mode="custom",
        proxy_url="user:pass@127.0.0.1:8080",
    )

    assert normalized == "http://user:pass@127.0.0.1:8080"


def test_split_proxy_fields_render_to_full_url():
    rendered = render_proxy_url(
        scheme="http",
        host="127.0.0.1",
        port="8080",
        username="user",
        password="pass",
    )

    assert rendered == "http://user:pass@127.0.0.1:8080"
