import { NO_SELECT_STYLE } from "../../../shared/no_select_style.js";

function getDisplayName(row) {
  return row.display_name || row.remark_name || row.c5_nick_name || row.default_name || row.account_id;
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
  onNicknameClick,
  onProxyClick,
  onPurchaseStatusClick,
  onRowContextMenu,
  rows,
}) {
  if (isLoading) {
    return (
      <tr>
        <td className="account-table__empty" colSpan={4} style={NO_SELECT_STYLE}>正在加载账号列表...</td>
      </tr>
    );
  }

  if (loadError) {
    return (
      <tr>
        <td className="account-table__empty" colSpan={4} style={NO_SELECT_STYLE}>加载失败：{loadError}</td>
      </tr>
    );
  }

  if (!rows.length) {
    return (
      <tr>
        <td className="account-table__empty" colSpan={4} style={NO_SELECT_STYLE}>没有符合条件的账号</td>
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
          <button
            aria-label={`编辑 API Key ${displayName}`}
            className="account-table__action"
            type="button"
            onClick={() => onApiKeyClick?.(row)}
          >
            <span className={`account-table__pill${row.api_key_present ? " is-good" : " is-muted"}`}>
              {row.api_key_present ? "有" : "无"}
            </span>
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
            aria-label={`编辑代理 ${displayName}`}
            className="account-table__action account-table__action--proxy"
            type="button"
            onClick={() => onProxyClick?.(row)}
          >
            {row.proxy_display || "未配置代理"}
          </button>
        </td>
      </tr>
    );
  });
}


export function AccountTable({
  isLoading,
  loadError,
  onApiKeyClick,
  onNicknameClick,
  onProxyClick,
  onPurchaseStatusClick,
  onRowContextMenu,
  rows,
}) {
  return (
    <table aria-label="账号列表" className="account-table">
      <thead>
        <tr>
          <th scope="col" style={NO_SELECT_STYLE}>C5昵称</th>
          <th scope="col" style={NO_SELECT_STYLE}>API Key</th>
          <th scope="col" style={NO_SELECT_STYLE}>购买状态</th>
          <th scope="col" style={NO_SELECT_STYLE}>代理</th>
        </tr>
      </thead>
      <tbody>
        {renderBody({
          isLoading,
          loadError,
          onApiKeyClick,
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
