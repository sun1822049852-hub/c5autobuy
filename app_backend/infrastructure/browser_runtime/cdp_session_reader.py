from __future__ import annotations

import base64
import html as html_lib
import json
import re
import time
import urllib.error
import urllib.request

import websocket


PARTNER_INFO_PATH_FRAGMENT = "/api/v1/uic/partner/v1/info"


def http_get_json(url: str) -> object:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接到 Edge 调试端口: {url} ({exc.reason})") from exc


def select_target(debugger_address: str) -> dict[str, object]:
    targets = http_get_json(f"http://{debugger_address}/json/list")
    if not isinstance(targets, list):
        raise RuntimeError("Edge 调试端口返回的 target 列表格式不正确")

    def _priority(target: dict[str, object]) -> tuple[int, str]:
        url = str(target.get("url") or "")
        title = str(target.get("title") or "")
        if "c5game.com/user/user" in url:
            return (0, url)
        if "c5game.com" in url:
            return (1, url)
        if "c5game" in title.lower():
            return (2, title)
        return (3, url or title)

    pages = [
        target for target in targets
        if isinstance(target, dict) and str(target.get("type") or "") == "page"
    ]
    if not pages:
        raise RuntimeError("当前调试浏览器里没有可用页面")
    selected = min(pages, key=_priority)
    if not str(selected.get("webSocketDebuggerUrl") or ""):
        raise RuntimeError("目标页面缺少 webSocketDebuggerUrl")
    return selected


def cdp_call(socket_conn, method: str, params: dict[str, object] | None = None) -> dict[str, object]:
    message_id = 1
    payload = {"id": message_id, "method": method, "params": params or {}}
    socket_conn.send(json.dumps(payload, ensure_ascii=False))
    while True:
        raw = socket_conn.recv()
        data = json.loads(raw)
        if data.get("id") == message_id:
            if data.get("error"):
                raise RuntimeError(f"CDP 调用失败: {method} -> {data['error']}")
            result = data.get("result")
            return result if isinstance(result, dict) else {}


