#!/usr/bin/env python3
"""
WebSocket Server for Remote Meeting Recording Control
Runs on ops.fyelabs.com to send recording commands to client machines
"""

import asyncio
import websockets
import json
from datetime import datetime
from logging_config import setup_logging

# Setup logging
logger = setup_logging("websocket_server")

class MeetingControlServer:
    def __init__(self, host="0.0.0.0", port=8769):
        self.host = host
        self.port = port
        self.connected_clients = set()
        
    async def register_client(self, websocket):
        """Register a new client connection"""
        self.connected_clients.add(websocket)
        logger.info(f"Client connected: {websocket.remote_address}")
        logger.info(f"Total clients: {len(self.connected_clients)}")
    
    async def unregister_client(self, websocket):
        """Unregister a client connection"""
        self.connected_clients.discard(websocket)
        logger.info(f"Client disconnected: {websocket.remote_address}")
        logger.info(f"Total clients: {len(self.connected_clients)}")
    
    async def send_message(self, websocket, message_type, data):
        """Send message to a client"""
        try:
            message = {
                "type": message_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            await websocket.send(json.dumps(message))
            logger.info(f"Sent to {websocket.remote_address}: {message_type}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
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
            logger.info(f"Broadcast to {len(self.connected_clients)} clients: {message_type}")
    
    async def handle_client_message(self, websocket, message):
        """Handle incoming message from client"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            msg_data = data.get('data', {})
            
            logger.info(f"\nReceived from {websocket.remote_address}: {msg_type}")
            logger.info(f"   Data: {json.dumps(msg_data, indent=2)}")
            
            # Log client responses
            if msg_type == 'client_connected':
                hostname = msg_data.get('hostname', 'unknown')
                user = msg_data.get('user', {})
                
                logger.info(f"   Client ready: {hostname}")
                
                if user:
                    logger.info(f"      User: {user.get('username', 'N/A')} ({user.get('email', 'N/A')})")
                    logger.info(f"      User ID: {user.get('user_id', 'N/A')}")
                else:
                    logger.info(f"      User: Not logged in")
            
            elif msg_type == 'start_confirmed':
                logger.info(f"   Recording started successfully")
                logger.info(f"      Meeting: {msg_data.get('subject', 'N/A')}")
                logger.info(f"      Duration: {msg_data.get('duration', 0)} minutes")
            
            elif msg_type == 'start_failed':
                logger.error(f"   Recording start failed")
                logger.error(f"      Reason: {msg_data.get('reason', 'Unknown')}")
            
            elif msg_type == 'stop_confirmed':
                logger.info(f"   Recording stopped successfully")
                logger.info(f"      Actual duration: {msg_data.get('duration_actual', 0)} seconds")
            
            elif msg_type == 'stop_failed':
                logger.error(f"   Recording stop failed")
                logger.error(f"      Reason: {msg_data.get('reason', 'Unknown')}")
            
            elif msg_type == 'recording_warning':
                logger.warning(f"   Recording warning")
                logger.warning(f"      Warning: {msg_data.get('warning', 'Unknown')}")
            
            elif msg_type == 'recording_status':
                logger.info(f"   Recording in progress")
                logger.info(f"      Elapsed: {msg_data.get('elapsed', 0)}s")
                logger.info(f"      Remaining: {msg_data.get('remaining', 0)}s")
            
            elif msg_type == 'app_health':
                alive = msg_data.get('alive', False)
                recording = msg_data.get('recording_active', False)
                recording_type = msg_data.get('recording_type', 'none')
                
                if alive:
                    if recording:
                        if recording_type == 'meeting':
                            meeting = msg_data.get('meeting', {})
                            meeting_subject = meeting.get('subject', 'Unknown')
                            meeting_id = meeting.get('id', 'N/A')
                            logger.info(f"   Flask app health: Recording MEETING")
                            logger.info(f"      Meeting: {meeting_subject}")
                            logger.info(f"      Meeting ID: {meeting_id}")
                        elif recording_type == 'manual':
                            logger.info(f"   Flask app health: Recording MANUAL (hotkey/button)")
                        else:
                            logger.info(f"   Flask app health: Recording")
                    else:
                        logger.info(f"   Flask app health: Idle")
                else:
                    logger.warning(f"   Flask app health: DOWN")
                    if msg_data.get('error'):
                        logger.error(f"      Error: {msg_data.get('error')}")
            
            elif msg_type == 'app_alert':
                logger.error(f"   ALERT: {msg_data.get('alert', 'Unknown alert')}")
                logger.error(f"      Error: {msg_data.get('error', 'Unknown')}")
            
            elif msg_type == 'pong':
                logger.info(f"   Pong received")
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from client: {e}")
        except Exception as e:
            logger.error(f"Error handling client message: {e}")
    
    async def handle_client(self, websocket, path):
        """Handle a client connection"""
        await self.register_client(websocket)
        
        try:
            async for message in websocket:
                await self.handle_client_message(websocket, message)
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed normally: {websocket.remote_address}")
        except Exception as e:
            logger.error(f"Error in client handler: {e}")
        finally:
            await self.unregister_client(websocket)
    
    async def send_test_start_command(self):
        """Send a test start recording command (for testing)"""
        # Wait for clients to connect
        logger.info("Waiting 5 seconds for clients to connect...")
        await asyncio.sleep(5)
        
        # Check if any clients connected
        if not self.connected_clients:
            logger.warning("No clients connected yet. Waiting longer...")
            await asyncio.sleep(5)
        
        if not self.connected_clients:
            logger.error("Still no clients connected. Test command aborted.")
            return
        
        # HARDCODED TEST VALUES - Replace these with actual event ID and duration
        test_meeting_id = "AAMkAGM2ZjJkMDJkLWE4ZDAtNGE4My1iNWYyLTJmYjJhZjJhNjFhNABGAAAAAACqGX5cOJWYRJtN9pPDpw4iBwCt0Z-jYRzCRoWPpJW4_HzrAAAADGqOAACt0Z-jYRzCRoWPpJW4_HzrAACJCOAAAA=="  # Replace with actual calendar_event_id
        test_duration = 2  # minutes
        
        logger.info("\n" + "="*60)
        logger.info("SENDING TEST START COMMAND")
        logger.info(f"   Meeting ID: {test_meeting_id}")
        logger.info(f"   Duration: {test_duration} minutes")
        logger.info("="*60 + "\n")
        
        await self.broadcast_message("start_recording", {
            "meeting_id": test_meeting_id,
            "duration": test_duration
        })
    
    async def interactive_console(self):
        """Interactive console for sending commands"""
        await asyncio.sleep(3)  # Wait for initial connection
        
        logger.info("\n" + "="*60)
        logger.info("INTERACTIVE CONSOLE")
        logger.info("="*60)
        logger.info("Commands:")
        logger.info("  start <meeting_id> <duration_minutes>  - Start recording")
        logger.info("  stop                                    - Stop current recording")
        logger.info("  ping                                    - Send ping to all clients")
        logger.info("  status                                  - Show connected clients")
        logger.info("  test                                    - Send test start command")
        logger.info("  quit                                    - Exit server")
        logger.info("="*60 + "\n")
        
        while True:
            try:
                await asyncio.sleep(0.1)  # Non-blocking
                # Note: For a real interactive console, you'd need aioconsole
                # For now, this is just a placeholder
            except KeyboardInterrupt:
                break
    
    async def start_server(self):
        """Start the WebSocket server"""
        logger.info("="*60)
        logger.info("Meeting Control Server Starting")
        logger.info(f"   Host: {self.host}")
        logger.info(f"   Port: {self.port}")
        logger.info("="*60 + "\n")
        
        # Start WebSocket server
        async with websockets.serve(self.handle_client, self.host, self.port):
            logger.info(f"Server listening on ws://{self.host}:{self.port}")
            logger.info("Waiting for client connections...\n")
            
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
        logger.info("\n\nShutting down server...")

if __name__ == "__main__":
    asyncio.run(main())
