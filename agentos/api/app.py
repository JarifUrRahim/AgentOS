"""FastAPI application exposing both layers of the dual-mode architecture."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agentos.api.schemas import ActionRequest, ChatRequest, MemoryRequest, PermissionRequest
from agentos.config import Settings, settings_from_env
from agentos.core.errors import AgentOSError, SandboxRejected, UnknownActionError
from agentos.core.kernel import AgentOS
from agentos.core.permissions import assess

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application around one :class:`AgentOS` instance."""
    kernel = AgentOS(settings or settings_from_env())
    app = FastAPI(title="AgentOS", version="0.1.0")
    app.state.kernel = kernel

    def get_kernel() -> AgentOS:
        return app.state.kernel

    @app.exception_handler(UnknownActionError)
    def _unknown_action(_: Any, exc: UnknownActionError) -> Any:
        raise HTTPException(status_code=404, detail=str(exc))

    # ------------------------------------------------------------- AI layer

    @app.post("/api/chat")
    def chat(body: ChatRequest, os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        try:
            return os_.handle(body.instruction, actor=body.actor).as_dict()
        except SandboxRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/status")
    def status(os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        return os_.status()

    @app.get("/api/actions")
    def actions(os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        return {
            "actions": [
                {
                    "name": action.name,
                    "agent": action.agent,
                    "description": action.description,
                    "risk": int(action.risk),
                    "reversible": action.reversible,
                    "required_params": list(action.required_params),
                    "decision": assess(
                        action.risk,
                        os_.settings.permission_level,
                        reversible=action.reversible,
                    ).decision.value,
                }
                for action in os_.registry.all()
            ]
        }

    # ------------------------------------------------- manual control layer

    @app.post("/api/actions/run")
    def run_action(body: ActionRequest, os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        try:
            outcome = os_.run_action(
                body.action, body.params, instruction=f"manual: {body.action}", actor=body.actor
            )
        except UnknownActionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SandboxRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return outcome.as_dict()

    # ------------------------------------------------------------ approvals

    @app.get("/api/approvals")
    def approvals(pending: bool = True, os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        queue = os_.approvals.pending() if pending else os_.approvals.all()
        return {"approvals": [a.as_dict() for a in queue]}

    @app.post("/api/approvals/{approval_id}/approve")
    def approve(approval_id: str, os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        try:
            return os_.approve(approval_id).as_dict()
        except SandboxRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except AgentOSError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/approvals/{approval_id}/reject")
    def reject(approval_id: str, os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        try:
            return os_.reject(approval_id).as_dict()
        except AgentOSError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ------------------------------------------- audit, snapshots, recovery

    @app.get("/api/audit")
    def audit(limit: int = 50, os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        return {"entries": os_.audit.entries(limit)}

    @app.get("/api/snapshots")
    def snapshots(os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        return {
            "snapshots": [
                {"id": s.id, "created_at": s.created_at, "label": s.label, "files": s.files}
                for s in os_.snapshots.list()
            ]
        }

    @app.post("/api/snapshots/{snapshot_id}/rollback")
    def rollback(snapshot_id: str, os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        try:
            return os_.rollback(snapshot_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/emergency-stop")
    def emergency_stop(os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        return os_.emergency_stop()

    @app.post("/api/permission-level")
    def permission_level(
        body: PermissionRequest, os_: AgentOS = Depends(get_kernel)
    ) -> dict[str, Any]:
        os_.set_permission_level(body.level, actor=body.actor)
        return os_.status()

    # ----------------------------------------------------------------- memory

    @app.get("/api/memory")
    def memory(os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        return {"memory": os_.memory.snapshot(), "conversation": os_.memory.conversation()}

    @app.post("/api/memory")
    def remember(body: MemoryRequest, os_: AgentOS = Depends(get_kernel)) -> dict[str, Any]:
        os_.memory.remember(body.namespace, body.key, body.value)
        return {"memory": os_.memory.namespace(body.namespace)}

    # -------------------------------------------------------------------- web

    if WEB_DIR.exists():
        app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(WEB_DIR / "index.html")

    return app


app = create_app()
