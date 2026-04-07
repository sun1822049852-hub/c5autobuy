import { NO_SELECT_STYLE } from "../../../shared/no_select_style.js";

function getDisplayName(row) {
  return row.display_name || row.remark_name || row.c5_nick_name || row.default_name || row.account_id;
}


function formatBalance(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "未获取";
  }
  return value.toFixed(2);
}


function getQueryTone(statusCode, reasonCode) {
  if (statusCode === "enabled") {
    return "is-good";
  }

  if (reasonCode === "ip_invalid" || reasonCode === "not_logged_in") {
    return "is-danger";
  }

  return "is-muted";
}


function getQueryStatusDisplay(row, prefix) {
  return row[`${prefix}_status_text`] || "已禁用";
}


function getStatusTone(code) {
  if (code === "selected_warehouse") {
    return "is-good";
  }

  if (code === "inventory_full") {
    return "is-warn";
  }

  if (code === "not_logged_in") {
    return "is-danger";
  }

  return "is-muted";
}


function getPurchaseStatusDisplay(row) {
  if (row.purchase_status_code === "not_logged_in") {
    return "待登录";
  }

  return row.purchase_status_text || row.purchase_status_code || "未知";
}


function renderBody({
  isLoading,
  loadError,
  onApiKeyClick,
  onApiKeyEdit,
  onApiQueryToggle,
  onBrowserProxyClick,
  onBrowserQueryToggle,
  onNicknameClick,
  onProxyClick,
  onPurchaseStatusClick,
  onRowContextMenu,
  rows,
}) {
  if (isLoading) {
    return (
      <tr>
        <td className="account-table__empty" colSpan={7} style={NO_SELECT_STYLE}>正在加载账号列表...</td>
      </tr>
    );
  }

  if (loadError) {
    return (
      <tr>
        <td className="account-table__empty" colSpan={7} style={NO_SELECT_STYLE}>加载失败：{loadError}</td>
      </tr>
    );
  }

  if (!rows.length) {
    return (
      <tr>
        <td className="account-table__empty" colSpan={7} style={NO_SELECT_STYLE}>没有符合条件的账号</td>
      </tr>
    );
  }

  return rows.map((row) => {
    const displayName = getDisplayName(row);

    return (
      <tr
        key={row.account_id}
        onContextMenu={(event) => {
          event.preventDefault();
          onRowContextMenu?.(row, {
            x: event.clientX,
            y: event.clientY,
          });
        }}
      >
        <td>
          <button
            aria-label={`编辑昵称 ${displayName}`}
            className="account-table__action"
            type="button"
            onClick={() => onNicknameClick?.(row)}
          >
            <div className="account-table__nickname">
              <span className="account-table__nickname-main">{displayName}</span>
              <span className="account-table__nickname-sub">{row.c5_nick_name || row.default_name || "未命名账号"}</span>
            </div>
          </button>
        </td>
        <td>
          <div className="account-table__query-stack">
            <button
              aria-label={`切换 API 查询 ${displayName}`}
              className="account-table__action account-table__action--query"
              type="button"
              onClick={() => onApiQueryToggle?.(row)}
            >
              <span className={`account-table__pill ${getQueryTone(row.api_query_status_code, row.api_query_disable_reason_code)}`}>
                {getQueryStatusDisplay(row, "api_query")}
              </span>
              {row.api_query_disable_reason_text ? (
                <span className="account-table__query-reason">({row.api_query_disable_reason_text})</span>
              ) : null}
            </button>
            <button
              aria-label={`编辑 API Key ${displayName}`}
              className="account-table__inline-link"
              type="button"
              onClick={() => (onApiKeyEdit ?? onApiKeyClick)?.(row)}
            >
              编辑 key
            </button>
          </div>
        </td>
        <td>
          <button
            aria-label={`切换浏览器查询 ${displayName}`}
            className="account-table__action account-table__action--query"
            type="button"
            onClick={() => onBrowserQueryToggle?.(row)}
          >
            <span className={`account-table__pill ${getQueryTone(row.browser_query_status_code, row.browser_query_disable_reason_code)}`}>
              {getQueryStatusDisplay(row, "browser_query")}
            </span>
            {row.browser_query_disable_reason_text ? (
              <span className="account-table__query-reason">({row.browser_query_disable_reason_text})</span>
            ) : null}
          </button>
        </td>
        <td>
          <button
            aria-label={`配置购买状态 ${displayName}`}
            className="account-table__action"
            type="button"
            onClick={() => onPurchaseStatusClick?.(row)}
          >
            <span className={`account-table__pill ${getStatusTone(row.purchase_status_code)}`}>
              {getPurchaseStatusDisplay(row)}
            </span>
          </button>
        </td>
        <td>
          <button
            aria-label={`编辑浏览器 IP ${displayName}`}
            className="account-table__action account-table__action--proxy"
            type="button"
            onClick={() => onBrowserProxyClick?.(row)}
          >
            <div className="account-table__nickname">
              <span className="account-table__nickname-main">
                {row.browser_proxy_display || "未获取IP"}
              </span>
            </div>
          </button>
        </td>
        <td>
          <button
            aria-label={`编辑API IP ${displayName}`}
            className="account-table__action account-table__action--proxy"
            type="button"
            onClick={() => onProxyClick?.(row)}
          >
            <div className="account-table__nickname">
              <span className="account-table__nickname-main">
                {row.api_proxy_display || "未获取IP"}
              </span>
            </div>
          </button>
        </td>
        <td>
          <div className="account-table__nickname">
            <span className="account-table__nickname-main">{formatBalance(row.balance_amount)}</span>
          </div>
        </td>
      </tr>
    );
  });
}


export function AccountTable({
  isLoading,
  loadError,
  onApiKeyClick,
  onApiKeyEdit,
  onApiQueryToggle,
  onBrowserProxyClick,
  onBrowserQueryToggle,
  onNicknameClick,
  onProxyClick,
  onPurchaseStatusClick,
  onRowContextMenu,
  rows,
}) {
  return (
    <table aria-label="账号列表" className="account-table">
      <colgroup>
        <col /><col /><col /><col /><col /><col /><col />
      </colgroup>
      <thead>
        <tr>
          <th scope="col" style={NO_SELECT_STYLE}>C5昵称</th>
          <th scope="col" style={NO_SELECT_STYLE}>API 状态</th>
          <th scope="col" style={NO_SELECT_STYLE}>浏览器查询</th>
          <th scope="col" style={NO_SELECT_STYLE}>购买状态</th>
          <th scope="col" style={NO_SELECT_STYLE}>账号代理</th>
          <th scope="col" style={NO_SELECT_STYLE}>API代理</th>
          <th scope="col" style={NO_SELECT_STYLE}>余额</th>
        </tr>
      </thead>
      <tbody>
        {renderBody({
          isLoading,
          loadError,
          onApiKeyClick,
          onApiKeyEdit,
          onApiQueryToggle,
          onBrowserProxyClick,
          onBrowserQueryToggle,
          onNicknameClick,
          onProxyClick,
          onPurchaseStatusClick,
          onRowContextMenu,
          rows,
        })}
      </tbody>
    </table>
  );
}