def cdp_call_with_id(
    socket_conn,
    command_id: int,
    method: str,
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = {"id": command_id, "method": method, "params": params or {}}
    socket_conn.send(json.dumps(payload, ensure_ascii=False))
    while True:
        raw = socket_conn.recv()
        data = json.loads(raw)
        if data.get("id") == command_id:
            if data.get("error"):
                raise RuntimeError(f"CDP 调用失败: {method} -> {data['error']}")
            result = data.get("result")
            return result if isinstance(result, dict) else {}


def extract_user_info_from_html(html: str) -> dict[str, object]:
    user_id = ""
    nick_name = ""
    user_id_match = re.search(r'"userId":\s*"?(?P<user_id>\d+)"?', html)
    if user_id_match:
        user_id = user_id_match.group("user_id")
    nick_name_match = re.search(r'"nickName":\s*"(?P<nick_name>[^"]+)"', html)
    if nick_name_match:
        nick_name = nick_name_match.group("nick_name")
    if not nick_name:
        user_center_match = re.search(
            r'<div[^>]*id="user_main"[^>]*>.*?<div[^>]*class="[^"]*\buser-left\b[^"]*"[^>]*>'
            r'.*?<div[^>]*class="[^"]*\buser-info\b[^"]*"[^>]*>.*?<p[^>]*>(?P<nick_name>.*?)</p>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if user_center_match:
            nick_name = re.sub(r"<[^>]+>", "", html_lib.unescape(user_center_match.group("nick_name"))).strip()
    return {
        "userId": user_id,
        "nickName": nick_name,
    }


def extract_cookie_map(cookie_raw: str) -> dict[str, str]:
    cookie_map: dict[str, str] = {}
    for item in cookie_raw.split(";"):
        if "=" not in item:
            continue
        name, value = item.split("=", 1)
        name = name.strip()
        if not name:
            continue
        cookie_map[name] = value.strip()
    return cookie_map


def decode_jwt_payload(token: str) -> dict[str, object]:
    parts = str(token or "").split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1].strip()
    if not payload:
        return {}
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode((payload + padding).encode("ascii")).decode("utf-8")
        parsed = json.loads(decoded)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def enrich_user_info_from_cookie(user_info: dict[str, object], cookie_raw: str) -> dict[str, object]:
    enriched = dict(user_info)
    cookie_map = extract_cookie_map(cookie_raw)
    nc5_uid = str(cookie_map.get("NC5_uid") or "").strip()
    if nc5_uid and nc5_uid.lower() != "undefined" and not enriched.get("userId"):
        enriched["userId"] = nc5_uid
    if not enriched.get("userId"):
        jwt_payload = decode_jwt_payload(str(cookie_map.get("NC5_accessToken") or ""))
        token_uid = str(jwt_payload.get("uid") or "").strip()
        if token_uid:
            enriched["userId"] = token_uid
    return enriched


def read_attached_session(debugger_address: str) -> dict[str, object]:
    target = select_target(debugger_address)
    target_url = str(target.get("url") or "")
    target_title = str(target.get("title") or "")
    ws_url = str(target.get("webSocketDebuggerUrl") or "")
    try:
        socket_conn = websocket.create_connection(ws_url, timeout=5, suppress_origin=True)
    except Exception as exc:
        raise RuntimeError(f"无法建立 CDP websocket 连接: {exc}") from exc

    try:
        html_result = cdp_call(
            socket_conn,
            "Runtime.evaluate",
            {
                "expression": "document.documentElement ? document.documentElement.outerHTML : ''",
                "returnByValue": True,
            },
        )
        html = str(((html_result.get("result") or {}) if isinstance(html_result, dict) else {}).get("value") or "")
        user_info = extract_user_info_from_html(html)

        cookie_result = cdp_call(socket_conn, "Network.getAllCookies")
        cookies = cookie_result.get("cookies") if isinstance(cookie_result, dict) else []
        cookie_parts: list[str] = []
        if isinstance(cookies, list):
            for item in cookies:
                if not isinstance(item, dict):
                    continue
                domain = str(item.get("domain") or "")
                name = str(item.get("name") or "")
                value = str(item.get("value") or "")
                if "c5game.com" not in domain or not name:
                    continue
                cookie_parts.append(f"{name}={value}")
        cookie_raw = "; ".join(cookie_parts)
        user_info = enrich_user_info_from_cookie(user_info, cookie_raw)
        if not user_info.get("userId") and not cookie_raw:
            raise RuntimeError("当前附加浏览器未读取到 C5 用户信息或 Cookie")
        return {
            "user_info": user_info,
            "cookie_raw": cookie_raw,
            "c5_user_id": str(user_info.get("userId") or ""),
            "c5_nick_name": str(user_info.get("nickName") or ""),
            "capture_source": "cdp",
            "target_url": target_url,
            "target_title": target_title,
        }
    finally:
        try:
            socket_conn.close()
        except Exception:
            pass


def navigate_attached_session(debugger_address: str, url: str) -> dict[str, object]:
    target = select_target(debugger_address)
    ws_url = str(target.get("webSocketDebuggerUrl") or "")
    if not ws_url:
        raise RuntimeError("目标页面缺少 webSocketDebuggerUrl")
    try:
        socket_conn = websocket.create_connection(ws_url, timeout=5, suppress_origin=True)
    except Exception as exc:
        raise RuntimeError(f"无法建立 CDP websocket 连接: {exc}") from exc

    try:
        cdp_call(socket_conn, "Page.enable")
        return cdp_call(socket_conn, "Page.navigate", {"url": url})
    finally:
        try:
            socket_conn.close()
        except Exception:
            pass


def capture_open_api_partner_info(debugger_address: str, timeout_seconds: float = 20.0) -> dict[str, object] | None:
    target = select_target(debugger_address)
    ws_url = str(target.get("webSocketDebuggerUrl") or "")
    if not ws_url:
        raise RuntimeError("目标页面缺少 webSocketDebuggerUrl")
    try:
        socket_conn = websocket.create_connection(ws_url, timeout=5, suppress_origin=True)
    except Exception as exc:
        raise RuntimeError(f"无法建立 CDP websocket 连接: {exc}") from exc

    try:
        cdp_call_with_id(socket_conn, 101, "Network.enable")
        deadline = time.time() + max(float(timeout_seconds), 0.1)
        request_url_map: dict[str, str] = {}
        while time.time() < deadline:
            remaining = max(deadline - time.time(), 0.1)
            socket_conn.settimeout(remaining)
            try:
                raw = socket_conn.recv()
            except websocket.WebSocketTimeoutException:
                return None
            data = json.loads(raw)
            method = str(data.get("method") or "")
            params = data.get("params") if isinstance(data.get("params"), dict) else {}
            if method == "Network.requestWillBeSent":
                request = params.get("request") if isinstance(params.get("request"), dict) else {}
                request_id = str(params.get("requestId") or "")
                url = str(request.get("url") or "")
                if request_id and _is_partner_info_url(url):
                    request_url_map[request_id] = url
                continue
            if method != "Network.responseReceived":
                continue
            response = params.get("response") if isinstance(params.get("response"), dict) else {}
            request_id = str(params.get("requestId") or "")
            url = str(response.get("url") or request_url_map.get(request_id) or "")
            status = int(response.get("status") or 0)
            if not request_id or status != 200 or not _is_partner_info_url(url):
                continue
            body_result = cdp_call_with_id(
                socket_conn,
                102,
                "Network.getResponseBody",
                {"requestId": request_id},
            )
            body = str(body_result.get("body") or "")
            if body_result.get("base64Encoded"):
                body = base64.b64decode(body).decode("utf-8", errors="ignore")
            payload = json.loads(body)
            if isinstance(payload, dict):
                return payload
            return None
        return None
    finally:
        try:
            socket_conn.close()
        except Exception:
            pass


def navigate_and_capture_open_api_partner_info(
    debugger_address: str,
    url: str,
    timeout_seconds: float = 20.0,
) -> dict[str, object] | None:
    target = select_target(debugger_address)
    ws_url = str(target.get("webSocketDebuggerUrl") or "")
    if not ws_url:
        raise RuntimeError("目标页面缺少 webSocketDebuggerUrl")
    try:
        socket_conn = websocket.create_connection(ws_url, timeout=5, suppress_origin=True)
    except Exception as exc:
        raise RuntimeError(f"无法建立 CDP websocket 连接: {exc}") from exc

    try:
        cdp_call_with_id(socket_conn, 201, "Page.enable")
        cdp_call_with_id(socket_conn, 202, "Network.enable")
        cdp_call_with_id(socket_conn, 203, "Page.navigate", {"url": url})
        deadline = time.time() + max(float(timeout_seconds), 0.1)
        request_url_map: dict[str, str] = {}
        while time.time() < deadline:
            remaining = max(deadline - time.time(), 0.1)
            socket_conn.settimeout(remaining)
            try:
                raw = socket_conn.recv()
            except websocket.WebSocketTimeoutException:
                return None
            data = json.loads(raw)
            method = str(data.get("method") or "")
            params = data.get("params") if isinstance(data.get("params"), dict) else {}
            if method == "Network.requestWillBeSent":
                request = params.get("request") if isinstance(params.get("request"), dict) else {}
                request_id = str(params.get("requestId") or "")
                request_url = str(request.get("url") or "")
                if request_id and _is_partner_info_url(request_url):
                    request_url_map[request_id] = request_url
                continue
            if method != "Network.responseReceived":
                continue
            response = params.get("response") if isinstance(params.get("response"), dict) else {}
            request_id = str(params.get("requestId") or "")
            response_url = str(response.get("url") or request_url_map.get(request_id) or "")
            status = int(response.get("status") or 0)
            if not request_id or status != 200 or not _is_partner_info_url(response_url):
                continue
            body_result = cdp_call_with_id(
                socket_conn,
                204,
                "Network.getResponseBody",
                {"requestId": request_id},
            )
            body = str(body_result.get("body") or "")
            if body_result.get("base64Encoded"):
                body = base64.b64decode(body).decode("utf-8", errors="ignore")
            payload = json.loads(body)
            return payload if isinstance(payload, dict) else None
        return None
    finally:
        try:
            socket_conn.close()
        except Exception:
            pass


def _is_partner_info_url(url: str) -> bool:
    return bool(url and PARTNER_INFO_PATH_FRAGMENT in url)


def read_open_api_page_state(debugger_address: str) -> dict[str, object] | None:
    target = select_target(debugger_address)
    ws_url = str(target.get("webSocketDebuggerUrl") or "")
    if not ws_url:
        raise RuntimeError("目标页面缺少 webSocketDebuggerUrl")
    try:
        socket_conn = websocket.create_connection(ws_url, timeout=5, suppress_origin=True)
    except Exception as exc:
        raise RuntimeError(f"无法建立 CDP websocket 连接: {exc}") from exc

    expression = """
(() => {
  const html = document.documentElement ? document.documentElement.outerHTML : "";
  const text = document.body ? document.body.innerText : "";
  const local = {};
  const session = {};
  try {
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (key) local[key] = localStorage.getItem(key);
    }
  } catch (e) {}
  try {
    for (let i = 0; i < sessionStorage.length; i += 1) {
      const key = sessionStorage.key(i);
      if (key) session[key] = sessionStorage.getItem(key);
    }
  } catch (e) {}
  return {
    html,
    text,
    pairs: Array.from(document.querySelectorAll('.applied-line, .mb15')).map((row) => {
      const labelNode = row.querySelector('.label');
      const valueNode = row.querySelector('.value');
      return {
        label: labelNode ? labelNode.textContent || "" : "",
        value: valueNode ? valueNode.textContent || "" : "",
      };
    }).filter((item) => item.label || item.value),
    openApiReady: !!document.querySelector('.open-api-wrap .applied-line .value'),
    openApiPairCount: document.querySelectorAll('.open-api-wrap .applied-line .value').length,
    localStorage: local,
    sessionStorage: session,
    href: location.href,
  };
})()
"""

    try:
        result = cdp_call(
            socket_conn,
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
            },
        )
        payload = ((result.get("result") or {}) if isinstance(result, dict) else {}).get("value")
        if isinstance(payload, dict):
            return payload
        return None
    finally:
        try:
            socket_conn.close()
        except Exception:
            pass


