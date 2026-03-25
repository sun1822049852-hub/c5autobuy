from __future__ import annotations


class UpdatePurchaseUiPreferencesUseCase:
    def __init__(self, repository, query_config_repository) -> None:
        self._repository = repository
        self._query_config_repository = query_config_repository

    def execute(self, *, selected_config_id: str | None) -> dict[str, object]:
        normalized_config_id = str(selected_config_id or "").strip() or None
        if normalized_config_id is None:
            preferences = self._repository.clear_selected_config()
            return {
                "selected_config_id": None,
                "updated_at": None,
            }
        if self._query_config_repository.get_config(normalized_config_id) is None:
            raise KeyError("查询配置不存在")
        preferences = self._repository.set_selected_config(normalized_config_id)
        return {
            "selected_config_id": str(getattr(preferences, "selected_config_id", "") or "") or None,
            "updated_at": getattr(preferences, "updated_at", None),
        }
