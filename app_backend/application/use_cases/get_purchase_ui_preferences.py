from __future__ import annotations


class GetPurchaseUiPreferencesUseCase:
    def __init__(self, repository, query_config_repository) -> None:
        self._repository = repository
        self._query_config_repository = query_config_repository

    def execute(self) -> dict[str, object]:
        preferences = self._repository.get()
        selected_config_id = str(getattr(preferences, "selected_config_id", "") or "").strip() or None
        if selected_config_id and self._query_config_repository.get_config(selected_config_id) is None:
            self._repository.clear_selected_config()
            return {
                "selected_config_id": None,
                "updated_at": None,
            }
        return self._serialize(preferences)

    @staticmethod
    def _serialize(preferences) -> dict[str, object]:
        selected_config_id = str(getattr(preferences, "selected_config_id", "") or "").strip() or None
        return {
            "selected_config_id": selected_config_id,
            "updated_at": getattr(preferences, "updated_at", None) if selected_config_id else None,
        }
