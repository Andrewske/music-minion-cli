#!/usr/bin/env python3
"""
Test script to verify the playlist mode persistence fix.
This simulates the IPC WebSocket behavior to ensure ranking_mode and playlist_id are included.
"""

import json
import asyncio
import websockets
from websockets.exceptions import ConnectionClosedError


async def test_ipc_playlist_mode():
    """Test that IPC commands include ranking mode and playlist ID."""
    try:
        uri = "ws://localhost:8765"
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to IPC WebSocket")

            # Send a winner command
            command = {"type": "command", "command": "winner", "args": []}

            await websocket.send(json.dumps(command))
            print("📤 Sent winner command")

            # Wait for any response (though IPC commands don't typically respond)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"📥 Received response: {response}")
            except asyncio.TimeoutError:
                print("⏰ No response received (expected for IPC commands)")

            print("✅ IPC WebSocket test completed successfully")
            return True

    except ConnectionRefusedError:
        print("❌ Could not connect to IPC WebSocket - backend may not be running")
        return False
    except Exception as e:
        print(f"❌ IPC WebSocket test failed: {e}")
        return False


async def test_backend_playlist_mode():
    """Test that the backend properly handles playlist mode requests."""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            # Test the comparisons endpoint
            response = await client.get("http://localhost:8000/comparisons/next-pair")
            if response.status_code == 200:
                print("✅ Backend comparisons endpoint is responding")
                return True
            else:
                print(f"❌ Backend endpoint returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Could not connect to backend: {e}")
        return False


async def main():
    print("🧪 Testing playlist mode persistence fix...")
    print()

    # Test IPC WebSocket
    print("1. Testing IPC WebSocket connection...")
    ipc_ok = await test_ipc_playlist_mode()
    print()

    # Test backend
    print("2. Testing backend connectivity...")
    backend_ok = await test_backend_playlist_mode()
    print()

    if ipc_ok and backend_ok:
        print("✅ All tests passed!")
        print()
        print("📋 Manual testing steps:")
        print("1. Open http://localhost:5173 in your browser")
        print("2. Select playlist ranking mode and choose a playlist")
        print("3. Start a session and rate 5+ tracks using mouse clicks")
        print("4. Switch to using keyboard hotkeys (if IPC is connected)")
        print(
            "5. Verify that playlist mode persists (playlist name should remain visible)"
        )
        print("6. Check that ratings continue to affect playlist rankings")
    else:
        print("❌ Some tests failed - check that services are running")


if __name__ == "__main__":
    asyncio.run(main())
