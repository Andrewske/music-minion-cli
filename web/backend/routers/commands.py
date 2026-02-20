"""Commands router for broadcasting commands to web clients."""

from fastapi import APIRouter

from ..sync_manager import sync_manager

router = APIRouter()


@router.post("/commands/broadcast")
async def broadcast_command(command: str) -> dict:
    """Broadcast a command to all connected web clients.

    Used by CLI to send commands like play1/play2 that need to reach
    the frontend via WebSocket (sync_manager), not IPC.
    """
    await sync_manager.broadcast("command", {"command": command})
    return {"status": "sent", "command": command}
