from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from c5_layered.application.use_cases import DashboardQueryUseCase, ScanControlUseCase
from c5_layered.domain.models import AccountProfile, ProductConfig
from c5_layered.infrastructure.runtime.legacy_cli_runtime import LegacyCliRuntime


class MainWindow:
    def __init__(
        self,
        dashboard_use_case: DashboardQueryUseCase,
        scan_use_case: ScanControlUseCase,
        cli_runtime: LegacyCliRuntime,
    ) -> None:
        self._dashboard = dashboard_use_case
        self._scan = scan_use_case
        self._cli_runtime = cli_runtime
        self._configs_by_name: dict[str, ProductConfig] = {}
        self._accounts_cache: list[AccountProfile] = []
        self._purchase_user_ids: set[str] = set()
        self._last_log_line_count = -1
        self._status_poll_job: str | None = None

        self.root = tk.Tk()
        self.root.title("C5 分层架构 - 图形化控制台")
        self.root.geometry("1260x840")
        self.root.minsize(1040, 700)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._summary_vars = {
            "total_accounts": tk.StringVar(value="0"),
            "logged_in_accounts": tk.StringVar(value="0"),
            "api_key_accounts": tk.StringVar(value="0"),
            "total_configs": tk.StringVar(value="0"),
            "total_products": tk.StringVar(value="0"),
        }
        self._scan_config_var = tk.StringVar(value="")
        self._scan_query_only_var = tk.BooleanVar(value=False)
        self._purchase_scope_var = tk.StringVar(value="购买账号：全部已登录账号")
        self._scan_status_var = tk.StringVar(value="扫描状态：未运行")

        self._build_layout()
        self.refresh()
        self._poll_scan_status_loop()

    def _build_layout(self) -> None:
        top_bar = ttk.Frame(self.root, padding=(12, 10))
        top_bar.pack(fill="x")

        ttk.Button(top_bar, text="刷新数据", command=self.refresh).pack(side="left")
        ttk.Label(top_bar, text="扫描配置:").pack(side="left", padx=(12, 4))
        self._scan_config_combo = ttk.Combobox(
            top_bar,
            textvariable=self._scan_config_var,
            width=22,
            state="readonly",
        )
        self._scan_config_combo.pack(side="left")

        ttk.Checkbutton(
            top_bar,
            text="仅查询模式",
            variable=self._scan_query_only_var,
            onvalue=True,
            offvalue=False,
        ).pack(side="left", padx=(12, 0))

        ttk.Button(top_bar, text="设置可购买账号", command=self._open_purchase_scope_dialog).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(top_bar, text="清空购买筛选", command=self._clear_purchase_scope).pack(
            side="left", padx=(8, 0)
        )

        ttk.Button(top_bar, text="开始扫描", command=self.start_scan).pack(side="left", padx=(8, 0))
        ttk.Button(top_bar, text="停止扫描", command=self.stop_scan).pack(side="left", padx=(8, 0))
        ttk.Button(top_bar, text="启动旧版 CLI", command=self.launch_legacy_cli).pack(side="left", padx=(8, 0))

        ttk.Label(top_bar, textvariable=self._scan_status_var).pack(side="right")

        purchase_scope_line = ttk.Frame(self.root, padding=(12, 0))
        purchase_scope_line.pack(fill="x")
        ttk.Label(purchase_scope_line, textvariable=self._purchase_scope_var).pack(side="left")

        summary_box = ttk.LabelFrame(self.root, text="运行概览", padding=(12, 10))
        summary_box.pack(fill="x", padx=12, pady=(6, 10))

        labels = [
            ("账号总数", "total_accounts"),
            ("已登录账号", "logged_in_accounts"),
            ("已配置 API Key", "api_key_accounts"),
            ("配置总数", "total_configs"),
            ("商品规则总数", "total_products"),
        ]
        for col, (title, key) in enumerate(labels):
            card = ttk.Frame(summary_box, padding=(10, 6))
            card.grid(row=0, column=col, sticky="nsew", padx=4)
            ttk.Label(card, text=title).pack(anchor="w")
            ttk.Label(card, textvariable=self._summary_vars[key], font=("Segoe UI", 14, "bold")).pack(
                anchor="w"
            )
            summary_box.columnconfigure(col, weight=1)

        body = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        left = ttk.Frame(body, padding=6)
        right = ttk.Frame(body, padding=6)
        body.add(left, weight=3)
        body.add(right, weight=4)

        notebook = ttk.Notebook(left)
        notebook.pack(fill="both", expand=True)
        account_tab = ttk.Frame(notebook, padding=8)
        config_tab = ttk.Frame(notebook, padding=8)
        notebook.add(account_tab, text="账号")
        notebook.add(config_tab, text="配置")

        self._account_tree = ttk.Treeview(
            account_tab,
            columns=("user_id", "name", "login", "api_key", "proxy", "updated"),
            show="headings",
            height=22,
        )
        self._setup_account_columns()
        self._account_tree.pack(fill="both", expand=True)

        config_split = ttk.PanedWindow(config_tab, orient=tk.HORIZONTAL)
        config_split.pack(fill="both", expand=True)
        cfg_left = ttk.Frame(config_split)
        cfg_right = ttk.Frame(config_split)
        config_split.add(cfg_left, weight=3)
        config_split.add(cfg_right, weight=4)

        self._config_tree = ttk.Treeview(
            cfg_left,
            columns=("name", "count", "updated"),
            show="headings",
            height=22,
        )
        self._setup_config_columns()
        self._config_tree.pack(fill="both", expand=True)
        self._config_tree.bind("<<TreeviewSelect>>", self._on_config_selected)

        ttk.Label(cfg_right, text="配置商品详情", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self._products_text = tk.Text(cfg_right, wrap="word", height=20)
        self._products_text.pack(fill="both", expand=True, pady=(6, 0))

        right_top = ttk.LabelFrame(right, text="运行日志", padding=8)
        right_top.pack(fill="both", expand=True)
        self._log_text = tk.Text(right_top, wrap="word", height=30)
        self._log_text.pack(fill="both", expand=True)
        self._log_text.configure(state="disabled")

    def _setup_account_columns(self) -> None:
        columns = {
            "user_id": ("用户 ID", 130),
            "name": ("账号名称", 240),
            "login": ("登录状态", 90),
            "api_key": ("API Key", 100),
            "proxy": ("代理", 260),
            "updated": ("更新时间", 160),
        }
        for key, (title, width) in columns.items():
            self._account_tree.heading(key, text=title)
            self._account_tree.column(key, width=width, anchor="w")

    def _setup_config_columns(self) -> None:
        columns = {
            "name": ("配置名", 180),
            "count": ("商品数", 80),
            "updated": ("更新时间", 160),
        }
        for key, (title, width) in columns.items():
            self._config_tree.heading(key, text=title)
            self._config_tree.column(key, width=width, anchor="w")

    def refresh(self) -> None:
        accounts = self._dashboard.list_accounts()
        configs = self._dashboard.list_configs()
        summary = self._dashboard.get_summary()
        self._accounts_cache = accounts

        valid_ids = {x.user_id for x in accounts}
        self._purchase_user_ids = {x for x in self._purchase_user_ids if x in valid_ids}
        self._update_purchase_scope_text()

        self._summary_vars["total_accounts"].set(str(summary.total_accounts))
        self._summary_vars["logged_in_accounts"].set(str(summary.logged_in_accounts))
        self._summary_vars["api_key_accounts"].set(str(summary.api_key_accounts))
        self._summary_vars["total_configs"].set(str(summary.total_configs))
        self._summary_vars["total_products"].set(str(summary.total_products))

        self._account_tree.delete(*self._account_tree.get_children())
        for account in accounts:
            self._account_tree.insert(
                "",
                "end",
                values=(
                    account.user_id,
                    account.name,
                    "已登录" if account.login else "未登录",
                    "已配置" if account.has_api_key else "未配置",
                    account.proxy or "直连",
                    account.last_updated or "-",
                ),
            )

        self._config_tree.delete(*self._config_tree.get_children())
        self._configs_by_name = {cfg.name: cfg for cfg in configs}
        config_names = [cfg.name for cfg in configs if cfg.name]
        self._scan_config_combo["values"] = config_names
        if config_names and self._scan_config_var.get() not in config_names:
            self._scan_config_var.set(config_names[0])
        if not config_names:
            self._scan_config_var.set("")

        for cfg in configs:
            self._config_tree.insert(
                "",
                "end",
                values=(cfg.name, len(cfg.products), cfg.last_updated or "-"),
            )

        self._products_text.delete("1.0", tk.END)
        self._products_text.insert("1.0", "选择左侧配置查看商品规则详情。")

    def _update_purchase_scope_text(self) -> None:
        if not self._purchase_user_ids:
            self._purchase_scope_var.set("购买账号：全部已登录账号")
        else:
            self._purchase_scope_var.set(f"购买账号：已选择 {len(self._purchase_user_ids)} 个")

    def _clear_purchase_scope(self) -> None:
        self._purchase_user_ids.clear()
        self._update_purchase_scope_text()

    def _open_purchase_scope_dialog(self) -> None:
        accounts = [x for x in self._accounts_cache if x.user_id]
        if not accounts:
            messagebox.showwarning("无可选账号", "当前没有可用账号。")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("设置可购买账号")
        dialog.geometry("620x420")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text="说明：不勾选表示全部已登录账号可购买；勾选后仅选中账号可购买。",
        ).pack(anchor="w", padx=12, pady=(10, 6))

        listbox = tk.Listbox(dialog, selectmode=tk.EXTENDED)
        listbox.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        for i, acc in enumerate(accounts):
            login_text = "已登录" if acc.login else "未登录"
            api_text = "有 API" if acc.has_api_key else "无 API"
            listbox.insert(tk.END, f"{acc.user_id} | {acc.name} | {login_text} | {api_text}")
            if acc.user_id in self._purchase_user_ids:
                listbox.selection_set(i)

        btns = ttk.Frame(dialog)
        btns.pack(fill="x", padx=12, pady=(0, 10))

        def _select_all() -> None:
            listbox.selection_set(0, tk.END)

        def _clear_all() -> None:
            listbox.selection_clear(0, tk.END)

        def _save() -> None:
            selected_indices = listbox.curselection()
            self._purchase_user_ids = {accounts[i].user_id for i in selected_indices}
            self._update_purchase_scope_text()
            dialog.destroy()

        ttk.Button(btns, text="全选", command=_select_all).pack(side="left")
        ttk.Button(btns, text="清空", command=_clear_all).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="保存", command=_save).pack(side="right")

    def _on_config_selected(self, _event: object) -> None:
        selected = self._config_tree.selection()
        if not selected:
            return

        values = self._config_tree.item(selected[0], "values")
        if not values:
            return

        name = str(values[0])
        config = self._configs_by_name.get(name)
        if not config:
            return

        lines: list[str] = [f"配置：{config.name}", f"商品数：{len(config.products)}", ""]
        for idx, item in enumerate(config.products, start=1):
            lines.extend(
                [
                    f"{idx}. {item.item_name or item.item_id}",
                    f"   item_id: {item.item_id}",
                    f"   wear: {item.minwear} ~ {item.max_wear}",
                    f"   max_price: {item.max_price}",
                    f"   market_hash_name: {item.market_hash_name or '-'}",
                    "",
                ]
            )

        self._products_text.delete("1.0", tk.END)
        self._products_text.insert("1.0", "\n".join(lines))

    def launch_legacy_cli(self) -> None:
        if not messagebox.askyesno("确认", "将打开旧版 CLI 扫描窗口，是否继续？"):
            return
        try:
            self._cli_runtime.launch_legacy_cli_detached()
            messagebox.showinfo("已启动", "旧版 CLI 已在新窗口启动。")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("启动失败", str(exc))

    def start_scan(self) -> None:
        config_name = self._scan_config_var.get().strip()
        query_only = bool(self._scan_query_only_var.get())
        purchase_user_ids = sorted(self._purchase_user_ids) if self._purchase_user_ids else None
        ok, msg = self._scan.start_scan(
            config_name,
            query_only=query_only,
            purchase_user_ids=purchase_user_ids,
        )
        if ok:
            messagebox.showinfo("扫描启动", msg)
        else:
            messagebox.showerror("扫描启动失败", msg)
        self._render_scan_status()

    def stop_scan(self) -> None:
        ok, msg = self._scan.stop_scan()
        if ok:
            messagebox.showinfo("扫描停止", msg)
        else:
            messagebox.showwarning("扫描停止", msg)
        self._render_scan_status()

    def _render_scan_status(self) -> None:
        status = self._scan.get_status()
        running = bool(status.get("running"))
        query_only = bool(status.get("query_only"))
        config_name = status.get("config_name") or "-"
        query_count = int(status.get("query_count", 0) or 0)
        found_count = int(status.get("found_count", 0) or 0)
        purchased_count = int(status.get("purchased_count", 0) or 0)
        msg = str(status.get("message", "") or "")

        if query_only:
            mode_text = "仅查询"
        elif status.get("purchase_scope") == "selected":
            selected_count = int(status.get("purchase_selected_count", 0) or 0)
            mode_text = f"查询+购买(指定{selected_count}个账号)"
        else:
            mode_text = "查询+购买(全部)"

        run_text = "运行中" if running else "已停止"
        self._scan_status_var.set(
            f"扫描状态：{run_text} | 模式：{mode_text} | 配置：{config_name} | "
            f"查询：{query_count} 命中：{found_count} 购买：{purchased_count} | {msg}"
        )

        logs = status.get("logs", [])
        if isinstance(logs, list) and len(logs) != self._last_log_line_count:
            self._set_log_lines(logs)
            self._last_log_line_count = len(logs)

    def _poll_scan_status_loop(self) -> None:
        self._render_scan_status()
        self._status_poll_job = self.root.after(1000, self._poll_scan_status_loop)

    def _set_log_lines(self, logs: list[str]) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", tk.END)
        self._log_text.insert("1.0", "\n".join(logs[-200:]))
        self._log_text.see(tk.END)
        self._log_text.configure(state="disabled")

    def _on_close(self) -> None:
        if self._status_poll_job is not None:
            self.root.after_cancel(self._status_poll_job)
            self._status_poll_job = None
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_gui(
    dashboard_use_case: DashboardQueryUseCase,
    scan_use_case: ScanControlUseCase,
    cli_runtime: LegacyCliRuntime,
) -> None:
    MainWindow(dashboard_use_case, scan_use_case, cli_runtime).run()
