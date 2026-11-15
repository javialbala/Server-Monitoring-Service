"""Estado del control plane (público)."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/health")
async def health(request: Request) -> dict:
    # Información mínima: sin versiones ni motivos técnicos. Siempre 200;
    # el panel interpreta el campo "status".
    agent = await request.app.state.agent_client.health()
    healthy = agent.reachable and agent.docker_reachable
    return {
        "status": "ok" if healthy else "degraded",
        "agent": {"reachable": agent.reachable},
        "docker": {"reachable": agent.docker_reachable},
    }
