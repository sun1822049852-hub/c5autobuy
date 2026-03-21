from __future__ import annotations


class ApplyQueryItemRuntimeUseCase:
    def __init__(self, query_config_repository, query_runtime_service) -> None:
        self._query_config_repository = query_config_repository
        self._query_runtime_service = query_runtime_service

    def execute(self, *, config_id: str, query_item_id: str) -> dict[str, str]:
        config = self._query_config_repository.get_config(config_id)
        if config is None:
            raise KeyError(config_id)

        if all(str(item.query_item_id) != str(query_item_id) for item in config.items):
            raise KeyError(query_item_id)

        apply_runtime = getattr(self._query_runtime_service, "apply_query_item_runtime", None)
        if not callable(apply_runtime):
            return {
                "status": "skipped_inactive",
                "message": "当前配置未在运行，已跳过热应用",
                "config_id": str(config_id),
                "query_item_id": str(query_item_id),
            }
        return dict(apply_runtime(config_id=str(config_id), query_item_id=str(query_item_id)))
