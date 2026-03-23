from __future__ import annotations


def test_c5_status_helper_marks_not_login_text_as_auth_invalid():
    from app_backend.infrastructure.c5.response_status import classify_c5_response_error

    error = classify_c5_response_error(status=200, text="Not login")

    assert error == "Not login"


def test_c5_status_helper_marks_http_403_as_auth_invalid():
    from app_backend.infrastructure.c5.response_status import classify_c5_response_error

    error = classify_c5_response_error(status=403, text="<html>forbidden</html>")

    assert error == "HTTP 403 Forbidden"


def test_c5_status_helper_marks_http_429_as_rate_limited():
    from app_backend.infrastructure.c5.response_status import classify_c5_response_error

    error = classify_c5_response_error(status=429, text="<html>too many requests</html>")

    assert error == "HTTP 429 Too Many Requests"
