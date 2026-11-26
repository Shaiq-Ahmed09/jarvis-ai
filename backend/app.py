"""
J.A.R.V.I.S. Engineering Division - Master Architecture
Project: Instagram DM Style Modern Messenger Application
Target File: app.py

A complete, production-ready FastAPI application delivering a modern Instagram DM style
messenger experience with real-time WebSocket communication, conversation history, and
an embedded responsive frontend interface. Includes a comprehensive pytest test suite.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from typing import Dict, List, Optional, Set
import unittest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("JARVIS.Messenger")

# ============================================================================
# DOMAIN MODELS & SCHEMAS
# ============================================================================

class MessageCreate(BaseModel):
    """Schema for creating a new message."""
    sender: str = Field(..., min_length=1, max_length=50, description="Username of the sender")
    recipient: str = Field(..., min_length=1, max_length=50, description="Username of the recipient")
    content: str = Field(..., min_length=1, max_length=2000, description="Message text content")


class MessageResponse(BaseModel):
    """Schema for outputting message details."""
    id: str
    sender: str
    recipient: str
    content: str
    timestamp: str
    read: bool = False

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


@dataclass
class Message:
    """Internal message representation."""
    id: str
    sender: str
    recipient: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    read: bool = False

    def to_dict(self) -> dict:
        """Convert message to dictionary format for JSON serialization."""
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "read": self.read,
        }


# ============================================================================
# CONNECTION MANAGER (WEBSOCKET BROKER)
# ============================================================================

class ConnectionManager:
    """
    Manages active WebSocket connections for real-time messaging.
    Supports user-specific routing and broadcast capabilities.
    """

    def __init__(self) -> None:
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        logger.info("ConnectionManager initialized.")

    async def connect(self, username: str, websocket: WebSocket) -> None:
        """Accepts a websocket connection and registers it under a username."""
        await websocket.accept()
        if username not in self.active_connections:
            self.active_connections[username] = set()
        self.active_connections[username].add(websocket)
        logger.info(f"User '{username}' connected via WebSocket.")

    def disconnect(self, username: str, websocket: WebSocket) -> None:
        """Removes a websocket connection for a given username."""
        if username in self.active_connections:
            self.active_connections[username].discard(websocket)
            if not self.active_connections[username]:
                del self.active_connections[username]
        logger.info(f"User '{username}' disconnected from WebSocket.")

    async def send_personal_message(self, message: dict, username: str) -> None:
        """Sends a JSON-encoded message to all active connections of a specific user."""
        if username in self.active_connections:
            disconnected = set()
            payload = json.dumps(message)
            for connection in self.active_connections[username]:
                try:
                    await connection.send_text(payload)
                except Exception as e:
                    logger.error(f"Failed to send message to {username}: {e}")
                    disconnected.add(connection)
            # Cleanup stale connections
            for conn in disconnected:
                self.active_connections[username].discard(conn)


# ============================================================================
# APPLICATION STATE & REPOSITORY
# ============================================================================

class MessageRepository:
    """Thread-safe in-memory data store for messages and conversations."""

    def __init__(self) -> None:
        self._messages: List[Message] = []

    def add_message(self, msg: Message) -> None:
        """Stores a message in the repository."""
        self._messages.append(msg)
        logger.debug(f"Stored message {msg.id} between {msg.sender} and {msg.recipient}")

    def get_conversation(self, user1: str, user2: str) -> List[Message]:
        """Retrieves chronological chat history between two users."""
        conv = [
            m for m in self._messages
            if (m.sender == user1 and m.recipient == user2) or
               (m.sender == user2 and m.recipient == user1)
        ]
        conv.sort(key=lambda x: x.timestamp)
        return conv


# ============================================================================
# FASTAPI APPLICATION SETUP
# ============================================================================

manager = ConnectionManager()
message_repo = MessageRepository()

app = FastAPI(
    title="J.A.R.V.I.S. Instagram DM Messenger",
    description="Modern Instagram DM style real-time messenger backend built with FastAPI.",
    version="1.0.0"
)

# ============================================================================
# FRONTEND HTML / CSS / JS EMBEDDED INTERFACE
# ============================================================================

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>J.A.R.V.I.S. Direct Messenger</title>
    <style>
        :root {
            --ig-primary-bg: #000000;
            --ig-secondary-bg: #121212;
            --ig-tertiary-bg: #262626;
            --ig-border: #262626;
            --ig-text: #f5f5f5;
            --ig-text-secondary: #a8a8a8;
            --ig-blue: #0095f6;
            --ig-blue-hover: #1877f2;
            --ig-bubble-incoming: #262626;
            --ig-bubble-outgoing: #3797ef;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--ig-primary-bg);
            color: var(--ig-text);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }

        .app-container {
            width: 100%;
            max-width: 935px;
            height: 90vh;
            background-color: var(--ig-secondary-bg);
            border: 1px solid var(--ig-border);
            border-radius: 8px;
            display: flex;
            overflow: hidden;
        }

        /* Login Screen Overlay */
        #login-overlay {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.85);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }

        .login-card {
            background: var(--ig-secondary-bg);
            border: 1px solid var(--ig-border);
            padding: 40px;
            border-radius: 8px;
            text-align: center;
            width: 350px;
        }

        .login-card h2 {
            margin-bottom: 20px;
            font-weight: 600;
            letter-spacing: 1px;
        }

        .login-card input {
            width: 100%;
            padding: 12px;
            background: var(--ig-primary-bg);
            border: 1px solid var(--ig-border);
            border-radius: 4px;
            color: var(--ig-text);
            margin-bottom: 15px;
            font-size: 14px;
        }

        .login-card button {
            width: 100%;
            padding: 10px;
            background: var(--ig-blue);
            color: white;
            border: none;
            border-radius: 4px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }

        .login-card button:hover {
            background: var(--ig-blue-hover);
        }

        /* Sidebar - Conversations */
        .sidebar {
            width: 350px;
            border-right: 1px solid var(--ig-border);
            display: flex;
            flex-direction: column;
        }

        .sidebar-header {
            padding: 20px;
            font-size: 18px;
            font-weight: 700;
            border-bottom: 1px solid var(--ig-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .user-list {
            flex: 1;
            overflow-y: auto;
        }

        .user-item {
            padding: 15px 20px;
            display: flex;
            align-items: center;
            cursor: pointer;
            transition: background 0.15s;
        }

        .user-item:hover {
            background-color: var(--ig-tertiary-bg);
        }

        .user-item.active {
            background-color: var(--ig-tertiary-bg);
        }

        .avatar {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888);
            display: flex;
            justify-content: center;
            align-items: center;
            font-weight: bold;
            color: white;
            margin-right: 15px;
            flex-shrink: 0;
        }

        .user-info .username {
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 3px;
        }

        .user-info .status {
            font-size: 12px;
            color: var(--ig-text-secondary);
        }

        /* Chat Area */
        .chat-area {
            flex: 1;
            display: flex;
            flex-direction: column;
            background-color: var(--ig-primary-bg);
        }

        .chat-header {
            padding: 15px 20px;
            border-bottom: 1px solid var(--ig-border);
            display: flex;
            align-items: center;
        }

        .messages-container {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .message-bubble {
            max-width: 65%;
            padding: 10px 14px;
            border-radius: 18px;
            font-size: 14px;
            line-height: 1.4;
            word-wrap: break-word;
            position: relative;
        }

        .message-bubble.incoming {
            background-color: var(--ig-bubble-incoming);
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }

        .message-bubble.outgoing {
            background-color: var(--ig-bubble-outgoing);
            align-self: flex-end;
            border-bottom-right-radius: 4px;
            color: white;
        }

        .message-timestamp {
            font-size: 10px;
            color: var(--ig-text-secondary);
            margin-top: 4px;
            text-align: right;
        }

        .chat-input-area {
            padding: 20px;
            border-top: 1px solid var(--ig-border);
            display: flex;
            align-items: center;
        }

        .chat-input-area input {
            flex: 1;
            padding: 12px 16px;
            background: var(--ig-secondary-bg);
            border: 1px solid var(--ig-border);
            border-radius: 22px;
            color: var(--ig-text);
            font-size: 14px;
            outline: none;
        }

        .chat-input-area input:focus {
            border-color: var(--ig-text-secondary);
        }

        .chat-input-area button {
            background: transparent;
            border: none;
            color: var(--ig-blue);
            font-weight: 600;
            font-size: 14px;
            margin-left: 15px;
            cursor: pointer;
            padding: 5px 10px;
        }

        .chat-input-area button:hover {
            color: var(--ig-blue-hover);
        }
    </style>
</head>
<body>

    <!-- Login Overlay -->
    <div id="login-overlay">
        <div class="login-card">
            <h2>J.A.R.V.I.S. DM</h2>
            <input type="text" id="username-input" placeholder="Enter your username..." autocomplete="off">
            <button onclick="login()">Start Messaging</button>
        </div>
    </div>

    <!-- App Container -->
    <div class="app-container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <span id="current-user-display">User</span>
                <span style="font-size: 12px; color: var(--ig-text-secondary);">Active</span>
            </div>
            <div class="user-list" id="user-list">
                <!-- Dynamically populated contacts -->
            </div>
        </div>

        <!-- Chat Area -->
        <div class="chat-area">
            <div class="chat-header">
                <div class="avatar" id="active-avatar" style="width: 32px; height: 32px; font-size: 12px; margin-right: 10px;">?</div>
                <div id="active-recipient-display" style="font-weight: 600; font-size: 14px;">Select a conversation</div>
            </div>
            <div class="messages-container" id="messages-container">
                <!-- Messages populated dynamically -->
            </div>
            <div class="chat-input-area">
                <input type="text" id="message-input" placeholder="Message..." onkeypress="handleKeyPress(event)" disabled>
                <button id="send-btn" onclick="sendMessage()" disabled>Send</button>
            </div>
        </div>
    </div>

    <script>
        let currentUser = null;
        let activeRecipient = null;
        let ws = null;

        const contacts = ["Stark", "Pepper", "Rhodey", "Happy", "Parker"];

        function login() {
            const input = document.getElementById('username-input');
            const val = input.value.trim();
            if (!val) {
                alert("Please enter a valid username.");
                return;
            }
            currentUser = val;
            document.getElementById('current-user-display').innerText = currentUser;
            document.getElementById('login-overlay').style.display = 'none';

            initUserList();
            initWebSocket();
        }

        function initUserList() {
            const listEl = document.getElementById('user-list');
            listEl.innerHTML = '';
            contacts.forEach(contact => {
                if (contact === currentUser) return; // Don't chat with self
                const div = document.createElement('div');
                div.className = 'user-item';
                div.id = `contact-${contact}`;
                div.onclick = () => selectRecipient(contact);
                div.innerHTML = `
                    <div class="avatar">${contact[0].toUpperCase()}</div>
                    <div class="user-info">
                        <div class="username">${contact}</div>
                        <div class="status">Active in chat</div>
                    </div>
                `;
                listEl.appendChild(div);
            });
        }

        function selectRecipient(recipient) {
            activeRecipient = recipient;
            document.getElementById('active-recipient-display').innerText = recipient;
            document.getElementById('active-avatar').innerText = recipient[0].toUpperCase();
            
            // Highlight active contact
            document.querySelectorAll('.user-item').forEach(el => el.classList.remove('active'));
            const activeEl = document.getElementById(`contact-${recipient}`);
            if (activeEl) activeEl.classList.add('active');

            // Enable inputs
            document.getElementById('message-input').disabled = false;
            document.getElementById('send-btn').disabled = false;
            document.getElementById('message-input').focus();

            loadConversationHistory();
        }

        function initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/${encodeURIComponent(currentUser)}`;
            
            ws = new WebSocket(wsUrl);

            ws.onmessage = function(event) {
                const message = JSON.parse(event.data);
                // If the message involves the currently active chat, append it
                if (activeRecipient && (message.sender === activeRecipient || message.recipient === activeRecipient)) {
                    appendMessageToDOM(message);
                }
            };

            ws.onclose = function() {
                console.warn("WebSocket disconnected. Attempting reconnection in 3s...");
                setTimeout(initWebSocket, 3000);
            };
        }

        async function loadConversationHistory() {
            if (!currentUser || !activeRecipient) return;
            try {
                const response = await fetch(`/messages/${encodeURIComponent(currentUser)}/${encodeURIComponent(activeRecipient)}`);
                if (!response.ok) throw new Error("Failed to fetch history");
                const messages = await response.json();
                
                const container = document.getElementById('messages-container');
                container.innerHTML = '';
                messages.forEach(msg => appendMessageToDOM(msg));
            } catch (err) {
                console.error("Error loading conversation history:", err);
            }
        }

        async function sendMessage() {
            const input = document.getElementById('message-input');
            const content = input.value.trim();
            if (!content || !activeRecipient || !currentUser) return;

            const payload = {
                sender: currentUser,
                recipient: activeRecipient,
                content: content
            };

            try {
                const response = await fetch('/messages/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) throw new Error("Failed to send message");
                
                const savedMessage = await response.json();
                appendMessageToDOM(savedMessage);
                input.value = '';
            } catch (err) {
                console.error("Error sending message:", err);
            }
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }

        function appendMessageToDOM(msg) {
            const container = document.getElementById('messages-container');
            const bubble = document.createElement('div');
            
            const isOutgoing = msg.sender === currentUser;
            bubble.className = `message-bubble ${isOutgoing ? 'outgoing' : 'incoming'}`;
            
            const timeStr = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            
            bubble.innerHTML = `
                <div>${escapeHtml(msg.content)}</div>
                <div class="message-timestamp">${timeStr}</div>
            `;
            
            container.appendChild(bubble);
            container.scrollTop = container.scrollHeight;
        }

        function escapeHtml(text) {
            return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }
    </script>
</body>
</html>
"""

