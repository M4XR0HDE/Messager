#!/usr/bin/env python3
"""
Enhanced group Server with Multiple Features
- Usernames/nicknames
- Private messages
- Chat rooms/channels
- Message timestamps
- Message history
- Fun commands
- Basic encryption
"""

import asyncio
import websockets
import json
import logging
import os
from datetime import datetime
from typing import Dict, Set, List
import random
import base64
from cryptography.fernet import Fernet
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chat_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ChatServer:
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port

        # Connected clients: websocket -> client info
        self.clients: Dict[websockets.WebSocketServerProtocol, dict] = {}

        # Chat rooms: room_name -> set of websockets
        self.rooms: Dict[str, Set[websockets.WebSocketServerProtocol]] = {
            'general': set(),
            'random': set(),
            'tech': set()
        }

        # Message history: room_name -> list of messages
        self.message_history: Dict[str, List[dict]] = {
            'general': [],
            'random': [],
            'tech': []
        }

        # Encryption key (in production, this should be securely managed)
        self.cipher_key = Fernet.generate_key()
        self.cipher = Fernet(self.cipher_key)

        # Load message history from files
        self.load_message_history()

        logger.info(f"Chat server initialized on {host}:{port}")

    def load_message_history(self):
        """Load message history from files"""
        try:
            for room in self.rooms.keys():
                filename = f"chat_history_{room}.json"
                if os.path.exists(filename):
                    with open(filename, 'r', encoding='utf-8') as f:
                        self.message_history[room] = json.load(f)
                        logger.info(
                            f"Loaded {len(self.message_history[room])} messages for room '{room}'")
        except Exception as e:
            logger.error(f"Error loading message history: {e}")

    def save_message_history(self, room_name: str):
        """Save message history to file"""
        try:
            filename = f"chat_history_{room_name}.json"
            # Keep only last 1000 messages to prevent files from getting too large
            recent_messages = self.message_history[room_name][-1000:]
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(recent_messages, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving message history for {room_name}: {e}")

    async def register_client(self, websocket, path):
        """Register a new client connection"""
        client_info = {
            'username': None,
            'current_room': 'general',
            'joined_at': datetime.now().isoformat(),
            'encrypted': False
        }
        self.clients[websocket] = client_info
        logger.info(f"New client connected from {websocket.remote_address}")

        # Send welcome message and room list
        await self.send_to_client(websocket, {
            'type': 'system',
            'message': 'Welcome to the Enhanced Chat Server! Please set your username with /username <name>',
            'rooms': list(self.rooms.keys()),
            'commands': ['/help', '/username', '/join', '/msg', '/who', '/joke', '/roll', '/encrypt', '/history']
        })

    async def unregister_client(self, websocket):
        """Unregister a client connection"""
        if websocket in self.clients:
            client_info = self.clients[websocket]
            username = client_info.get('username', 'Unknown')
            current_room = client_info.get('current_room', 'general')

            # Remove from room
            if current_room in self.rooms:
                self.rooms[current_room].discard(websocket)

                # Notify room about user leaving
                if username:
                    await self.broadcast_to_room(current_room, {
                        'type': 'system',
                        'message': f"{username} left the chat",
                        'timestamp': datetime.now().isoformat()
                    }, exclude=websocket)

            del self.clients[websocket]
            logger.info(f"Client {username} disconnected")

    async def send_to_client(self, websocket, message_data):
        """Send message to a specific client"""
        try:
            message = json.dumps(message_data)
            await websocket.send(message)
        except websockets.exceptions.ConnectionClosed:
            await self.unregister_client(websocket)
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")

    async def broadcast_to_room(self, room_name: str, message_data, exclude=None):
        """Broadcast message to all clients in a room"""
        if room_name not in self.rooms:
            return

        # Add to message history
        self.message_history[room_name].append(message_data)

        # Save history periodically (every 10 messages)
        if len(self.message_history[room_name]) % 10 == 0:
            self.save_message_history(room_name)

        # Send to all clients in room
        disconnected = []
        for client_websocket in self.rooms[room_name]:
            if client_websocket != exclude:
                try:
                    await self.send_to_client(client_websocket, message_data)
                except:
                    disconnected.append(client_websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            await self.unregister_client(ws)

    async def handle_command(self, websocket, message: str):
        """Handle special commands"""
        client_info = self.clients[websocket]
        parts = message.split()
        command = parts[0].lower()

        if command == '/help':
            help_text = """
📚 Available Commands:
/username <name> - Set your username
/join <room> - Join a chat room (general, random, tech)
/msg <username> <message> - Send private message
/who - List users in current room
/joke - Get a random joke
/roll - Roll a dice (1-6)
/encrypt - Toggle message encryption
/history - Show recent messages
/rooms - List available rooms
            """
            await self.send_to_client(websocket, {
                'type': 'system',
                'message': help_text
            })

        elif command == '/username' and len(parts) > 1:
            new_username = ' '.join(parts[1:])
            old_username = client_info.get('username')

            # Check if username is already taken
            taken = any(info.get('username') == new_username
                        for info in self.clients.values())

            if taken:
                await self.send_to_client(websocket, {
                    'type': 'error',
                    'message': f"Username '{new_username}' is already taken!"
                })
            else:
                client_info['username'] = new_username
                current_room = client_info['current_room']

                # Add to current room if not already there
                if websocket not in self.rooms[current_room]:
                    self.rooms[current_room].add(websocket)

                # Notify room
                if old_username:
                    message = f"{old_username} changed name to {new_username}"
                else:
                    message = f"{new_username} joined the chat"

                await self.broadcast_to_room(current_room, {
                    'type': 'system',
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                })

        elif command == '/join' and len(parts) > 1:
            new_room = parts[1].lower()
            if client_info.get('username'):
                await self.join_room(websocket, new_room)
            else:
                await self.send_to_client(websocket, {
                    'type': 'error',
                    'message': "Please set a username first with /username <name>"
                })

        elif command == '/msg' and len(parts) > 2:
            target_username = parts[1]
            private_message = ' '.join(parts[2:])
            await self.send_private_message(websocket, target_username, private_message)

        elif command == '/who':
            await self.list_room_users(websocket)

        elif command == '/joke':
            await self.send_joke(websocket)

        elif command == '/roll':
            await self.roll_dice(websocket)

        elif command == '/encrypt':
            client_info['encrypted'] = not client_info.get('encrypted', False)
            status = "enabled" if client_info['encrypted'] else "disabled"
            await self.send_to_client(websocket, {
                'type': 'system',
                'message': f"🔐 Encryption {status}"
            })

        elif command == '/history':
            await self.send_history(websocket)

        elif command == '/rooms':
            rooms_info = []
            for room, clients in self.rooms.items():
                user_count = len(clients)
                rooms_info.append(f"{room} ({user_count} users)")

            await self.send_to_client(websocket, {
                'type': 'system',
                'message': f"Available rooms: {', '.join(rooms_info)}"
            })

        else:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': "Unknown command. Type /help for available commands."
            })

    async def join_room(self, websocket, room_name: str):
        """Move client to a different room"""
        client_info = self.clients[websocket]
        old_room = client_info['current_room']
        username = client_info.get('username', 'Unknown')

        # Create room if it doesn't exist
        if room_name not in self.rooms:
            self.rooms[room_name] = set()
            self.message_history[room_name] = []

        # Remove from old room
        if old_room in self.rooms:
            self.rooms[old_room].discard(websocket)
            await self.broadcast_to_room(old_room, {
                'type': 'system',
                'message': f"{username} left for #{room_name}",
                'timestamp': datetime.now().isoformat()
            }, exclude=websocket)

        # Add to new room
        self.rooms[room_name].add(websocket)
        client_info['current_room'] = room_name

        # Notify new room
        await self.broadcast_to_room(room_name, {
            'type': 'system',
            'message': f"{username} joined from #{old_room}",
            'timestamp': datetime.now().isoformat()
        }, exclude=websocket)

        # Send confirmation to user
        await self.send_to_client(websocket, {
            'type': 'system',
            'message': f"Joined room #{room_name}. Type /who to see who's here."
        })

    async def send_private_message(self, sender_websocket, target_username: str, message: str):
        """Send a private message to another user"""
        sender_info = self.clients[sender_websocket]
        sender_username = sender_info.get('username')

        if not sender_username:
            await self.send_to_client(sender_websocket, {
                'type': 'error',
                'message': "Please set a username first"
            })
            return

        # Find target user
        target_websocket = None
        for ws, info in self.clients.items():
            if info.get('username') == target_username:
                target_websocket = ws
                break

        if not target_websocket:
            await self.send_to_client(sender_websocket, {
                'type': 'error',
                'message': f"User '{target_username}' not found"
            })
            return

        # Handle encryption if enabled
        display_message = message
        if sender_info.get('encrypted', False):
            try:
                encrypted_bytes = self.cipher.encrypt(message.encode())
                display_message = f"[ENCRYPTED] {base64.b64encode(encrypted_bytes).decode()[:50]}..."
            except Exception as e:
                logger.error(f"Encryption error: {e}")

        timestamp = datetime.now().isoformat()

        # Send to target
        await self.send_to_client(target_websocket, {
            'type': 'private_message',
            'from': sender_username,
            'message': message,  # Send original message to target
            'encrypted': sender_info.get('encrypted', False),
            'timestamp': timestamp
        })

        # Confirm to sender
        await self.send_to_client(sender_websocket, {
            'type': 'private_sent',
            'to': target_username,
            'message': display_message,
            'timestamp': timestamp
        })

    async def list_room_users(self, websocket):
        """List all users in the current room"""
        client_info = self.clients[websocket]
        current_room = client_info['current_room']

        users = []
        for ws in self.rooms.get(current_room, []):
            if ws in self.clients:
                username = self.clients[ws].get('username', 'Anonymous')
                encrypted = " 🔐" if self.clients[ws].get(
                    'encrypted', False) else ""
                users.append(f"{username}{encrypted}")

        await self.send_to_client(websocket, {
            'type': 'system',
            'message': f"Users in #{current_room}: {', '.join(users) if users else 'No users'}"
        })

    async def send_joke(self, websocket):
        """Send a random joke"""
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
            "How many programmers does it take to change a light bulb? None, that's a hardware problem! 💡",
            "Why do Python programmers prefer snake_case? Because they can't C the point of camelCase! 🐍",
            "What's the object-oriented way to become wealthy? Inheritance! 💰",
            "Why did the programmer quit his job? He didn't get arrays! 📊",
            "How do you comfort a JavaScript bug? You console it! 🐛",
            "Why don't programmers like nature? It has too many bugs! 🌳",
            "What do you call a programmer from Finland? Nerdic! 🇫🇮"
        ]

        joke = random.choice(jokes)
        await self.send_to_client(websocket, {
            'type': 'system',
            'message': f"🎭 {joke}"
        })

    async def roll_dice(self, websocket):
        """Roll a dice"""
        roll = random.randint(1, 6)
        client_info = self.clients[websocket]
        username = client_info.get('username', 'Someone')
        current_room = client_info['current_room']

        await self.broadcast_to_room(current_room, {
            'type': 'system',
            'message': f"🎲 {username} rolled a {roll}!",
            'timestamp': datetime.now().isoformat()
        })

    async def send_history(self, websocket):
        """Send recent message history"""
        client_info = self.clients[websocket]
        current_room = client_info['current_room']

        history = self.message_history.get(current_room, [])
        recent = history[-10:]  # Last 10 messages

        await self.send_to_client(websocket, {
            'type': 'history',
            'room': current_room,
            'messages': recent
        })

    async def handle_message(self, websocket, message_data):
        """Handle regular chat message"""
        client_info = self.clients[websocket]
        username = client_info.get('username')
        current_room = client_info['current_room']

        if not username:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': "Please set a username first with /username <name>"
            })
            return

        # Handle encryption
        display_message = message_data
        if client_info.get('encrypted', False):
            try:
                encrypted_bytes = self.cipher.encrypt(message_data.encode())
                display_message = f"[ENCRYPTED] {base64.b64encode(encrypted_bytes).decode()}"
            except Exception as e:
                logger.error(f"Encryption error: {e}")

        # Broadcast to room
        await self.broadcast_to_room(current_room, {
            'type': 'message',
            'username': username,
            'message': display_message,
            'encrypted': client_info.get('encrypted', False),
            'timestamp': datetime.now().isoformat(),
            'room': current_room
        })

    async def client_handler(self, websocket, path):
        """Handle individual client connections"""
        await self.register_client(websocket, path)

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    message_type = data.get('type', 'message')

                    if message_type == 'message':
                        content = data.get('content', '').strip()
                        if content.startswith('/'):
                            await self.handle_command(websocket, content)
                        else:
                            await self.handle_message(websocket, content)

                except json.JSONDecodeError:
                    await self.send_to_client(websocket, {
                        'type': 'error',
                        'message': 'Invalid message format'
                    })

                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    await self.send_to_client(websocket, {
                        'type': 'error',
                        'message': 'Error processing your message'
                    })

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            await self.unregister_client(websocket)

    async def start_server(self):
        """Start the WebSocket server"""
        logger.info(f"Starting chat server on {self.host}:{self.port}")

        server = await websockets.serve(
            self.client_handler,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10
        )

        logger.info(f"Chat server running on ws://{self.host}:{self.port}")
        print(
            f"🚀 Enhanced Chat Server running on ws://{self.host}:{self.port}")
        print(f"📁 Message history saved to chat_history_*.json files")
        print(f"📋 Server logs saved to chat_server.log")

        return server

    def cleanup(self):
        """Save all message history on shutdown"""
        logger.info("Shutting down server, saving message history...")
        for room_name in self.message_history:
            self.save_message_history(room_name)


async def main():
    # Create and start server
    chat_server = ChatServer(host='localhost', port=8765)
    server = await chat_server.start_server()

    try:
        # Keep server running
        await server.wait_closed()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    finally:
        chat_server.cleanup()
        logger.info("Server stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        print(f"❌ Server error: {e}")

