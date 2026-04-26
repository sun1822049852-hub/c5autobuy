// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { QueryItemTable } from "../../src/features/query-system/components/query_item_table.jsx";

function buildItem(overrides = {}) {
  return {
    query_item_id: "item-1",
    item_name: "P90 | 满晕作品 (久经沙场)",
    last_market_price: 0.31,
    max_price: 0.35,
    detail_min_wear: 0.15,
    detail_max_wear: 0.28,
    manual_paused: false,
    statusByMode: {
      new_api: { status_message: "无可用账号" },
      fast_api: { status_message: "无可用账号" },
      token: { status_message: "无可用账号" },
    },
    ...overrides,
  };
}

describe("query item table", () => {
  it("uses the same explicit alignment track on the header and item rows", () => {
    render(
      <QueryItemTable
        canManageItems
        isDeleteMode={false}
        items={[buildItem()]}
        onDeleteItem={vi.fn()}
        onEditItem={vi.fn()}
        onOpenCreateItemDialog={vi.fn()}
        onToggleDeleteMode={vi.fn()}
        onToggleManualPause={vi.fn()}
      />,
    );

    const table = screen.getByRole("region", { name: "商品配置列表" });
    const headerGrid = table.querySelector(".query-item-table__column-grid");
    const itemRow = within(table).getByRole("region", { name: "商品 P90 | 满晕作品 (久经沙场)" });
    const rowContent = itemRow.querySelector(".query-item-row__content");

    expect(headerGrid).not.toBeNull();
    expect(rowContent).not.toBeNull();
    expect(headerGrid).toHaveClass("query-item-table__grid-track");
    expect(rowContent).toHaveClass("query-item-table__grid-track");
    expect(itemRow.querySelector(".query-item-row__toolbar-spacer")).not.toBeNull();
  });
});