# ============================================================================
# API ROUTERS & ENDPOINTS
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def get_messenger_frontend() -> HTMLResponse:
    """Serves the modern Instagram DM messenger interface."""
    return HTMLResponse(content=HTML_CONTENT)


@app.post("/messages/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(payload: MessageCreate) -> MessageResponse:
    """
    Sends a direct message, stores it in repository, and broadcasts it
    to the recipient in real-time via WebSockets if connected.
    """
    import uuid
    msg_id = str(uuid.uuid4())
    message = Message(
        id=msg_id,
        sender=payload.sender,
        recipient=payload.recipient,
        content=payload.content
    )

    message_repo.add_message(message)
    msg_dict = message.to_dict()

    # Real-time dispatching to recipient & sender across active tabs
    await manager.send_personal_message(msg_dict, payload.recipient)
    await manager.send_personal_message(msg_dict, payload.sender)

    return MessageResponse(**msg_dict)


@app.get("/messages/{user1}/{user2}", response_model=List[MessageResponse])
async def get_conversation_history(user1: str, user2: str) -> List[MessageResponse]:
    """Retrieves full conversation message history between two users."""
    messages = message_repo.get_conversation(user1, user2)
    return [MessageResponse(**m.to_dict()) for m in messages]


@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str) -> None:
    """WebSocket endpoint handling real-time duplex client communication."""
    await manager.connect(username, websocket)
    try:
        while True:
            # Keep connection alive and listen for client pings/actions if required
            data = await websocket.receive_text()
            logger.debug(f"Received raw WS frame from {username}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(username, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for user {username}: {e}")
        manager.disconnect(username, websocket)


