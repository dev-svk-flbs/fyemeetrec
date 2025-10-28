#!/usr/bin/env python3
"""
WebSocket Server for Remote Meeting Recording Control
Runs on ops.fyelabs.com to send recording commands to client machines
"""

import asyncio
import websockets
import json
from datetime import datetime

class MeetingControlServer:
    def __init__(self, host="0.0.0.0", port=8769):
        self.host = host
        self.port = port
        self.connected_clients = set()
        
    async def register_client(self, websocket):
        """Register a new client connection"""
        self.connected_clients.add(websocket)
        print(f"✅ Client connected: {websocket.remote_address}")
        print(f"📊 Total clients: {len(self.connected_clients)}")
    
    async def unregister_client(self, websocket):
        """Unregister a client connection"""
        self.connected_clients.discard(websocket)
        print(f"❌ Client disconnected: {websocket.remote_address}")
        print(f"📊 Total clients: {len(self.connected_clients)}")
    
    async def send_message(self, websocket, message_type, data):
        """Send message to a client"""
        try:
            message = {
                "type": message_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            await websocket.send(json.dumps(message))
            print(f"📤 Sent to {websocket.remote_address}: {message_type}")
        except Exception as e:
            print(f"❌ Error sending message: {e}")
    
    async def broadcast_message(self, message_type, data):
        """Broadcast message to all connected clients"""
        if self.connected_clients:
            message = {
                "type": message_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            message_json = json.dumps(message)
            
            # Send to all clients
            await asyncio.gather(
                *[client.send(message_json) for client in self.connected_clients],
                return_exceptions=True
            )
            print(f"📢 Broadcast to {len(self.connected_clients)} clients: {message_type}")
    
    async def handle_client_message(self, websocket, message):
        """Handle incoming message from client"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            msg_data = data.get('data', {})
            
            print(f"\n📥 Received from {websocket.remote_address}: {msg_type}")
            print(f"   Data: {json.dumps(msg_data, indent=2)}")
            
            # Log client responses
            if msg_type == 'client_connected':
                print(f"   ✅ Client ready: {msg_data.get('hostname', 'unknown')}")
            
            elif msg_type == 'start_confirmed':
                print(f"   ✅ Recording started successfully")
                print(f"      Meeting: {msg_data.get('subject', 'N/A')}")
                print(f"      Duration: {msg_data.get('duration', 0)} minutes")
            
            elif msg_type == 'start_failed':
                print(f"   ❌ Recording start failed")
                print(f"      Reason: {msg_data.get('reason', 'Unknown')}")
            
            elif msg_type == 'stop_confirmed':
                print(f"   ✅ Recording stopped successfully")
                print(f"      Actual duration: {msg_data.get('duration_actual', 0)} seconds")
            
            elif msg_type == 'stop_failed':
                print(f"   ❌ Recording stop failed")
                print(f"      Reason: {msg_data.get('reason', 'Unknown')}")
            
            elif msg_type == 'recording_warning':
                print(f"   ⚠️  Recording warning")
                print(f"      Warning: {msg_data.get('warning', 'Unknown')}")
            
            elif msg_type == 'recording_status':
                print(f"   📹 Recording in progress")
                print(f"      Elapsed: {msg_data.get('elapsed', 0)}s")
                print(f"      Remaining: {msg_data.get('remaining', 0)}s")
            
            elif msg_type == 'app_health':
                alive = msg_data.get('alive', False)
                recording = msg_data.get('recording_active', False)
                if alive:
                    status_icon = "💚" if recording else "💛"
                    print(f"   {status_icon} Flask app health: {'Recording' if recording else 'Idle'}")
                else:
                    print(f"   ❤️‍🩹 Flask app health: DOWN")
                    if msg_data.get('error'):
                        print(f"      Error: {msg_data.get('error')}")
            
            elif msg_type == 'app_alert':
                print(f"   🚨 ALERT: {msg_data.get('alert', 'Unknown alert')}")
                print(f"      Error: {msg_data.get('error', 'Unknown')}")
            
            elif msg_type == 'pong':
                print(f"   🏓 Pong received")
        
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON from client: {e}")
        except Exception as e:
            print(f"❌ Error handling client message: {e}")
    
    async def handle_client(self, websocket, path):
        """Handle a client connection"""
        await self.register_client(websocket)
        
        try:
            async for message in websocket:
                await self.handle_client_message(websocket, message)
        
        except websockets.exceptions.ConnectionClosed:
            print(f"Connection closed normally: {websocket.remote_address}")
        except Exception as e:
            print(f"❌ Error in client handler: {e}")
        finally:
            await self.unregister_client(websocket)
    
    async def send_test_start_command(self):
        """Send a test start recording command (for testing)"""
        # Wait for clients to connect
        print("⏳ Waiting 5 seconds for clients to connect...")
        await asyncio.sleep(5)
        
        # Check if any clients connected
        if not self.connected_clients:
            print("⚠️  No clients connected yet. Waiting longer...")
            await asyncio.sleep(5)
        
        if not self.connected_clients:
            print("❌ Still no clients connected. Test command aborted.")
            return
        
        # HARDCODED TEST VALUES - Replace these with actual event ID and duration
        test_meeting_id = "AAMkAGM2ZjJkMDJkLWE4ZDAtNGE4My1iNWYyLTJmYjJhZjJhNjFhNABGAAAAAACqGX5cOJWYRJtN9pPDpw4iBwCt0Z-jYRzCRoWPpJW4_HzrAAAADGqOAACt0Z-jYRzCRoWPpJW4_HzrAACJCOAAAA=="  # Replace with actual calendar_event_id
        test_duration = 2  # minutes
        
        print("\n" + "="*60)
        print("🧪 SENDING TEST START COMMAND")
        print(f"   Meeting ID: {test_meeting_id}")
        print(f"   Duration: {test_duration} minutes")
        print("="*60 + "\n")
        
        await self.broadcast_message("start_recording", {
            "meeting_id": test_meeting_id,
            "duration": test_duration
        })
    
    async def interactive_console(self):
        """Interactive console for sending commands"""
        await asyncio.sleep(3)  # Wait for initial connection
        
        print("\n" + "="*60)
        print("📋 INTERACTIVE CONSOLE")
        print("="*60)
        print("Commands:")
        print("  start <meeting_id> <duration_minutes>  - Start recording")
        print("  stop                                    - Stop current recording")
        print("  ping                                    - Send ping to all clients")
        print("  status                                  - Show connected clients")
        print("  test                                    - Send test start command")
        print("  quit                                    - Exit server")
        print("="*60 + "\n")
        
        while True:
            try:
                await asyncio.sleep(0.1)  # Non-blocking
                # Note: For a real interactive console, you'd need aioconsole
                # For now, this is just a placeholder
            except KeyboardInterrupt:
                break
    
    async def start_server(self):
        """Start the WebSocket server"""
        print("="*60)
        print("🚀 Meeting Control Server Starting")
        print(f"   Host: {self.host}")
        print(f"   Port: {self.port}")
        print("="*60 + "\n")
        
        # Start WebSocket server
        async with websockets.serve(self.handle_client, self.host, self.port):
            print(f"✅ Server listening on ws://{self.host}:{self.port}")
            print("⏳ Waiting for client connections...\n")
            
            # Uncomment one of these for testing:
            
            # Option 1: Send automatic test command after 5 seconds
            asyncio.create_task(self.send_test_start_command())
            
            # Option 2: Interactive console (requires aioconsole library)
            # asyncio.create_task(self.interactive_console())
            
            # Keep server running
            await asyncio.Future()  # Run forever

async def main():
    """Main entry point"""
    server = MeetingControlServer(host="0.0.0.0", port=8765)
    
    try:
        await server.start_server()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down server...")

if __name__ == "__main__":
    asyncio.run(main())
