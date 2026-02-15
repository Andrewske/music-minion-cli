import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from ..sync_manager import sync_manager

router = APIRouter()


@router.websocket("/ws/sync")
async def sync_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time state synchronization."""
    await sync_manager.connect(websocket)
    device_id = None

    try:
        # Send current state immediately (stateful - includes comparison/radio)
        await websocket.send_json({
            "type": "sync:full",
            "data": sync_manager.get_current_state(),
        })

        # Handle incoming messages
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "device:register":
                    # Register device
                    device_id = data.get("id")
                    device_name = data.get("name", "Unknown Device")
                    if device_id:
                        await sync_manager.register_device(device_id, device_name, websocket)
                        logger.info(f"Device registered: {device_id} ({device_name})")

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from WebSocket: {message}")

    except WebSocketDisconnect:
        sync_manager.disconnect(websocket)

        # Start grace period for device if registered
        if device_id:
            logger.info(f"Device disconnected, starting grace period: {device_id}")
            await sync_manager.unregister_device(device_id)
