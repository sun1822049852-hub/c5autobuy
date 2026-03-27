from __future__ import annotations

import asyncio

from app_backend.workers.tasks.login_task import run_login_task


class StartLoginTaskUseCase:
    def __init__(
        self,
        repository,
        task_manager,
        login_adapter,
        bundle_repository,
        purchase_runtime_service=None,
        open_api_binding_sync_service=None,
    ) -> None:
        self._repository = repository
        self._task_manager = task_manager
        self._login_adapter = login_adapter
        self._bundle_repository = bundle_repository
        self._purchase_runtime_service = purchase_runtime_service
        self._open_api_binding_sync_service = open_api_binding_sync_service

    def execute(self, account_id: str):
        account = self._repository.get_account(account_id)
        if account is None:
            raise KeyError(account_id)

        task = self._task_manager.create_task(task_type="login")
        asyncio.create_task(
            run_login_task(
                task_id=task.task_id,
                account_id=account_id,
                repository=self._repository,
                task_manager=self._task_manager,
                login_adapter=self._login_adapter,
                bundle_repository=self._bundle_repository,
                purchase_runtime_service=self._purchase_runtime_service,
                open_api_binding_sync_service=self._open_api_binding_sync_service,
            )
        )
        return task

