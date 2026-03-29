from __future__ import annotations

from fastapi import APIRouter, Request

from app_backend.api.schemas.diagnostics import SidebarDiagnosticsResponse
from app_backend.application.use_cases.get_sidebar_diagnostics import GetSidebarDiagnosticsUseCase

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def _query_runtime_service(request: Request):
    return request.app.state.query_runtime_service


def _purchase_runtime_service(request: Request):
    return request.app.state.purchase_runtime_service


def _task_manager(request: Request):
    return request.app.state.task_manager


@router.get("/sidebar", response_model=SidebarDiagnosticsResponse)
def get_sidebar_diagnostics(request: Request) -> SidebarDiagnosticsResponse:
    payload = GetSidebarDiagnosticsUseCase(
        _query_runtime_service(request),
        _purchase_runtime_service(request),
        _task_manager(request),
    ).execute()
    return SidebarDiagnosticsResponse.model_validate(payload)
