from __future__ import annotations


def test_extract_user_info_from_html_prefers_user_center_nickname_over_other_ellipsis_text():
    from app_backend.infrastructure.browser_runtime.cdp_session_reader import extract_user_info_from_html

    payload = extract_user_info_from_html(
        """
        <div class="banner">
          <p class="ellipsis">为维护交易公平，任一方在交易完成后撤销交易，账号将受到限制和处罚。</p>
        </div>
        <div id="user_main">
          <div class="user-left">
            <div class="user-info">
              <img class="mb10 avatar" src="https://img.c5game.com/image/u-1003288.jpg" />
              <p class="ellipsis">功过是非皆过客...</p>
              <span>*</span>
            </div>
          </div>
        </div>
        """
    )

    assert payload["nickName"] == "功过是非皆过客..."


def test_extract_user_info_from_html_still_reads_nickname_from_embedded_json():
    from app_backend.infrastructure.browser_runtime.cdp_session_reader import extract_user_info_from_html

    payload = extract_user_info_from_html(
        """
        <script>
          window.__INITIAL_STATE__ = {"userId":"1003936745","nickName":"Eight"};
        </script>
        <div id="user_main">
          <div class="user-left">
            <div class="user-info">
              <p class="ellipsis">功过是非皆过客...</p>
            </div>
          </div>
        </div>
        """
    )

    assert payload["userId"] == "1003936745"
    assert payload["nickName"] == "Eight"