def poll_open_api_page_partner_info(
    debugger_address: str,
    timeout_seconds: float = 20.0,
    interval_seconds: float = 1.0,
) -> dict[str, object] | None:
    deadline = time.time() + max(float(timeout_seconds), 0.1)
    interval = max(float(interval_seconds), 0.1)
    while time.time() < deadline:
        page_state = read_open_api_page_state(debugger_address)
        payload = extract_partner_info_from_page_state(page_state)
        if payload is not None:
            return payload
        time.sleep(interval)
    return None


def summarize_open_api_page_state(page_state: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(page_state, dict):
        return {"has_page_state": False}
    return {
        "has_page_state": True,
        "href": str(page_state.get("href") or "") or None,
        "open_api_ready": bool(page_state.get("openApiReady")),
        "open_api_pair_count": int(page_state.get("openApiPairCount") or 0),
        "pair_count": len(page_state.get("pairs") or []) if isinstance(page_state.get("pairs"), list) else 0,
        "text_present": bool(str(page_state.get("text") or "").strip()),
        "html_present": bool(str(page_state.get("html") or "").strip()),
    }


def extract_partner_info_from_page_state(page_state: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(page_state, dict):
        return None
    href = str(page_state.get("href") or "")
    open_api_ready = bool(page_state.get("openApiReady"))
    if "c5game.com/user/user/open-api" in href and not open_api_ready:
        return None
    pair_payload = _extract_partner_info_from_pairs(page_state.get("pairs"))
    if pair_payload is not None:
        return pair_payload
    candidates: list[str] = []
    html = str(page_state.get("html") or "")
    text = str(page_state.get("text") or "")
    html_pair_payload = _extract_partner_info_from_html_pairs(html)
    if html_pair_payload is not None:
        return html_pair_payload
    if html:
        candidates.append(html)
    if text:
        candidates.append(text)
    for storage_name in ("localStorage", "sessionStorage"):
        storage = page_state.get(storage_name)
        if isinstance(storage, dict):
            for value in storage.values():
                if value is not None:
                    candidates.append(str(value))

    for candidate in candidates:
        payload = _extract_partner_info_from_text(candidate)
        if payload is not None:
            return payload
    return None


def _normalize_partner_label(label: str) -> str:
    normalized = html_lib.unescape(str(label or "")).strip().lower()
    normalized = normalized.replace("：", ":").replace(" ", "")
    normalized = normalized.rstrip(":")
    return normalized


def _build_partner_payload(api_info: dict[str, object]) -> dict[str, object] | None:
    cleaned = {
        key: str(value).strip()
        for key, value in api_info.items()
        if str(value or "").strip()
    }
    if not cleaned:
        return None
    return {
        "success": True,
        "data": {
            "apiInfo": cleaned,
        },
    }


def _extract_partner_info_from_pairs(pairs: object) -> dict[str, object] | None:
    if not isinstance(pairs, list):
        return None
    api_info: dict[str, object] = {}
    for item in pairs:
        if not isinstance(item, dict):
            continue
        label = _normalize_partner_label(str(item.get("label") or ""))
        value = str(item.get("value") or "").strip()
        if not label or not value:
            continue
        if label in {"app_key", "apikey", "apikey", "key"} and re.fullmatch(r"[a-fA-F0-9]{32,}", value):
            api_info["key"] = value
        elif label in {"app_secret", "apisecret", "secret"} and re.fullmatch(r"[a-fA-F0-9]{32,}", value):
            api_info["secret"] = value
        elif label in {"ip白名单", "白名单ip", "允许ip", "绑定ip", "ipallowlist"}:
            api_info["ipAllowList"] = value
    return _build_partner_payload(api_info)


def _extract_partner_info_from_html_pairs(html: str) -> dict[str, object] | None:
    if not html:
        return None
    pair_matches = re.findall(
        r'<div[^>]*class="[^"]*\blabel\b[^"]*"[^>]*>\s*(?P<label>.*?)\s*</div>\s*'
        r'<div[^>]*class="[^"]*\bvalue\b[^"]*"[^>]*>\s*(?P<value>.*?)\s*</div>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not pair_matches:
        pair_matches = re.findall(
            r'<div[^>]*>\s*(?P<label>[^<]{1,64})\s*</div>\s*<div[^>]*>\s*(?P<value>[^<]{1,256})\s*</div>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
    if not pair_matches:
        return None
    pairs = []
    for label, value in pair_matches:
        clean_label = re.sub(r"<[^>]+>", "", html_lib.unescape(label)).strip()
        clean_value = re.sub(r"<[^>]+>", "", html_lib.unescape(value)).strip()
        pairs.append({"label": clean_label, "value": clean_value})
    return _extract_partner_info_from_pairs(pairs)


def _extract_partner_info_from_text(text: str) -> dict[str, object] | None:
    if not text:
        return None
    key_match = re.search(r'"key"\s*:\s*"(?P<key>[a-fA-F0-9]{32,})"', text)
    secret_match = re.search(r'"secret"\s*:\s*"(?P<secret>[a-fA-F0-9]{32,})"', text)
    allow_list_match = re.search(r'"ipAllowList"\s*:\s*"(?P<ip>[^"]*)"', text)
    if not key_match:
        key_match = re.search(
            r'(?:app_key|API\s*Key|apikey|key)\s*[:：]?\s*</?[^>]*>\s*(?P<key>[a-fA-F0-9]{32,})',
            text,
            flags=re.IGNORECASE,
        )
    if not secret_match:
        secret_match = re.search(
            r'(?:app_secret|API\s*Secret|secret)\s*[:：]?\s*</?[^>]*>\s*(?P<secret>[a-fA-F0-9]{32,})',
            text,
            flags=re.IGNORECASE,
        )
    if not allow_list_match:
        allow_list_match = re.search(
            r'(?:ipAllowList|IP\s*Allow\s*List|IP白名单|白名单IP|允许IP|绑定IP)\s*[:：]?\s*</?[^>]*>\s*(?P<ip>[0-9\.,\s]+)',
            text,
            flags=re.IGNORECASE,
        )
    if not key_match and "apiInfo" not in text:
        return None
    api_info: dict[str, object] = {}
    if key_match:
        api_info["key"] = key_match.group("key")
    if secret_match:
        api_info["secret"] = secret_match.group("secret")
    if allow_list_match:
        api_info["ipAllowList"] = allow_list_match.group("ip")
    if not api_info:
        return None
    return _build_partner_payload(api_info)
