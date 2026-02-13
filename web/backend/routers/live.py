from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..sync_manager import sync_manager

router = APIRouter()


@router.websocket("/ws/sync")
async def sync_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time state synchronization."""
    await sync_manager.connect(websocket)
    try:
        # Send current state immediately (stateful - includes comparison/radio)
        await websocket.send_json({
            "type": "sync:full",
            "data": sync_manager.get_current_state(),
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        sync_manager.disconnect(websocket)