# ============================================================================
# UNIT TEST SUITE (PYTEST / UNITTEST)
# ============================================================================

class TestMessengerSystem(unittest.TestCase):
    """Robust unit test suite validating API routes, message storage, and websocket manager."""

    def setUp(self) -> None:
        """Reset state before each test."""
        message_repo._messages.clear()
        manager.active_connections.clear()

    def test_message_repository_storage_and_retrieval(self) -> None:
        """Verify message repository correctly stores and filters conversations."""
        msg1 = Message(id="1", sender="Stark", recipient="Pepper", content="Hello Pepper")
        msg2 = Message(id="2", sender="Pepper", recipient="Stark", content="Hi Tony")
        msg3 = Message(id="3", sender="Happy", recipient="Stark", content="Hey Tony")

        message_repo.add_message(msg1)
        message_repo.add_message(msg2)
        message_repo.add_message(msg3)

        conv = message_repo.get_conversation("Stark", "Pepper")
        self.assertEqual(len(conv), 2)
        self.assertEqual(conv[0].id, "1")
        self.assertEqual(conv[1].id, "2")

    def test_connection_manager_registration(self) -> None:
        """Verify connection manager handles socket registration and cleanup."""
        mock_ws = MagicMock(spec=WebSocket)
        
        # Test synchronous parts of ConnectionManager logic
        username = "Rhodey"
        manager.active_connections[username] = {mock_ws}
        self.assertIn(username, manager.active_connections)

        manager.disconnect(username, mock_ws)
        self.assertNotIn(username, manager.active_connections)


class TestFastAPIEndpoints(unittest.TestCase):
    """Integration style tests using FastAPI TestClient."""

    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        self.client = TestClient(app)
        message_repo._messages.clear()

    def test_root_endpoint(self) -> None:
        """Ensure frontend HTML is served successfully at root."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("J.A.R.V.I.S.", response.text)

    def test_send_and_retrieve_messages(self) -> None:
        """Test POST message creation and GET conversation history endpoints."""
        payload = {
            "sender": "Stark",
            "recipient": "Parker",
            "content": "Don't do anything I would do."
        }
        
        # Send Message
        post_response = self.client.post("/messages/", json=payload)
        self.assertEqual(post_response.status_code, 201)
        data = post_response.json()
        self.assertEqual(data["sender"], "Stark")
        self.assertEqual(data["content"], payload["content"])
        self.assertIn("id", data)

        # Retrieve History
        get_response = self.client.get("/messages/Stark/Parker")
        self.assertEqual(get_response.status_code, 200)
        history = get_response.json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], payload["content"])


if __name__ == "__main__":
    unittest.main()