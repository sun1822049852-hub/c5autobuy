# Query Item Detail Backfill Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让“新增商品”在不要求前端传账号的前提下，由后端全局轮询已登录且带 `NC5_accessToken` 的账号，自动补全商品基础信息并落库。

**Architecture:** 保持现有 `AddQueryItemUseCase` API 不变，在 `infrastructure/query/collectors` 下补一个账号轮询选择器和真实商品详情抓取器。`ProductDetailCollector` 默认组装这套真实实现；抓取链内部复用现有 `RuntimeAccountAdapter`、`aiohttp` 会话和 `x-sign` 生成模式，失败时自动切换到下一个候选账号。

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, aiohttp, pytest

---

## Chunk 1: 账号轮询选择器

### Task 1: 为商品补全建立后端全局轮询账号选择器

**Files:**
- Create: `app_backend/infrastructure/query/collectors/detail_account_selector.py`
- Test: `tests/backend/test_detail_account_selector.py`

- [ ] **Step 1: 写失败测试，覆盖候选过滤和轮询顺序**

```python
def test_selector_only_returns_logged_in_accounts_with_token():
    repository = FakeRepository([
        build_account("a1", cookie_raw=None),
        build_account("a2", cookie_raw="NC5_accessToken=token-2"),
        build_account("a3", cookie_raw="foo=bar; NC5_accessToken=token-3"),
    ])

    selector = DetailAccountSelector(repository)

    assert selector.acquire_next_account().account_id == "a2"
    assert selector.acquire_next_account().account_id == "a3"
    assert selector.acquire_next_account().account_id == "a2"
```

- [ ] **Step 2: 运行测试确认它先失败**

Run: `pytest tests/backend/test_detail_account_selector.py -v`

Expected: FAIL，因为选择器文件还不存在。

- [ ] **Step 3: 写最小实现**

```python
class DetailAccountSelector:
    def __init__(self, repository) -> None:
        self._repository = repository
        self._next_index = 0

    def acquire_next_account(self):
        candidates = [item for item in self._repository.list_accounts() if _is_eligible(item)]
        if not candidates:
            raise ValueError("没有可用于商品信息补全的已登录账号")
        account = candidates[self._next_index % len(candidates)]
        self._next_index = (self._next_index + 1) % len(candidates)
        return account
```

- [ ] **Step 4: 扩展失败测试，覆盖账号失败后的切换和空候选报错**

```python
def test_selector_mark_failure_skips_to_next_account():
    ...

def test_selector_raises_when_no_eligible_account():
    ...
```

- [ ] **Step 5: 跑测试确认全部转绿**

Run: `pytest tests/backend/test_detail_account_selector.py -v`

Expected: PASS

## Chunk 2: 真实商品详情抓取链

### Task 2: 先补真实抓取链的失败测试

**Files:**
- Modify: `tests/backend/test_query_item_collectors.py`
- Create: `tests/backend/test_product_detail_fetcher.py`

- [ ] **Step 1: 为 preview 接口和 search 接口结果合并写失败测试**

```python
async def test_product_detail_fetcher_merges_preview_and_market_hash_name():
    fetcher = ProductDetailFetcher(
        selector=FakeSelector([build_account("a1", cookie_raw="NC5_accessToken=token; NC5_deviceId=device")]),
        session_factory=...,
        xsign_wrapper=FakeSigner(),
    )

    detail = await fetcher.fetch(external_item_id="1380979899390267393", product_url="https://www.c5game.com/...")

    assert detail["item_name"] == "AK-47 | Redline"
    assert detail["market_hash_name"] == "AK-47 | Redline (Field-Tested)"
    assert detail["min_wear"] == 0.1
    assert detail["max_wear"] == 0.7
    assert detail["last_market_price"] == 123.45
```

- [ ] **Step 2: 为账号失败切换写失败测试**

```python
async def test_product_detail_fetcher_switches_account_after_request_failure():
    ...
```

- [ ] **Step 3: 跑新增测试，确认先失败**

Run: `pytest tests/backend/test_query_item_collectors.py tests/backend/test_product_detail_fetcher.py -v`

Expected: FAIL，因为真实 fetcher 还不存在。

### Task 3: 写最小真实实现并接回 `ProductDetailCollector`

**Files:**
- Create: `app_backend/infrastructure/query/collectors/product_detail_fetcher.py`
- Modify: `app_backend/infrastructure/query/collectors/product_detail_collector.py`

- [ ] **Step 1: 实现 preview 请求**

```python
class ProductDetailFetcher:
    PREVIEW_API_PATH_TEMPLATE = "support/trade/product/batch/v1/preview/{item_id}"

    async def _fetch_preview_payload(...):
        ...
```

- [ ] **Step 2: 实现 search 请求，只提取 `market_hash_name`**

```python
    SEARCH_API_PATH_TEMPLATE = "search/v2/sell/{item_id}/list"

    async def _fetch_market_payload(...):
        ...
```

- [ ] **Step 3: 在 fetch 中合并字段并处理账号切换**

```python
    async def fetch(...):
        for _ in range(candidate_count):
            account = self._selector.acquire_next_account()
            try:
                preview = await self._fetch_preview_payload(...)
                market = await self._fetch_market_payload(...)
                return self._merge_payloads(preview, market, ...)
            except Exception:
                continue
        raise ValueError("商品信息补全失败")
```

- [ ] **Step 4: 让 `ProductDetailCollector()` 默认接真实 fetcher**

```python
class ProductDetailCollector:
    def __init__(self, *, fetcher=None) -> None:
        self._fetcher = fetcher or ProductDetailFetcher().fetch
```

- [ ] **Step 5: 跑 collector/fetcher 测试，确认转绿**

Run: `pytest tests/backend/test_query_item_collectors.py tests/backend/test_product_detail_fetcher.py -v`

Expected: PASS

## Chunk 3: 主入口接线和接口验证

### Task 4: 让主应用默认拥有真实商品补全能力

**Files:**
- Modify: `app_backend/main.py`
- Modify: `tests/backend/test_backend_main_entry.py`

- [ ] **Step 1: 写失败测试，证明 `create_app()` 默认注入的 collector 可调用真实 fetcher**

```python
def test_create_app_wires_real_product_detail_collector():
    app = create_app(...)
    collector = app.state.product_detail_collector
    assert isinstance(collector, ProductDetailCollector)
    assert collector.has_default_fetcher() is True
```

- [ ] **Step 2: 跑测试确认先失败**

Run: `pytest tests/backend/test_backend_main_entry.py::test_create_app_wires_real_product_detail_collector -v`

Expected: FAIL，因为当前默认 fetcher 是空壳。

- [ ] **Step 3: 接线 `DetailAccountSelector` 和 `ProductDetailFetcher` 到 `create_app()`**

```python
detail_account_selector = DetailAccountSelector(repository)
product_detail_collector = ProductDetailCollector(
    fetcher=ProductDetailFetcher(selector=detail_account_selector).fetch,
)
```

- [ ] **Step 4: 跑主入口测试确认转绿**

Run: `pytest tests/backend/test_backend_main_entry.py -v`

Expected: PASS

### Task 5: 走一次新增商品接口的真实装配验证

**Files:**
- Modify: `tests/backend/test_query_config_routes.py`

- [ ] **Step 1: 增加一条失败测试，验证不传 `account_id` 也会调用真实 collector 依赖**

```python
async def test_add_query_item_uses_backend_account_selector_instead_of_frontend_account_id(client, app):
    ...
```

- [ ] **Step 2: 跑路由测试确认先失败**

Run: `pytest tests/backend/test_query_config_routes.py::test_add_query_item_uses_backend_account_selector_instead_of_frontend_account_id -v`

Expected: FAIL

- [ ] **Step 3: 保持前端请求结构不变，修正测试装配**

```python
app.state.product_detail_collector = ProductDetailCollector(fetcher=fake_fetcher)
```

- [ ] **Step 4: 跑路由测试确认通过**

Run: `pytest tests/backend/test_query_config_routes.py -v`

Expected: PASS

## Chunk 4: 完整验证

### Task 6: 跑最小相关测试集和后端全量测试

**Files:**
- Modify: `README.md`（仅在确有必要时补一句当前进度说明）

- [ ] **Step 1: 跑相关测试集**

Run: `pytest tests/backend/test_detail_account_selector.py tests/backend/test_product_detail_fetcher.py tests/backend/test_query_item_collectors.py tests/backend/test_query_config_routes.py tests/backend/test_backend_main_entry.py -v`

Expected: PASS

- [ ] **Step 2: 跑后端全量测试**

Run: `pytest tests/backend -q`

Expected: PASS

- [ ] **Step 3: 只有在 README 明显缺失该进度时才补文档，然后复跑相关测试**

Run: `pytest tests/backend -q`

Expected: PASS

- [ ] **Step 4: 不执行 git 操作**

Reason: 用户已明确要求不要默认计划和执行 `git commit` / 分支相关动作。
